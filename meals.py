"""A week of meals at one chain.  python3 meals.py [--chain ah] [--strictness medium] -> meals.md

Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources.

One weekly MILP (it repeats every week):
  dinners   NEVO dishes from data/dinners.tsv that are priceable at the chain (dishes.py). k_d = evenings per week,
            G_d = grams per week, portion 300-600 g per evening, x1.0-1.5 with leftovers for the next brunch
            (brunch pattern; the classic pattern cooks 1.0-1.2). Nutrients: NEVO's own values for the dish.
            Its ingredients go on the shopping list (whole packs for fresh ones, like plan.py).
  brunch/   basic foods that are eaten as they are (no raw flour, sugar, tomato paste ...), from lp.py.
  sides     dinner sides (rice, potatoes, vegetables ...) and snacks are basic foods too.
Rules (DESIGN.md), each soft: breaking it costs a fixed penalty per week, set by the strictness:
  strict = never, medium = only if it saves >= €0.25/day, loose = if it saves >= €0.10/day.
  dinners_4      at least 4 different dinners a week
  dinner_max2    no dinner more than twice a week
  toppings_2     at least 2 different bread toppings a week
  veg_250        >= 250 g vegetables a day (dinner dishes count with their vegetable ingredients)
  fruit_200      >= 200 g fruit a day
  kcal_30        no single food or dish above 30% of the week's energy
Batch cooking: 'batch' dishes are cooked in the weekend session, at most BATCH_MAX evenings a week.
Starch sides (pasta, rice, potatoes) only on evenings whose dish takes one (dinners.tsv starch_side).
"""
import argparse
import csv
import dataclasses
import re
import time

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import hstack, lil_matrix

import categories as CAT
import dishes as D
import lp
import plan as P
from lp import load, rows, solve
from profiles import all_profiles, load_profile

PENALTY = {"strict": None, "medium": 0.25, "loose": 0.10}     # €/day for breaking one rule
RULES = ["dinners_4", "dinner_max2", "toppings_2", "veg_250", "fruit_200", "kcal_30"]
PORTION = (300, 600)          # g dish per evening
LEFTOVER = {"brunch": (1.0, 1.5), "classic": (1.0, 1.2)}
STARCH_SIDE_G = 150           # g of pasta, rice or potatoes per evening whose dish takes a starch side
BATCH_MAX = 3                 # evenings per week from the weekend batch session
TOPPING_GROUPS = {"cheese", "coldcut", "spread", "sweet"}
TOPPING_MIN_G = 50            # g per week before a topping counts as "used"
NOT_DIRECT = re.compile(r"^(flour|bread crumbs|dough|filo|corn starch|potato starch|bakery mix|vol-au-vent|yeast|"
                        r"sugar|tomato puree|semolina|wheat bran|oat bran|rice white raw w candied|salt low)", re.I)
ANIMAL = {"fish", "meat", "egg", "dairy", "cheese", "coldcut", "snack"}


def direct_ok(m, i):
    k = m.keys[i]
    if not m.unit_g[i]:
        return True                                   # vitamin D tablet
    f = P.FOODS.get(k)
    if f is None or int(f["n_chains"]) < 3:
        return False
    if k in ("flour_wholemeal", "flour_white", "sugar", "tomato_paste"):
        return False
    return not NOT_DIRECT.search(P.NEVO_EN.get(f["nevo"], ""))


