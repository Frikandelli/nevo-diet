"""Cheapest nutritionally adequate Dutch diet on real NEVO 2025 data and Checkjebon prices.

Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources.

Variables: x_i = grams/day of food i / 100 (so A and c are per 100 g).
"""
import csv
from dataclasses import dataclass

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, linprog, milp

from profiles import load_profile, requirements

NEVO = "data/nevo/NEVO2025_v9.0.csv"
# Pseudo-food: AH Care Vitamine D3 25 µg, 300 tablets for €4.99 (Checkjebon, 2026-10-30).
# One "unit" = 1 tablet; capped at 1/day.
COOKED = True  # default composition: as eaten (NEVO prepared entries x yield); run.py --raw switches it off
PROFILE = PROFILE_DEFAULT = "avg_man"  # data/profiles.tsv; run.py --profile switches it
# Absorbed iron (model rule, DESIGN.md): haem ~25%, non-haem ~10% absorbed. FE_ABS = HAEM_ABS*haem + NONHAEM_ABS*rest.
HAEM_ABS, NONHAEM_ABS = 0.25, 0.10
AMINO = ["HIS", "ILE", "LEU", "LYS", "SAA", "AAA", "THR", "TRP", "VAL"]
COMPUTED = {"FE_ABS"} | {f"AA_{a}" for a in AMINO}   # columns built here, not read from NEVO
SUPPLEMENTS = {"vitD_tablet": {"price": 4.99 / 300, "VITD": 25.0, "cap": 1.0, "group": "supplement"}}


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
    unit_g: np.ndarray       # grams per unit (100 for foods, 0 for tablets)
    profile: dict = None


def catalog_prices(chain=None):
    """{key: price row}: the given chain's price, or the cheapest chain when chain is None."""
    best = {}
    for r in csv.DictReader(open("data/catalog_prices.tsv"), delimiter="\t"):
        if chain and r["chain"] != chain:
            continue
        if r["key"] not in best or float(r["eur_per_100g"]) < float(best[r["key"]]["eur_per_100g"]):
            best[r["key"]] = r
    return best


def load(drop=(), price_file=None, cooked=None, chain=None, min_chains=0, profile=None, nonhaem=None):
    """Foods from the catalog (data/catalog_*.tsv, built by catalog.py), priced at `chain` or the cheapest chain.
    price_file: the old 50-food list with one price file instead. min_chains: drop foods sold at fewer chains.
    cooked=None follows COOKED. cooked=True: use the NEVO 'as eaten' entry (nevo_cooked) scaled by the yield,
    so x stays in grams as bought. yield 'P' = estimate from protein (raw protein / cooked protein).
    profile: a name in data/profiles.tsv (default PROFILE). nonhaem: non-haem iron absorption (default NONHAEM_ABS)."""
    cooked = COOKED if cooked is None else cooked
    prof = load_profile(profile or PROFILE)
    nonhaem = NONHAEM_ABS if nonhaem is None else nonhaem
    amino = {r["key"]: r for r in csv.DictReader(open("data/amino_foods.tsv"), delimiter="\t")}
    nevo = {r["NEVO-code"]: r for r in csv.DictReader(open(NEVO, encoding="utf-8"), delimiter="|")}
    colname = {k.split(" (")[0]: k for k in next(iter(nevo.values())).keys()}
    if price_file:
        foods = {r["key"]: r for r in csv.DictReader(open("data/foods.tsv"), delimiter="\t")}
        prices = {r["key"]: r for r in csv.DictReader(open(price_file), delimiter="\t")}
    else:
        foods = {r["key"]: r for r in csv.DictReader(open("data/catalog_foods.tsv"), delimiter="\t")
                 if int(r["n_chains"]) >= min_chains}
        prices = catalog_prices(chain)
    reqs = requirements(prof)
    cols = sorted(({c for r in reqs for c in r["cols"].split("+")} - COMPUTED)
                  | {"ENERCC", "FASAT", "NA", "HAEM", "PROT", "FE", "TRP"})

    keys = [k for k in foods if k in prices and k not in drop] + [k for k in SUPPLEMENTS if k not in drop]
    n = len(keys)
    c, cap, unit_g, groups = np.zeros(n), np.zeros(n), np.zeros(n), []
    N = {col: np.zeros(n) for col in [*cols, *COMPUTED]}
    missing = {col: np.zeros(n, bool) for col in [*cols, *COMPUTED]}
    for i, k in enumerate(keys):
        if k in SUPPLEMENTS:
            s = SUPPLEMENTS[k]
            c[i], cap[i], unit_g[i] = s["price"], s["cap"], 0
            groups.append(s["group"])
            for col in cols:
                N[col][i] = s.get(col, 0.0)
            continue
        f, row = foods[k], nevo[foods[k]["nevo"]]
        c[i], cap[i], unit_g[i] = float(prices[k]["eur_per_100g"]), np.inf, 100
        groups.append(f["group"])
        scale = 1.0
        if cooked and f.get("nevo_cooked"):
            raw, row = row, nevo[f["nevo_cooked"]]
            scale = (num(raw[colname["PROT"]]) / num(row[colname["PROT"]]) if f["yield"] == "P"
                     else float(f["yield"]))
        for col in cols:
            v = num(row[colname[col]])
            missing[col][i] = v is None
            N[col][i] = (v or 0.0) * scale
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
    return Model(keys, groups, c, cap, N, missing, reqs, unit_g, prof)


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
    lb = np.zeros(len(m.keys)) if lb is None else lb
    res = linprog(m.c if cost is None else cost, A_ub=G, b_ub=h,
                  bounds=list(zip(lb, m.cap)), method="highs")
    return res, G, h, lab


def nutrient_totals(m, x):
    return {r["name"]: sum(m.N[c] for c in r["cols"].split("+")) @ x for r in m.reqs}
