"""Cheapest nutritionally adequate Dutch diet on real NEVO 2025 data and Checkjebon prices.

Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources.

Variables: x_i = grams/day of food i / 100 (so A and c are per 100 g).
"""
import csv
import re
import dataclasses
from dataclasses import dataclass, field
from types import SimpleNamespace

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, linprog, milp
from scipy.sparse import csr_matrix, diags, hstack, vstack

import cooking
import supplements as S
from profiles import load_profile, requirements

NEVO = "data/nevo/NEVO2025_v9.0.csv"
COOKED = True  # default composition: each food as it's usually eaten (cooking.py); run.py --raw switches it off
PROFILE = PROFILE_DEFAULT = "avg_man"  # data/profiles.tsv; run.py --profile switches it
# Absorbed iron (model rule, DESIGN.md): haem ~25%, non-haem ~10% absorbed. FE_ABS = HAEM_ABS*haem + NONHAEM_ABS*rest.
HAEM_ABS, NONHAEM_ABS = 0.25, 0.10
AMINO = ["HIS", "ILE", "LEU", "LYS", "SAA", "AAA", "THR", "TRP", "VAL"]
COMPUTED = {"FE_ABS", "FRUIT", "MG_SUPP"} | {f"AA_{a}" for a in AMINO}   # columns built here, not read from NEVO
# Whole fruit (model rule, DESIGN.md), for the fruit-per-day box: fresh, frozen and tinned in juice or water count, the
# NEVO fruit group minus these. FRUIT = grams of whole fruit per unit (100 for those foods, 0 for the rest).
NOT_WHOLE_FRUIT = re.compile(r"dried|prunes|raisin|olive|lemon|lime|coconut|juice$|jam|syrup|snack|apple sauce tinned$",
                             re.I)
# Supplements (supplements.py, data/supplements.tsv): pseudo-foods per unit (a tablet, a capsule, a 5 g spoon), unit_g 0,
# group "supplement", with the label converted to what the norms count (supplements.counted). Which ones the plan may use,
# at what price and in what amount is `pills` (supplements.spec); None = the vitamin D 25 µg tablet only, at the cheapest
# shop, as the scripts and reports have it. No caps of their own (no food has a default cap since 2026-11-09): the
# nutrient maximums bound them (the vitamin D maximum of 100 µg allows 4 of the 25 µg tablets a day). Magnesium from
# pills (MG_SUPP) gets its own maximum, a requirement row added here when a pill has magnesium.
MG_SUPP_ROW = {"name": "magnesium_pills", "cols": "MG_SUPP", "unit": "mg", "kind": "abs", "per": "", "lower": "",
               "upper": f"{S.MG_SUPP_MAX:g}", "source": "EFSA: upper limit 250 mg/day for magnesium from supplements "
               "(readily dissociable salts and compounds like magnesium oxide); magnesium in food has none",
               "url": "https://www.efsa.europa.eu/sites/default/files/2024-05/ul-summary-report.pdf", "evidence": "confirmed"}
# Your own limits on foods and kinds of food (the app's "Limits on foods" box): "at most g grams a day of these foods
# together", as bought, one requirement row each (kind "food"), on a column of their own: LIMIT_COL + its number, 100 for
# the foods it covers (grams per unit), 0 for the rest. A row and not a cap on x_i, so a kind is one limit on the sum, the
# realistic week counts the food in dinners too (meals.dish_model), and the duals price it like any other limit.
LIMIT_COL = "LIMIT_"


def num(s):
    return float(s.replace(",", ".")) if s.strip() else None


@dataclass
class Model:
    keys: list               # food keys: hand-mapped names, or 'n<NEVO code>' for auto-matched foods
    groups: list
    c: np.ndarray            # € per unit
    cap: np.ndarray          # units
    N: dict                  # nevo column -> np.array per unit (missing -> 0)
    missing: dict            # nevo column -> bool array
    reqs: list
    unit_g: np.ndarray       # grams per unit (100 for foods, 0 for supplements: per tablet, capsule or spoon)
    profile: dict = None
    lb: np.ndarray = None    # units you want to eat anyway (your own foods); cap = lb when the amount is exact
    elsewhere: set = field(default_factory=set)   # your own foods not sold at this chain: priced at the cheapest other chain
    cooked: set = field(default_factory=set)        # keys counted as cooked (cooking.py)
    how: dict = field(default_factory=dict)          # key -> cooking.info(...)
    pills: dict = field(default_factory=dict)        # supplement key -> supplements.choose row (price, free, offer ...)