def dish_model(m, chain, pattern, no_cats=()):
    """Append the chain's priceable dinner dishes to the model as pseudo-foods. Returns (model, dish info).
    no_cats: ticked categories; a dish with one of them anywhere in its recipe is left out, however small the amount."""
    cat = D.catalog(chain)
    roles = {r["code"]: r for r in csv.DictReader(open("data/dinners.tsv"), delimiter="\t")}
    info = []
    keyset = set(m.keys)
    for code, role in roles.items():
        if CAT.dish_blocked(code, no_cats):
            continue
        price, leaves, miss, subs, minor = D.price_dish(code, cat)
        if price is None or any(k not in keyset and k != "_veg_median" for k in leaves):
            continue
        info.append({"code": code, "key": f"dish{code}", "role": role["role"], "min": int(role["hands_on_min"]),
                     "side": role["starch_side"] == "yes",
                     "note": role["note"], "price": price, "leaves": leaves, "subs": subs, "minor": minor,
                     "name": D.NEVO[code]["Engelse naam/Food name"]})
    n0, nd = len(m.keys), len(info)
    N = {col: np.concatenate([v, np.zeros(nd)]) for col, v in m.N.items()}
    missing = {col: np.concatenate([v, np.zeros(nd, bool)]) for col, v in m.missing.items()}
    for j, d in enumerate(info):
        row = D.NEVO[d["code"]]
        i = n0 + j
        for col in m.N:
            if col in lp.COMPUTED:
                continue
            v = D.num(row[D.COL[col]]) if col in D.COL else None
            N[col][i] = v or 0.0
            missing[col][i] = v is None
        # amino acids: dish protein x the protein-weighted profile of its ingredients (incl. digestibility)
        wsum, prof = 0.0, {a: 0.0 for a in lp.AMINO}
        animal = False
        for k, g in d["leaves"].items():
            if k == "_veg_median":
                continue
            ii = m.keys.index(k)
            animal |= m.groups[ii] in ANIMAL
            pr = m.N["PROT"][ii] * g                     # protein (g) from this leaf per 100 g dish
            if m.N["PROT"][ii] > 0:
                for a in lp.AMINO:
                    prof[a] += pr * m.N[f"AA_{a}"][ii] / m.N["PROT"][ii]
                wsum += pr
        for a in lp.AMINO:
            N[f"AA_{a}"][i] = N["PROT"][i] * prof[a] / wsum if wsum else 0.0
        if not animal:
            for col in ("F20:5CN3", "F22:6CN3"):
                N[col][i] = 0.0
        N["FE_ABS"][i] = lp.HAEM_ABS * N["HAEM"][i] + lp.NONHAEM_ABS * (N["FE"][i] - N["HAEM"][i])
    mm = dataclasses.replace(
        m, keys=m.keys + [d["key"] for d in info], groups=m.groups + ["dish"] * nd,
        c=np.concatenate([m.c, np.zeros(nd)]), cap=np.concatenate([m.cap, np.full(nd, 99.0)]),
        N=N, missing=missing, unit_g=np.concatenate([m.unit_g, np.full(nd, 100.0)]),
        lb=np.concatenate([m.lb, np.zeros(nd)]))
    return mm, info


