"""Shopping plans with whole packs at one chain.  python3 plan.py [--chain dekamarkt] -> plans.md

Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources.

Two plans per profile, both mixed-integer programs on the LP model of lp.py:
  weekly    the same shopping list every week;
  rotation  a 4-week cycle: different fresh food per week, stored nutrients averaged over the 4 weeks.

How food is bought (model decisions, DESIGN.md):
  fresh     whole packs (integer), eaten within the food's shelf life L (1, 2 or 4 weeks, freezer included);
            what isn't eaten in time is wasted but still paid for.
  pantry    keeps for months (dry goods, cans, oil, frozen vegetables, UHT milk, tablets): paid per gram used,
            because the rest of the pack carries over to the next cycle.
Nutrient windows: lower bounds of stored nutrients (vitamins A, D, B12, K1, absorbed iron, iodine, selenium,
EPA/DHA) hold on the 4-week average; everything else (and every upper limit) holds every week.
Plans are "not crazy": one chain, foods sold at >= 3 chains, no food above 30% of a week's energy.
"""
import argparse
import csv
import re
import time

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, linprog, milp
from scipy.sparse import lil_matrix

import lp
from lp import load, rows, solve
from profiles import all_profiles, load_profile

WEEKS = 4
STORED = {"vitA", "vitD", "vitB12", "vitK1", "iron_abs", "iodine", "selenium", "epa_dha"}
MAX_KCAL_SHARE = 0.30
FREEZER_KG = 10.0     # small freezer (2-3 drawers): food kept frozen between weeks (model decision)
FREEZER_GROUPS = {"bread", "meat", "fish", "meat_sub"}   # fresh foods that keep 4 weeks only by freezing
CANDIDATE_RC = 0.5     # foods whose reduced cost is within 50% of their price join the MILP
MAX_CANDIDATES = 90

NEVO_EN = {r["NEVO-code"]: r["Engelse naam/Food name"] for r in
           csv.DictReader(open("data/nevo/NEVO2025_v9.0.csv", encoding="utf-8"), delimiter="|")}
FOODS = {r["key"]: r for r in csv.DictReader(open("data/catalog_foods.tsv"), delimiter="\t")}
CHAINS = sorted({r["chain"] for r in csv.DictReader(open("data/catalog_prices.tsv"), delimiter="\t")})
BIG_CHAINS = [c for c in CHAINS if c not in ("poiesz", "vomar")]   # the two with tiny online ranges


def label(k):
    f = FOODS.get(k)
    return k if not f or f["source"] == "hand" else NEVO_EN[f["nevo"]][:34]


def packs(chain):
    """{key: (usable_g, pack_eur, product, pack_g)} at this chain. usable_g = the edible (drained, peeled) grams
    in the pack, the unit NEVO and the LP work in: pack_eur / eur_per_100g x 100."""
    return {r["key"]: (100 * float(r["pack_eur"]) / float(r["eur_per_100g"]), float(r["pack_eur"]), r["product"],
                       float(r["pack_g"]))
            for r in csv.DictReader(open("data/catalog_prices.tsv"), delimiter="\t") if r["chain"] == chain}


# ---- shelf life (model decisions; see DESIGN.md) ----
PANTRY_GROUPS = {"grain", "legume", "nut", "fat", "misc", "sweet", "exotic", "supplement"}
LONG_FRESH = r"kool (witte|rode|groene|savooie)|^wortel|winterpeen|^ui |^ui$|uien|aardappel|knol|pompoen|^appel"