def catalog_prices(chain=None):
    """{key: price row}: the given chain's price, or the cheapest chain when chain is None."""
    best = {}
    for r in csv.DictReader(open("data/catalog_prices.tsv"), delimiter="\t"):
        if chain and r["chain"] != chain:
            continue
        if r["key"] not in best or float(r["eur_per_100g"]) < float(best[r["key"]]["eur_per_100g"]):
            best[r["key"]] = r
    return best


def load(drop=(), price_file=None, cooked=None, chain=None, min_chains=0, profile=None, nonhaem=None, own=(), flip=(),
         limits=(), pills=None):
    """Foods from the catalog (data/catalog_*.tsv, built by catalog.py), priced at `chain` or the cheapest chain.
    price_file: the old 50-food list with one price file instead. min_chains: drop foods sold at fewer chains.
    cooked=None follows COOKED. cooked=True: each food cooked or raw as cooking.py says by default, with the keys in
    `flip` turned the other way. Cooked = the NEVO 'as eaten' entry (nevo_cooked) scaled by the yield, so x stays in
    grams as bought (yield 'P' = estimate from protein: raw protein / cooked protein); or else the raw values x the USDA
    retention factors. cooked=False: every food raw.
    profile: a name in data/profiles.tsv (default PROFILE). nonhaem: non-haem iron absorption (default NONHAEM_ABS).
    own: your own foods, as (key, grams a day, exact?): at least that amount, or exactly it. They stay in whatever
    `drop`, `chain` or `min_chains` say about them (at the cheapest other chain if this one doesn't sell them).
    limits: your own maximums, as (name, food keys, grams a day): at most that many grams of those foods together. None by
    default: no food has a cap unless you set one (supplements can't be limited; they have no grams).
    pills: which supplements the plan may use (supplements.spec); None = the vitamin D 25 µg tablet only. Priced at this
    chain or at any shop, as the spec says; a supplement without a price is free. An exact amount fixes it (lb = cap)."""
    cooked = COOKED if cooked is None else cooked
    prof = load_profile(profile or PROFILE)
    nonhaem = NONHAEM_ABS if nonhaem is None else nonhaem
    amino = {r["key"]: r for r in csv.DictReader(open("data/amino_foods.tsv"), delimiter="\t")}
    nevo = {r["NEVO-code"]: r for r in csv.DictReader(open(NEVO, encoding="utf-8"), delimiter="|")}
    colname = {k.split(" (")[0]: k for k in next(iter(nevo.values())).keys()}
    own_keys = {o[0] for o in own}
    elsewhere = set()
    if price_file:
        foods = {r["key"]: r for r in csv.DictReader(open("data/foods.tsv"), delimiter="\t")}
        prices = {r["key"]: r for r in csv.DictReader(open(price_file), delimiter="\t")}
    else:
        foods = {r["key"]: r for r in csv.DictReader(open("data/catalog_foods.tsv"), delimiter="\t")
                 if int(r["n_chains"]) >= min_chains or r["key"] in own_keys}
        prices = catalog_prices(chain)
        if own_keys - prices.keys():
            anywhere = catalog_prices()
            elsewhere = {k for k in own_keys - prices.keys() if k in anywhere}
            prices.update({k: anywhere[k] for k in elsewhere})
    reqs = requirements(prof)
    cols = sorted(({c for r in reqs for c in r["cols"].split("+")} - COMPUTED)
                  | {"ENERCC", "FASAT", "NA", "HAEM", "PROT", "FE", "TRP"})

    chosen = {p["key"]: p for p in S.choose(pills, chain)}
    keys = ([k for k in foods if k in prices and (k not in drop or k in own_keys)]
            + [k for k, p in chosen.items() if k not in drop or p["exact"] is not None])
    how = {k: cooking.info(nevo[foods[k]["nevo"]]["Engelse naam/Food name"], foods[k]["group"], bool(foods[k].get("nevo_cooked")))
           for k in keys if k in foods}
    cook = cooking.cooked_keys(how, flip) if cooked else set()
    rf = cooking.retention()
    n = len(keys)
    c, cap, unit_g, groups = np.zeros(n), np.zeros(n), np.zeros(n), []
    N = {col: np.zeros(n) for col in [*cols, *COMPUTED]}
    missing = {col: np.zeros(n, bool) for col in [*cols, *COMPUTED]}
    for i, k in enumerate(keys):
        if k in chosen:
            c[i], cap[i], unit_g[i] = chosen[k]["price"], np.inf, 0
            groups.append("supplement")
            for col, v in S.counted(k)[0].items():
                if col in N:
                    N[col][i] = v
            continue
        f, row = foods[k], nevo[foods[k]["nevo"]]
        c[i], cap[i], unit_g[i] = float(prices[k]["eur_per_100g"]), np.inf, 100
        groups.append(f["group"])
        if f["group"] == "fruit" and not NOT_WHOLE_FRUIT.search(row["Engelse naam/Food name"]):
            N["FRUIT"][i] = 100.0
        scale, kept = 1.0, {}
        if k in cook and f.get("nevo_cooked"):
            raw, row = row, nevo[f["nevo_cooked"]]
            scale = (num(raw[colname["PROT"]]) / num(row[colname["PROT"]]) if f["yield"] == "P"
                     else float(f["yield"]))
        elif k in cook and how[k].usda:
            kept = rf[how[k].usda]
        for col in cols:
            v = num(row[colname[col]])
            missing[col][i] = v is None
            N[col][i] = (v or 0.0) * scale * kept.get(col, 1.0)
        # NEVO lists trace "DHA" in oats (0.04 g) and peanut butter (0.1 g) from lab analyses;
        # plants make no EPA/DHA, and the LP builds the vegetarian optimum on it. Zero it.
        if f["group"] not in ("fish", "meat", "egg", "dairy", "snack", "coldcut", "cheese"):
            for col in ("F20:5CN3", "F22:6CN3"):
                N[col][i] = 0.0
        # Essential amino acids: USDA mg per g protein (amino.py) x NEVO protein x digestibility.
        # Tryptophan from NEVO where it has a value.
        a = amino[k]
        dig = float(a["digestibility"])
        for aa in AMINO:
            N[f"AA_{aa}"][i] = float(a[f"{aa}_mg_per_g_prot"]) * N["PROT"][i] * dig
        if not missing["TRP"][i]:
            N["AA_TRP"][i] = N["TRP"][i] * dig
    # Absorbed iron (model rule): haem and non-haem absorbed at different rates. A blank HAEM counts as 0,
    # so all iron is then treated as non-haem (conservative).
    N["FE_ABS"] = HAEM_ABS * N["HAEM"] + nonhaem * (N["FE"] - N["HAEM"])
    lb = np.zeros(n)
    for key, g_day, exact in own:
        if key in keys:
            i = keys.index(key)
            lb[i] = g_day / 100
            if exact:
                cap[i] = g_day / 100
    for k, p in chosen.items():                  # a supplement at an exact amount: units a day
        if p["exact"] is not None and k in keys:
            i = keys.index(k)
            lb[i] = cap[i] = p["exact"]
    reqs = list(reqs)
    if N["MG_SUPP"].any():
        reqs.append(dict(MG_SUPP_ROW))
    for j, (name, members, g_day) in enumerate(limits):
        col, members = f"{LIMIT_COL}{j}", set(members)
        N[col] = np.array([100.0 if k in members and unit_g[i] else 0.0 for i, k in enumerate(keys)])
        missing[col] = np.zeros(n, bool)
        reqs.append({"name": name, "cols": col, "unit": "g", "kind": "food", "lower": "", "upper": f"{g_day:.6g}",
                     "source": "your own limit", "url": "", "evidence": "your choice"})
    return Model(keys, groups, c, cap, N, missing, reqs, unit_g, prof, lb, elsewhere, cook, how,
                 {k: p for k, p in chosen.items() if k in keys})