def build(mm, info, pk, chain, pattern, penalty, forced=None, no_batch=False):
    """forced: {rule: 0} to make a rule hard (for 'what does breaking it save')."""
    G, h, lab = rows(mm)
    n_food = len(mm.keys) - len(info)
    foods = [i for i in range(n_food)]
    own = {i for i in foods if mm.lb[i] > 0}             # your own foods: eaten as such, whatever direct_ok says
    direct = [i for i in foods if direct_ok(mm, i) or i in own]
    used_in_dish = {mm.keys.index(k) for d in info for k in d["leaves"] if k != "_veg_median"}
    active = sorted(set(direct) | used_in_dish)
    kind = {i: (P.shelf(mm.keys[i], mm.groups[i], pk.get(mm.keys[i], (0, 0, ""))[2]) if mm.unit_g[i] else "pantry")
            for i in active}
    for i in active:                                   # fresh foods need a pack at this chain
        if kind[i] != "pantry" and mm.keys[i] not in pk:
            kind[i] = "pantry"
    var, cost, integ, lo_b, hi_b = {}, [], [], [], []

    def add(name, c, is_int, lo, hi):
        var[name] = len(cost); cost.append(c); integ.append(is_int); lo_b.append(lo); hi_b.append(hi)

    for i in active:
        add(("y", i), mm.c[i] if kind[i] == "pantry" else 0.0, 0, 7 * mm.lb[i], 7 * mm.cap[i] if i in direct else 0)
        if kind[i] != "pantry":
            add(("n", i), pk[mm.keys[i]][1] / kind[i], 1, 0, np.inf)
    vegmed = D.veg_median(D.catalog(chain)) or 0.0
    lo_l, hi_l = LEFTOVER[pattern]
    for j, d in enumerate(info):
        allowed = not (no_batch and d["role"] == "batch")
        # cost of ingredients bought per gram of dish: pantry leaves at their price; fresh leaves via packs below;
        # '_veg_median' leaves at the chain's median vegetable price
        c_pantry = sum(g * mm.c[mm.keys.index(k)] for k, g in d["leaves"].items()
                       if k != "_veg_median" and kind[mm.keys.index(k)] == "pantry") + d["leaves"].get("_veg_median", 0) * vegmed
        add(("G", j), c_pantry, 0, 0, np.inf)
        add(("k", j), 0.0, 1, 0, 7 if allowed else 0)
        add(("z", j), 0.0, 1, 0, 1 if allowed else 0)
    rules = [r for r in RULES]
    for r in rules:
        hard = penalty is None or (forced and r in forced)
        add(("b", r), 0 if hard else 7 * penalty, 1, 0, 0 if hard else 1)
    for i in [i for i in active if mm.groups[i] in TOPPING_GROUPS and i in direct]:
        add(("t", i), 0.0, 1, 0, 1)

    A, lo, hi = [], [], []

    def row(coefs, l, u):
        A.append(coefs); lo.append(l); hi.append(u)

    dish_idx = {j: n_food + j for j in range(len(info))}
    # nutrients, per week: foods eaten directly + dishes
    for jr, (name, side) in enumerate(lab):
        coefs = {var[("y", i)]: G[jr, i] for i in active if G[jr, i] != 0}
        for j in range(len(info)):
            if G[jr, dish_idx[j]] != 0:
                coefs[var[("G", j)]] = G[jr, dish_idx[j]]
        row(coefs, -np.inf, 7 * h[jr])
    # purchases of fresh foods cover direct eating + dish ingredients
    for i in active:
        if kind[i] == "pantry":
            continue
        coefs = {var[("y", i)]: 1, var[("n", i)]: -pk[mm.keys[i]][0] / 100 / kind[i]}
        for j, d in enumerate(info):
            g = d["leaves"].get(mm.keys[i], 0)
            if g:
                coefs[var[("G", j)]] = g
        row(coefs, -np.inf, 0)
    # dinners: 7 a week, portions, counts
    row({var[("k", j)]: 1 for j in range(len(info))}, 7, 7)
    for j in range(len(info)):
        row({var[("G", j)]: 1, var[("k", j)]: -PORTION[0] * lo_l / 100}, 0, np.inf)
        row({var[("G", j)]: 1, var[("k", j)]: -PORTION[1] * hi_l / 100}, -np.inf, 0)
        row({var[("z", j)]: 1, var[("k", j)]: -1}, -np.inf, 0)          # z <= k
        row({var[("k", j)]: 1, var[("z", j)]: -7}, -np.inf, 0)          # k <= 7 z
        row({var[("k", j)]: 1, var[("b", "dinner_max2")]: -5}, -np.inf, 2)
    row({**{var[("z", j)]: 1 for j in range(len(info))}, var[("b", "dinners_4")]: 4}, 4, np.inf)
    row({var[("k", j)]: 1 for j, d in enumerate(info) if d["role"] == "batch"}, -np.inf, BATCH_MAX)
    # starch sides (pasta, rice, potatoes ...) only on evenings whose dish wants one, <= 150 g each
    # (your own foods aren't sides: you eat them when you like)
    starch = [i for i in direct if i not in own and (mm.groups[i] == "potato" or (mm.groups[i] == "grain" and not re.search(
        r"oat|muesli|cereal|flakes|bran", P.NEVO_EN.get(P.FOODS.get(mm.keys[i], {}).get("nevo", ""), ""), re.I)))]
    coefs = {var[("y", i)]: 1 for i in starch}
    for j, d in enumerate(info):
        if d["side"]:
            coefs[var[("k", j)]] = -STARCH_SIDE_G / 100
    row(coefs, -np.inf, 0)
    # toppings
    tops = [k for k in var if k[0] == "t"]
    for _, i in tops:
        row({var[("y", i)]: 1, var[("t", i)]: -TOPPING_MIN_G / 100}, 0, np.inf)   # t=1 only if >= 50 g/week
    row({**{var[k]: 1 for k in tops}, var[("b", "toppings_2")]: 2}, 2, np.inf)
    # vegetables and fruit (g/week): direct + vegetable ingredients of dishes
    vegc = {var[("y", i)]: 100 for i in active if mm.groups[i] == "veg" and i in direct}
    for j, d in enumerate(info):
        share = sum(g for k, g in d["leaves"].items() if k == "_veg_median" or mm.groups[mm.keys.index(k)] == "veg")
        if share:
            vegc[var[("G", j)]] = 100 * share
    vegc[var[("b", "veg_250")]] = 7 * 250
    row(vegc, 7 * 250, np.inf)
    fruc = {var[("y", i)]: 100 for i in active if mm.groups[i] == "fruit" and i in direct}
    fruc[var[("b", "fruit_200")]] = 7 * 200
    row(fruc, 7 * 200, np.inf)
    # 30% of energy, per food and per dish (big-M relaxed when broken)
    kc = mm.N["ENERCC"]
    tot = {var[("y", i)]: kc[i] for i in active if kc[i] > 0}
    for j in range(len(info)):
        tot[var[("G", j)]] = kc[dish_idx[j]]
    bigM = 7 * 6000
    # What you asked for of your own food doesn't count against the rule, only what the plan adds on top of it.
    for v, kci, asked in [(var[("y", i)], kc[i], 7 * mm.lb[i] * kc[i]) for i in active if kc[i] > 0] + \
                         [(var[("G", j)], kc[dish_idx[j]], 0.0) for j in range(len(info))]:
        coefs = {vv: -0.30 * c for vv, c in tot.items()}
        coefs[v] = coefs.get(v, 0) + kci
        coefs[var[("b", "kcal_30")]] = -bigM
        row(coefs, -np.inf, asked)

    M = lil_matrix((len(A), len(cost)))
    for r, coefs in enumerate(A):
        for cidx, val in coefs.items():
            M[r, cidx] = val
    lay = {"var": var, "kind": kind, "active": active, "direct": direct, "info": info, "n_food": n_food, "own": own,
           "n_nutrient_rows": len(lab)}
    return np.array(cost), M.tocsr(), np.array(lo), np.array(hi), np.array(integ), np.array(lo_b), np.array(hi_b), lay