def shelf(key, group, product):
    """'pantry' or the number of weeks a fresh pack keeps (freezer counted: bread, meat and fish keep 4)."""
    name = (NEVO_EN.get(FOODS[key]["nevo"], "") if key in FOODS else "").lower()
    dutch = product.lower()
    if group in PANTRY_GROUPS or key == "vitD_tablet":
        return "pantry"
    if group == "spread" and re.search(r"peanut|tahin|sesame", name):
        return "pantry"
    if key == "soy_drink" or re.search(r"^drink (soya|oat|rice|almond|coconut)|(soya|oat|rice) drink", name):
        return "pantry"   # plant drinks are sold in long-life cartons
    if re.search(r"houdba|uht|diepvries|blik|\bpot\b|glas|in (tomatensaus|olie|zonnebloemolie|water)", dutch) \
            or re.search(r"frozen|canned|tinned|tin\b|dried|powder", name):
        return "pantry"
    if group in ("bread", "meat", "fish", "meat_sub"):
        return 4          # freezer
    if group in ("cheese", "egg") or key == "margarine" or re.search(r"margarine|halvarine", name + dutch):
        return 4
    if group == "coldcut":
        return 2
    if group == "dairy":
        return 2 if re.search(r"yoghurt|kwark|quark|vla", dutch + name) else 1
    if group in ("veg", "fruit", "potato"):
        return 4 if re.search(LONG_FRESH, dutch) else 1
    if group == "drink":
        return 1
    return 1


def candidates(m, res):
    """Basket foods plus foods close to entering (reduced cost < CANDIDATE_RC x price)."""
    rc = res.lower.marginals
    score = np.where(res.x > 1e-7, -1.0, rc / np.maximum(m.c, 1e-9))
    keep = [i for i in np.argsort(score) if score[i] < CANDIDATE_RC][:MAX_CANDIDATES]
    return sorted(keep)


def build(m, idx, pk, weeks, kcal_share=MAX_KCAL_SHARE):
    """MILP over `weeks` weeks for the foods idx. Returns (c, A, lo, hi, integrality, bounds, layout)."""
    G, h, lab = rows(m)
    n_f = len(idx)
    kind = {}
    for i in idx:
        k = m.keys[i]
        kind[i] = shelf(k, m.groups[i], pk.get(k, (0, 0, ""))[2]) if m.unit_g[i] else "pantry"
    frozen = {i for i in idx if kind[i] == 4 and m.groups[i] in FREEZER_GROUPS}
    # variables: y[i,v] units eaten in week v; for fresh: n[i,w] packs bought in week w and u[i,w,v] eaten
    var, cost, integ, ub = {}, [], [], []

    def add(name, c, is_int, upper):
        var[name] = len(cost); cost.append(c); integ.append(1 if is_int else 0); ub.append(upper)

    for i in idx:
        for v in range(weeks):
            pantry = kind[i] == "pantry"
            add(("y", i, v), m.c[i] if pantry else 0.0, False, 7 * m.cap[i])
    for i in idx:
        if kind[i] == "pantry":
            continue
        g, eur, *_ = pk[m.keys[i]]
        L = kind[i]
        if weeks == 1:
            # weekly repeat: n packs every L weeks -> per week n/L packs, n*g/L grams
            add(("n", i, 0), eur / L, True, np.inf)
            add(("u", i, 0, 0), 0.0, False, np.inf)
        else:
            for w in range(weeks):
                add(("n", i, w), eur, True, np.inf)
                for d in range(min(L, weeks)):
                    add(("u", i, w, (w + d) % weeks), 0.0, False, np.inf)
    nv = len(cost)
    A_rows, lo, hi = [], [], []

    def row(coefs, l, u):
        A_rows.append(coefs); lo.append(l); hi.append(u)

    # nutrient rows: G y_v <= 7 h per week; stored lower bounds summed over the weeks
    for j, (name, side) in enumerate(lab):
        stored = name in STORED and side == "lo" and weeks > 1
        groups = [list(range(weeks))] if stored else [[v] for v in range(weeks)]
        for vs in groups:
            coefs = {var[("y", i, v)]: G[j, i] for i in idx for v in vs if G[j, i] != 0}
            row(coefs, -np.inf, 7 * h[j] * len(vs))
    # fresh: eaten = sum of batches; batches <= bought
    for i in idx:
        if kind[i] == "pantry":
            continue
        g = pk[m.keys[i]][0] / 100
        if weeks == 1:
            row({var[("y", i, 0)]: 1, var[("u", i, 0, 0)]: -1}, 0, 0)
            row({var[("u", i, 0, 0)]: 1, var[("n", i, 0)]: -g / kind[i]}, -np.inf, 0)
        else:
            for v in range(weeks):
                row({var[("y", i, v)]: 1, **{var[k]: -1 for k in var if k[0] == "u" and k[1] == i and k[3] == v}}, 0, 0)
            for w in range(weeks):
                row({**{var[k]: 1 for k in var if k[0] == "u" and k[1] == i and k[2] == w}, var[("n", i, w)]: -g},
                    -np.inf, 0)
    # freezer: what is kept frozen after a week (bought for later weeks) fits in FREEZER_KG
    cap_units = FREEZER_KG * 10
    if frozen:
        if weeks == 1:
            row({var[("n", i, 0)]: pk[m.keys[i]][0] / 100 * (kind[i] - 1) / kind[i] for i in frozen},
                -np.inf, cap_units)
        else:
            for v in range(weeks):
                coefs = {}
                for i in frozen:
                    g = pk[m.keys[i]][0] / 100
                    for w in range(weeks):
                        d0 = (v - w) % weeks
                        if d0 >= kind[i]:
                            continue              # batch w no longer kept in week v
                        coefs[var[("n", i, w)]] = coefs.get(var[("n", i, w)], 0) + g
                        for d in range(d0 + 1):
                            kk = var[("u", i, w, (w + d) % weeks)]
                            coefs[kk] = coefs.get(kk, 0) - 1
                row(coefs, -np.inf, cap_units)
    lay_frozen = frozen
    # no food above kcal_share of the week's energy
    if kcal_share:
        kc = m.N["ENERCC"]
        for v in range(weeks):
            for i in idx:
                if kc[i] > 0:
                    coefs = {var[("y", i2, v)]: -kcal_share * kc[i2] for i2 in idx if kc[i2] > 0}
                    coefs[var[("y", i, v)]] += kc[i]
                    row(coefs, -np.inf, 0)
    A = lil_matrix((len(A_rows), nv))
    for r, coefs in enumerate(A_rows):
        for cidx, val in coefs.items():
            A[r, cidx] = val
    return (np.array(cost), A.tocsr(), np.array(lo), np.array(hi), np.array(integ), np.array(ub),
            {"var": var, "kind": kind, "idx": idx, "weeks": weeks, "frozen": lay_frozen})