def rows(m: Model, overrides=None):
    """Build G x <= h. Returns (G, h, labels) where label = (req name, 'lo'|'hi')."""
    overrides = overrides or {}
    G, h, lab = [], [], []
    kcal = m.N["ENERCC"]
    for r in m.reqs:
        a = sum(m.N[c] for c in r["cols"].split("+"))
        lo, hi = (overrides.get(r["name"], (r["lower"], r["upper"])))
        lo = float(lo) if lo not in ("", None) else None
        hi = float(hi) if hi not in ("", None) else None
        if r["kind"] == "en":            # nutrient energy share, linear in x: 9*fat - frac*kcal >= 0
            e = 4.0 if r["cols"] in ("CHO", "PROT", "NVSUGAF") else 9.0   # kcal per g
            if lo is not None:
                G.append(-(e * a - lo / 100 * kcal)); h.append(0.0); lab.append((r["name"], "lo"))
            if hi is not None:
                G.append(e * a - hi / 100 * kcal); h.append(0.0); lab.append((r["name"], "hi"))
        else:
            if lo is not None:
                G.append(-a); h.append(-lo); lab.append((r["name"], "lo"))
            if hi is not None:
                G.append(a); h.append(hi); lab.append((r["name"], "hi"))
    return np.array(G), np.array(h), lab