def solve_week(mm, info, pk, chain, pattern="brunch", strictness="medium", forced=None, no_batch=False, limit=180):
    c, A, lo, hi, integ, lb, ub, lay = build(mm, info, pk, chain, pattern, PENALTY[strictness], forced, no_batch)
    t = time.time()
    r = milp(c, constraints=LinearConstraint(A, lo, hi), integrality=integ, bounds=Bounds(lb, ub),
             options={"time_limit": limit, "mip_rel_gap": 2e-3})
    if r.x is None:
        return None
    x = r.x
    var = lay["var"]
    broken = [k[1] for k in var if k[0] == "b" and x[var[k]] > 0.5]
    pen = sum(c[var[("b", b)]] for b in broken)
    lay.update(x=x, cost=r.fun - pen, objective=r.fun, broken=broken, seconds=time.time() - t, status=r.status)
    return lay


def closest_week(mm, info, pk, chain, pattern="brunch", strictness="medium", no_batch=False, limit=30):
    """When no week fits: the one that misses the nutrient limits by the least, in relative terms. What it misses is
    what's in the way. None if even that fails, so the meal rules themselves leave no room."""
    c, A, lo, hi, integ, lb, ub, lay = build(mm, info, pk, chain, pattern, PENALTY[strictness], None, no_batch)
    k = lay["n_nutrient_rows"]
    h = hi[:k]
    energy = next((float(r["lower"]) for r in mm.reqs if r["name"] == "energy" and r["lower"]), 2000.0)
    scale = np.where(np.abs(h) > 0, np.abs(h), 7 * energy)            # energy-share rows have h = 0 and are in kcal
    slack = lil_matrix((A.shape[0], k))
    for j in range(k):
        slack[j, j] = -1
    r = milp(np.r_[1e-6 * c, 1 / scale], constraints=LinearConstraint(hstack([A, slack.tocsr()]).tocsr(), lo, hi),
             integrality=np.r_[integ, np.zeros(k)], bounds=Bounds(np.r_[lb, np.zeros(k)], np.r_[ub, np.full(k, np.inf)]),
             options={"time_limit": limit, "mip_rel_gap": 1e-2})
    if r.x is None:
        return None
    lay.update(x=r.x[:len(c)])
    return lay


def most_of(mm, info, pk, chain, i, pattern="brunch", strictness="medium", no_batch=False, limit=30):
    """The most of food i (grams a day) any week can hold, with everything else as asked. None if none can."""
    c, A, lo, hi, integ, lb, ub, lay = build(mm, info, pk, chain, pattern, PENALTY[strictness], None, no_batch)
    v = lay["var"][("y", i)]
    lb[v], ub[v] = 0.0, np.inf
    goal = np.zeros(len(c))
    goal[v] = -1.0
    r = milp(goal, constraints=LinearConstraint(A, lo, hi), integrality=integ, bounds=Bounds(lb, ub),
             options={"time_limit": limit, "mip_rel_gap": 1e-2})
    return None if r.x is None else float(r.x[v]) * 100 / 7