def plan(m, pk, weeks, kcal_share=MAX_KCAL_SHARE, time_limit=120):
    res, *_ = solve(m)
    if res.status != 0:
        return None
    idx = [i for i in candidates(m, res) if m.keys[i] in pk or not m.unit_g[i]]
    c, A, lo, hi, integ, ub, lay = build(m, idx, pk, weeks, kcal_share)
    t = time.time()
    r = milp(c, constraints=LinearConstraint(A, lo, hi), integrality=integ, bounds=Bounds(0, ub),
             options={"time_limit": time_limit, "mip_rel_gap": 1e-3})
    lay.update(seconds=time.time() - t, status=r.status, lp_cost=res.fun)
    if r.x is None:
        return None
    lay["x"], lay["cost"] = r.x, r.fun
    return lay


def eaten(lay, i, v):
    return lay["x"][lay["var"][("y", i, v)]]


def bought(lay, i, w):
    k = ("n", i, w)
    return round(lay["x"][lay["var"][k]]) if k in lay["var"] else 0


# ---------------- report ----------------
out = []
def p(s=""):
    print(s); out.append(s)


def shopping(m, pk, lay, title):
    W, var, x = lay["weeks"], lay["var"], lay["x"]
    per_day = lay["cost"] / (7 * W)
    p(f"### {title}: €{per_day:.2f}/day, €{per_day * 7:.2f}/week\n")
    p(f"Pure LP at this chain: €{lay['lp_cost']:.2f}/day, so whole packs, shelf life and the 30% rule cost "
      f"€{per_day - lay['lp_cost']:+.2f}/day. (MILP: {lay['seconds']:.1f} s.)\n")
    fresh = [i for i in lay["idx"] if lay["kind"][i] != "pantry" and any(bought(lay, i, w) for w in range(W))]
    pantry = [i for i in lay["idx"] if lay["kind"][i] == "pantry" and sum(eaten(lay, i, v) for v in range(W)) > 1e-4]
    if W == 1:
        p("**Fresh, whole packs** (buy every week unless said otherwise):\n")
        p("| product | food | packs | every | eaten g/day | wasted g/week | €/week |\n|---|---|---:|---|---:|---:|---:|")
        for i in sorted(fresh, key=lambda i: -bought(lay, i, 0) * pk[m.keys[i]][1]):
            g, eur, prod, pg = pk[m.keys[i]]
            n, L = bought(lay, i, 0), lay["kind"][i]
            eat = eaten(lay, i, 0) * 100
            waste = max(0.0, n * g / L - eat)
            p(f"| {prod} ({pg:.0f} g) | {label(m.keys[i])} | {n} | {'week' if L == 1 else f'{L} weeks'} | "
              f"{eat/7:.0f} | {waste:.0f} | {n*eur/L:.2f} |")
    else:
        p("**Fresh, whole packs per week:**\n")
        p("| product | food | " + " | ".join(f"wk {w+1}" for w in range(W)) + " | keeps | eaten g/day (avg) |\n"
          "|---|---|" + "---:|" * W + "---|---:|")
        for i in sorted(fresh, key=lambda i: -sum(bought(lay, i, w) for w in range(W)) * pk[m.keys[i]][1]):
            g, eur, prod, pg = pk[m.keys[i]]
            cells = " | ".join(str(bought(lay, i, w) or "") for w in range(W))
            avg = sum(eaten(lay, i, v) for v in range(W)) * 100 / (7 * W)
            L = lay["kind"][i]
            p(f"| {prod} ({pg:.0f} g, €{eur:.2f}) | {label(m.keys[i])} | {cells} | {L} wk | {avg:.0f} |")
        wk = [sum(bought(lay, i, w) * pk[m.keys[i]][1] for i in fresh) for w in range(W)]
        p("| **fresh € per week** | | " + " | ".join(f"**{e:.2f}**" for e in wk) + " | | |")
    p("\n**Pantry** (keeps for months; paid per gram used, the rest of the pack carries over):\n")
    p("| product | food | g/day | one pack lasts | €/week |\n|---|---|---:|---|---:|")
    for i in sorted(pantry, key=lambda i: -sum(eaten(lay, i, v) for v in range(W)) * m.c[i]):
        use = sum(eaten(lay, i, v) for v in range(W)) / W          # units per week
        if m.unit_g[i]:
            g, eur, prod, pg = pk[m.keys[i]]
            lasts = g / (use * 100) if use > 0 else np.inf
            p(f"| {prod} ({pg:.0f} g, €{eur:.2f}) | {label(m.keys[i])} | {use*100/7:.0f} | "
              f"{lasts:.1f} weeks | {use*m.c[i]:.2f} |")
        else:
            p(f"| AH Care Vitamine D3 25 µg (300 tablets, €4.99) | vitamin D tablet | {use/7:.2f} tablet | "
              f"{300/use:.0f} weeks | {use*m.c[i]:.2f} |")
    p()