def solve(m: Model, overrides=None, lb=None, extra=None, cost=None):
    G, h, lab = rows(m, overrides)
    if extra:
        for g_row, h_val, name in extra:
            G = np.vstack([G, g_row]); h = np.append(h, h_val); lab.append((name, "extra"))
    if not m.keys:           # you've excluded everything: no plan, and linprog won't take zero variables
        return SimpleNamespace(status=2, message="No foods left.", x=np.zeros(0), fun=None), G, h, lab
    if lb is None:
        lb = np.zeros(len(m.keys)) if m.lb is None else m.lb
    res = linprog(m.c if cost is None else cost, A_ub=G, b_ub=h,
                  bounds=list(zip(lb, m.cap)), method="highs")
    return res, G, h, lab


def most_units(m):
    """An upper bound on x_i in any adequate diet: the energy maximum, 6 kg for a food without energy, or the cap."""
    energy = [float(r["upper"]) for r in m.reqs if r["name"] == "energy" and r["upper"] not in ("", None)]
    kcal = m.N["ENERCC"]
    most = np.where(kcal > 0, (energy[0] if energy else np.inf) / np.maximum(kcal, 1e-9), np.inf)
    return np.minimum(np.minimum(most, 60.0), m.cap)


def solve_few(m, food_cost=0.0, limit=5):
    """The LP with a fixed cost per food in the basket, so a food only comes in if it saves at least that:
    min c·x + food_cost · sum z  s.t.  G x <= h,  x_i <= most_i z_i,  z binary. Your own foods (lb > 0) are free.

    The MILP only picks the foods. The LP is then solved again on those foods alone, so what comes back is an ordinary LP
    result: res.fun is the real price without the extra cost, and the shadow prices and price split still hold for the
    basket. Only foods in the plain LP's basket or with a reduced cost below half their price are considered, as in
    plan.py: that took 2-4 s down to under 1 s, and gave the same basket in every test. Plain LP if food_cost is 0, or if
    the MILP finds nothing in time."""
    res, G, h, lab = solve(m)
    if not food_cost or res.status != 0:
        return res, G, h, lab
    use = np.where((res.x > 1e-7) | (res.lower.marginals < 0.5 * m.c))[0]
    pay = use[m.lb[use] <= 0]                       # the foods with a z
    k, p = len(use), len(pay)
    Gu = csr_matrix(G[:, use])
    link = csr_matrix((np.ones(p), (np.arange(p), np.searchsorted(use, pay))), shape=(p, k))
    A = vstack([hstack([Gu, csr_matrix((Gu.shape[0], p))]), hstack([link, -diags(most_units(m)[pay])])]).tocsr()
    r = milp(np.r_[m.c[use], np.full(p, food_cost)], constraints=LinearConstraint(A, -np.inf, np.r_[h, np.zeros(p)]),
             integrality=np.r_[np.zeros(k), np.ones(p)],
             bounds=Bounds(np.r_[m.lb[use], np.zeros(p)], np.r_[m.cap[use], np.ones(p)]),
             options={"time_limit": limit, "mip_rel_gap": 1e-3})
    if r.x is None:
        return res, G, h, lab
    keep = set(use[m.lb[use] > 0]) | set(pay[r.x[k:] > 0.5])
    cap = np.array([m.cap[i] if i in keep else 0.0 for i in range(len(m.keys))])
    few = solve(dataclasses.replace(m, cap=cap))
    return few if few[0].status == 0 else (res, G, h, lab)


def nutrient_totals(m, x):
    return {r["name"]: sum(m.N[c] for c in r["cols"].split("+")) @ x for r in m.reqs}