# ---------------- report ----------------
out = []
def p(s=""):
    print(s); out.append(s)


def val(lay, k):
    return lay["x"][lay["var"][k]] if k in lay["var"] else 0.0


def week_report(mm, pk, lay, title):
    info, var = lay["info"], lay["var"]
    p(f"### {title}: €{lay['cost']/7:.2f}/day, €{lay['cost']:.2f}/week\n")
    if lay["broken"]:
        p("Rules bent (each saves at least the strictness threshold): " + ", ".join(lay["broken"]) + "\n")
    else:
        p("All rules kept.\n")
    p("**Dinners this week** (cook the portion shown; with leftovers it feeds the next brunch):\n")
    p("| dinner | evenings | g per evening | hands-on | kind | €/portion |\n|---|---:|---:|---:|---|---:|")
    for j, d in enumerate(info):
        k = round(val(lay, ("k", j)))
        if k:
            g = val(lay, ("G", j)) * 100 / k
            p(f"| {d['note']} ({d['name'][:40]}, NEVO {d['code']}) | {k} | {g:.0f} | {d['min']} min | {d['role']} | "
              f"{g/100*d['price']:.2f} |")
    p("\n**Eaten as such** (brunch, dinner sides, snacks), g/day:\n")
    p("| food | g/day | group |\n|---|---:|---|")
    for i in sorted(lay["direct"], key=lambda i: -val(lay, ("y", i))):
        y = val(lay, ("y", i))
        if y > 1e-4:
            amt = f"{y*100/7:.0f}" if mm.unit_g[i] else f"{y/7:.2f} tablet"
            p(f"| {P.label(mm.keys[i])} | {amt} | {mm.groups[i]} |")
    # shopping list
    p("\n**Shopping list** (whole packs for fresh food; pantry paid per gram, buy a pack when it runs out):\n")
    p("| product | food | buy | €/week |\n|---|---|---|---:|")
    use = {}
    for i in lay["active"]:
        u = val(lay, ("y", i))
        for j, d in enumerate(info):
            u += d["leaves"].get(mm.keys[i], 0) * val(lay, ("G", j))
        use[i] = u
    rows_ = []
    for i in lay["active"]:
        if use[i] < 1e-4:
            continue
        if not mm.unit_g[i]:
            rows_.append((use[i] * mm.c[i], f"| AH Care Vitamine D3 25 µg (300 tablets) | vitamin D tablet | "
                          f"{use[i]/7:.2f} a day | {use[i]*mm.c[i]:.2f} |"))
            continue
        g, eur, prod, pg = pk[mm.keys[i]] if mm.keys[i] in pk else (0, 0, "?", 0)
        if lay["kind"][i] == "pantry":
            weeks = g / (use[i] * 100) if use[i] else 0
            rows_.append((use[i] * mm.c[i], f"| {prod} ({pg:.0f} g) | {P.label(mm.keys[i])} | 1 pack per "
                          f"{weeks:.1f} weeks ({use[i]*100:.0f} g/week) | {use[i]*mm.c[i]:.2f} |"))
        else:
            n, L = round(val(lay, ("n", i))), lay["kind"][i]
            rows_.append((n * eur / L, f"| {prod} ({pg:.0f} g) | {P.label(mm.keys[i])} | {n} every "
                          f"{'week' if L == 1 else f'{L} weeks'} | {n*eur/L:.2f} |"))
    vm = sum(d["leaves"].get("_veg_median", 0) * val(lay, ("G", j)) for j, d in enumerate(info))
    if vm > 1e-4:
        vegmed = D.veg_median(D.catalog(CHAIN)) or 0
        rows_.append((vm * vegmed, f"| (vegetables sold per piece: celery, cucumber, courgette ...) | dish "
                      f"ingredients | {vm*100:.0f} g/week | {vm*vegmed:.2f} |"))
    for _, s in sorted(rows_, key=lambda t: -t[0]):
        p(s)
    p()


def coverage(mm, lay):
    info = lay["info"]
    p("**Nutrients per day** (% of requirement):\n")
    p("| nutrient | % | | nutrient | % |\n|---|---:|---|---|---:|")
    cells = []
    for r in mm.reqs:
        if r["kind"] != "abs" or not r["lower"]:
            continue
        a = sum(mm.N[c] for c in r["cols"].split("+"))
        v = sum(a[i] * val(lay, ("y", i)) for i in lay["active"])
        v += sum(a[lay["n_food"] + j] * val(lay, ("G", j)) for j in range(len(info)))
        cells.append((r["name"], 100 * v / 7 / float(r["lower"])))
    for k in range(0, len(cells), 2):
        a = cells[k]; b = cells[k + 1] if k + 1 < len(cells) else ("", 0)
        p(f"| {a[0]} | {a[1]:.0f} | | {b[0]} | {b[1]:.0f}{'' if b[0] else ''} |")
    p()