def coverage(m, lay):
    """Per nutrient: lowest weekly (or 4-week) coverage."""
    W = lay["weeks"]
    p("**Nutrients** (% of requirement; stored nutrients on the 4-week average, the rest in the worst week):\n")
    p("| nutrient | requirement | worst week | ✓ |\n|---|---:|---:|---|")
    for r in m.reqs:
        if r["kind"] != "abs" or not r["lower"]:
            continue
        a = sum(m.N[c] for c in r["cols"].split("+"))
        weekly = [sum(a[i] * eaten(lay, i, v) for i in lay["idx"]) / 7 for v in range(W)]
        val = np.mean(weekly) if (r["name"] in STORED and W > 1) else min(weekly)
        pct = 100 * val / float(r["lower"])
        p(f"| {r['name']} | {float(r['lower']):.4g} {r['unit']} | {pct:.0f}% | {'✓' if pct > 99.9 else '✗'} |")
    p()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chain", help="chain for the shopping lists (default: cheapest weekly plan)")
    ap.add_argument("--profile", default="avg_man")
    a = ap.parse_args()
    lp.PROFILE = a.profile
    pr = load_profile(a.profile)

    p(f"# Shopping plans: whole packs at one chain\n")
    p("_Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources "
      "(Checkjebon prices 2026-10-30)._\n")
    p("Rules: one chain; only foods sold at >= 3 chains; no food above 30% of a week's energy; fresh food in "
      "whole packs within its shelf life (waste is paid for); pantry food paid per gram. Stored nutrients "
      "(vitamins A, D, B12, K1, iron, iodine, selenium, EPA/DHA) on the 4-week average, everything else "
      "every week. Freezer: at most 10 kg kept frozen between weeks.\n")
    p("**Not yet a diet you'd want to eat:** these are the cheapest nutrient baskets, bought as real packs. "
      "Meals, the vegetable/fruit minimums and variety rules are in `meals.py`.\n")

    # 1) the chosen profile: weekly plan per chain, pick the cheapest
    p(f"## 1. {pr['label']}: weekly plan per chain\n")
    p("| chain | pure LP €/day | weekly plan €/day | 4-week rotation €/day |\n|---|---:|---:|---:|")
    results = {}
    for ch in BIG_CHAINS:
        m = load(chain=ch, min_chains=3)
        pk = packs(ch)
        wk, rot = plan(m, pk, 1), plan(m, pk, WEEKS)
        results[ch] = (m, pk, wk, rot)
        f = lambda l: f"{l['cost']/(7*l['weeks']):.2f}" if l else "infeasible"
        p(f"| {ch} | {wk['lp_cost'] if wk else float('nan'):.2f} | {f(wk)} | {f(rot)} |")
    chain = a.chain or min((c for c in results if results[c][2]), key=lambda c: results[c][2]["cost"])
    m, pk, wk, rot = results[chain]
    p(f"\nShopping lists below are for **{chain}** "
      f"({'chosen' if a.chain else 'cheapest weekly plan'}; `python3 plan.py --chain <name>` for another).\n")

    p(f"## 2. Repeating weekly list at {chain}\n")
    shopping(m, pk, wk, "Weekly list")
    coverage(m, wk)
    p(f"## 3. 4-week rotation at {chain}\n")
    shopping(m, pk, rot, "Rotation")
    coverage(m, rot)

    # 3) crazy savings
    p("## 4. Crazy savings (not in any plan; opt in if you like)\n")
    p("| what | €/day | saving vs the weekly plan |\n|---|---:|---:|")
    base = wk["cost"] / 7
    nocap = plan(m, pk, 1, kcal_share=None)
    if nocap:
        p(f"| allow one food above 30% of energy | {nocap['cost']/7:.2f} | {base - nocap['cost']/7:.2f} |")
    mall = load(min_chains=0, chain=chain)
    allf = plan(mall, pk, 1)
    if allf:
        p(f"| also foods sold at fewer than 3 chains | {allf['cost']/7:.2f} | {base - allf['cost']/7:.2f} |")
    r_all, *_ = solve(load())
    p(f"| shop at every chain, any food, no packs (the pure LP) | {r_all.fun:.2f} | {base - r_all.fun:.2f} |")
    p()

    # 4) other profiles: comparison
    p("## 5. All profiles at their cheapest chain\n")
    p("| profile | chain | pure LP €/day | weekly plan €/day | rotation €/day | price of packs |\n"
      "|---|---|---:|---:|---:|---:|")
    for n in all_profiles():
        best = None
        for ch in BIG_CHAINS:
            mm = load(profile=n, chain=ch, min_chains=3)
            pkk = packs(ch)
            w = plan(mm, pkk, 1)
            if w and (best is None or w["cost"] < best[1]["cost"]):
                best = (ch, w, mm, pkk)
        ch, w, mm, pkk = best
        r4 = plan(mm, pkk, WEEKS)
        p(f"| {load_profile(n)['label']} | {ch} | {w['lp_cost']:.2f} | {w['cost']/7:.2f} | "
          f"{r4['cost']/28:.2f} | {w['cost']/7 - w['lp_cost']:+.2f} |")
    p()
    open("plans.md", "w").write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