CHAIN = "ah"


def main():
    global CHAIN
    ap = argparse.ArgumentParser()
    ap.add_argument("--chain", default="ah")
    ap.add_argument("--strictness", default="medium", choices=list(PENALTY))
    a = ap.parse_args()
    CHAIN = a.chain
    pk = P.packs(a.chain)

    p("# A week of meals\n")
    p("_Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources "
      "(Checkjebon prices 2026-10-30)._\n")
    p(f"Chain: **{a.chain}**. Strictness: **{a.strictness}** (a rule is bent only if that saves at least "
      f"€{PENALTY[a.strictness] or 0:.2f}/day). Dinners are NEVO dishes (`data/dinners.tsv`); their nutrients are "
      "NEVO's values for the dish, their ingredients are on the shopping list. Everything else is basic foods.\n")

    lp.PROFILE = "avg_man"
    m = load(chain=a.chain, min_chains=0)
    mm, info = dish_model(m, a.chain, "brunch")
    p(f"{len(info)} dinner dishes are priceable at {a.chain}.\n")
    p("## 1. You: brunch + warm dinner + snacks\n")
    wk = solve_week(mm, info, pk, a.chain, "brunch", a.strictness)
    week_report(mm, pk, wk, "Week plan")
    coverage(mm, wk)
    base = P.plan(load(chain=a.chain, min_chains=3), pk, 1)
    p(f"Price of meals: the bare weekly basket at {a.chain} costs €{base['cost']/7:.2f}/day, so real "
      f"dinners, brunches and the rules add **€{wk['cost']/7 - base['cost']/7:+.2f}/day**.\n")

    p("## 2. What each rule costs\n")
    p("Each rule made strict on its own; the difference to the plan above (0.00 = kept anyway).\n")
    p("| rule | bent in the plan | €/day if kept strictly | extra €/day |\n|---|---|---:|---:|")
    for r in RULES:
        f = solve_week(mm, info, pk, a.chain, "brunch", a.strictness, forced={r: 0})
        extra = (f["cost"] - wk["cost"]) / 7 if f else float("nan")
        p(f"| {r} | {'yes' if r in wk['broken'] else 'no'} | {f['cost']/7 if f else float('nan'):.2f} | {extra:+.2f} |")
    p()
    p("## 3. Variants\n")
    p("| variant | €/day | rules bent |\n|---|---:|---|")
    for title, kw in [("strict (no rule bent)", {"strictness": "strict"}),
                      ("loose (bend for >= €0.10/day)", {"strictness": "loose"}),
                      ("no batch cooking (no weekend session)", {"no_batch": True}),
                      ("classic pattern: breakfast, lunch, dinner (no leftovers)", {"pattern": "classic"})]:
        kw2 = {"pattern": "brunch", "strictness": a.strictness, **kw}
        f = solve_week(mm, info, pk, a.chain, kw2["pattern"], kw2["strictness"], no_batch=kw.get("no_batch", False))
        p(f"| {title} | {f['cost']/7:.2f} | {', '.join(f['broken']) or '-'} |" if f else f"| {title} | infeasible | |")
    p()
    p("## 4. All profiles (classic pattern for the reference profiles)\n")
    p("| profile | pattern | €/day | rules bent | dinners |\n|---|---|---:|---|---|")
    for n in all_profiles():
        lp.PROFILE = n
        mn = load(chain=a.chain, min_chains=0)
        mmn, infon = dish_model(mn, a.chain, "brunch")
        pat = "brunch" if n == lp.PROFILE_DEFAULT else "classic"
        f = solve_week(mmn, infon, pk, a.chain, pat, a.strictness)
        dn = ", ".join(f"{d['note'].split(' (')[0].split(':')[0]} ×{round(val(f, ('k', j)))}"
                       for j, d in enumerate(infon) if round(val(f, ("k", j))))
        p(f"| {load_profile(n)['label']} | {pat} | {f['cost']/7:.2f} | {', '.join(f['broken']) or '-'} | {dn} |")
    lp.PROFILE = "avg_man"
    p()
    open("meals.md", "w").write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
