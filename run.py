"""Run all analyses per profile and write reports/<profile>.md.  python3 run.py [--raw] [--profile NAME ...]"""
import argparse
import os

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, linprog, milp

import explain
import lp
from lp import load, nutrient_totals, rows, solve
from profiles import all_profiles

ap = argparse.ArgumentParser()
ap.add_argument("--raw", action="store_true", help="raw NEVO values instead of cooked (as eaten)")
ap.add_argument("--profile", nargs="*", help="profiles from data/profiles.tsv (default: all)")
args = ap.parse_args()
lp.COOKED = not args.raw

out = []
def p(s=""):
    print(s); out.append(s)


def basket(m, x, cost, title):
    p(f"**{title}: €{cost:.2f}/day (€{7*cost:.2f}/week)**\n")
    p("| food | g/day | €/day | |\n|---|---:|---:|---|")
    for i in np.argsort(-(x * np.where(m.unit_g > 0, m.unit_g, 1))):
        if x[i] > 1e-6:
            amt = f"{x[i]*m.unit_g[i]:.0f}" if m.unit_g[i] else f"{x[i]:.2f} tablet"
            p(f"| {label(m.keys[i])} | {amt} | {x[i]*m.c[i]:.2f} | {'cap' if abs(x[i]-m.cap[i]) < 1e-7 else ''} |")
    p()


def diagnose(m, drop_note):
    """Elastic LP: minimise total relative violation to name the conflicting requirements."""
    G, h, lab = rows(m)
    k, n = len(h), len(m.keys)
    scale = np.maximum(np.abs(h), 1.0)
    A = np.hstack([G, -np.diag(scale)])
    res = linprog(np.r_[np.zeros(n), np.ones(k)], A_ub=A, b_ub=h,
                  bounds=list(zip(np.zeros(n), m.cap)) + [(0, None)] * k, method="highs")
    s = res.x[n:]
    viol = [f"{lab[j][0]} ({lab[j][1]}, short by {100*s[j]*scale[j]/abs(h[j]) if h[j] else s[j]:.0f}%)"
            for j in np.argsort(-s) if s[j] > 1e-6]
    p(f"Infeasible {drop_note}. Smallest fix violates: " + ", ".join(viol))
    p()


import csv, re
NEVO_EN = {r["NEVO-code"]: r["Engelse naam/Food name"] for r in
           csv.DictReader(open("data/nevo/NEVO2025_v9.0.csv", encoding="utf-8"), delimiter="|")}
FOODS = {r["key"]: r for r in csv.DictReader(open("data/catalog_foods.tsv"), delimiter="\t")}


def keys(groups=(), name=None, keep=()):
    """Catalog food keys in these groups and/or whose English NEVO name matches `name` (regex)."""
    return tuple(k for k, f in FOODS.items() if k not in keep and (f["group"] in groups or
                 (name and re.search(name, NEVO_EN[f["nevo"]], re.I))))


def label(k):
    """Readable food name: hand-mapped key, or the NEVO English name for auto-matched foods."""
    f = FOODS.get(k)
    return k if not f or f["source"] == "hand" else NEVO_EN[f["nevo"]][:32]


def report(profile):
    lp.PROFILE = profile
    out.clear()
    m = load()
    res, G, h, lab = solve(m)
    x, v = res.x, res.fun

    pr = m.profile
    p(f"# {pr['label']}: cheapest adequate Dutch diet, NEVO 2025 + Checkjebon prices (2026-10-30), {len(FOODS)} foods\n")
    p("_Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources._\n")
    p(f"Profile `{pr['name']}`: {pr['sex']}, {pr['age']}, {pr['weight']:.1f} kg, {pr['energy']:.0f} kcal, "
      f"{pr['protein']:.0f} g protein. Source: {pr['source']}.\n")
    p(f"Composition: {'cooked, as eaten (NEVO prepared entries x yield)' if lp.COOKED else 'raw NEVO values'}.\n")
    p("## 1. Base LP (cheapest product per food across all chains)\n")
    basket(m, x, v, "Optimum")

    # binding constraints and shadow prices, expressed as € per +10% of the requirement
    slack = h - G @ x
    reqs = {r["name"]: r for r in m.reqs}
    p("Binding constraints (shadow price = extra €/day if this requirement rose by 10%):\n")
    p("| constraint | side | requirement | €/day per +10% | main sources |\n|---|---|---:|---:|---|")
    T = 0
    for j, (name, side) in enumerate(lab):
        if slack[j] < 1e-7:
            T += 1
            y = -res.ineqlin.marginals[j]
            r = reqs[name]
            b = r["lower"] if side == "lo" else r["upper"]
            unit = "en%" if r["kind"] == "en" else r["unit"]
            # en% rows have rhs 0; +10% of the share shifts the row by 0.1*share*total kcal
            tenpct = y * 0.1 * (abs(h[j]) if h[j] else float(b) / 100 * (m.N["ENERCC"] @ x))
            a = sum(m.N[c] for c in r["cols"].split("+"))
            top = sorted(((a[i] * x[i], label(m.keys[i])) for i in range(len(x)) if x[i] > 1e-7), reverse=True)[:2]
            p(f"| {name} | {side} | {b} {unit} | {tenpct:.3f} | {', '.join(k for _, k in top)} |")
    caps = sum(abs(x - m.cap) < 1e-7)
    S = sum(x > 1e-7)
    p(f"\nSparsity check: |S| = {S} foods used, |T| = {T} tight nutrient rows + {caps} caps = {T+caps}. "
      f"Lemma from the earlier chat says |S| <= |T|: {'holds' if S <= T + caps else 'VIOLATED'}.\n")

    # missing NEVO values among the basket for binding nutrients
    p("NEVO gaps in the basket (blank cell counted as 0, so the true intake is higher):\n")
    gaps = []
    for j, (name, side) in enumerate(lab):
        if slack[j] < 1e-7 and side == "lo":
            for col in reqs[name]["cols"].split("+"):
                for i in np.where((x > 1e-7) & m.missing[col])[0]:
                    gaps.append(f"{label(m.keys[i])}:{col}")
    p(", ".join(gaps) or "none")
    p()

    # reduced costs
    p("## 2. Reduced costs: how much cheaper an unused food must get before it enters\n")
    rc = res.lower.marginals
    p("| food | price €/100g | reduced cost €/100g | needed price drop |\n|---|---:|---:|---:|")
    NOTABLE = ("yeast_flakes", "chicken_liver", "tofu", "egg", "cheese_gouda", "frikandelbroodje", "sardines",
               "chicken_thigh", "mince_mixed", "soy_drink", "oats", "banana", "apple", "peanut_butter")
    order = [i for i in np.argsort(rc / m.c) if x[i] < 1e-9 and m.unit_g[i]]
    for i in order[:25] + [i for i in order[25:] if m.keys[i] in NOTABLE]:
        p(f"| {label(m.keys[i])} | {m.c[i]:.3f} | {rc[i]:.3f} | {100*rc[i]/m.c[i]:.0f}% |")
    p(f"\n({len(order)} unused foods; the 25 closest to entering plus notable ones shown.)")
    p()

    # variants
    p("## 3. Variants\n")
    def variant(title, **kw):
        mm = load(**{k: v for k, v in kw.items() if k in ("drop", "price_file", "chain")})
        r, *_ = solve(mm, overrides=kw.get("overrides"))
        if r.status == 0:
            used = ", ".join(f"{label(mm.keys[i])} {r.x[i]*mm.unit_g[i]:.0f}g" if mm.unit_g[i] else f"{label(mm.keys[i])} {r.x[i]:.2f}"
                             for i in np.argsort(-r.x * np.maximum(mm.unit_g, 1)) if r.x[i] > 1e-6)
            p(f"- **{title}: €{r.fun:.2f}/day** (+€{r.fun - v:.2f}). {used}")
        else:
            p(f"- **{title}:**"); diagnose(mm, "")
        return r

    fish_meat = keys(("fish", "meat", "coldcut", "snack"))
    salts = keys(name=r"^Salt")
    variant("No vitamin D tablet (D from food only)", drop=("vitD_tablet",))
    variant("No iodised salt", drop=keys(name=r"^Salt .*iodine"))
    variant("No bread and no iodised salt (the RIVM iodine worry)",
            drop=keys(("bread",), name=r"^Salt .*iodine|^Flour"))
    variant("Vegetarian (no fish/meat)", drop=fish_meat)
    variant("Vegetarian, EPA+DHA requirement dropped", drop=fish_meat, overrides={"epa_dha": ("", "")})
    variant("Vegan (also no dairy/eggs/cheese/spreads, fortified soy drink allowed)",
            drop=fish_meat + keys(("dairy", "cheese", "egg", "spread"), keep=("soy_drink",)), overrides={"epa_dha": ("", "")})
    for chain in ("ah", "lidl", "dirk", "jumbo"):
        variant(f"Only {chain.upper()} prices", chain=chain)
    p()

    # frikandelbroodje
    p("## 4. A frikandelbroodje every day\n")
    i_f = m.keys.index("frikandelbroodje")
    lb = np.zeros(len(m.keys)); lb[i_f] = 1.45
    r, *_ = solve(m, lb=lb)
    if r.status == 0:
        p(f"Forcing 145 g/day: €{r.fun:.2f}/day, so +€{r.fun - v:.2f}/day. The snack itself costs €{1.45*m.c[i_f]:.2f}; "
          f"the reduced cost predicted +€{1.45*rc[i_f]:.2f}.")
        Gf, hf, labf = rows(m)
        sl = hf - Gf @ r.x
        p("Newly binding: " + ", ".join(n for j, (n, s) in enumerate(labf) if sl[j] < 1e-7 and s == "hi"))
    else:
        diagnose(m, "with a daily frikandelbroodje")
    tot = {k: (m.N[k][i_f] * 1.45) for k in ("ENERCC", "PROT", "FAT", "FASAT", "NA")}
    p(f"\nOne broodje (NEVO 3373, 145 g): {tot['ENERCC']:.0f} kcal, {tot['PROT']:.1f} g protein, {tot['FAT']:.1f} g fat "
      f"({tot['FASAT']:.1f} g saturated = {100*9*tot['FASAT']/tot['ENERCC']:.0f}% of its energy), {tot['NA']*2.5/1000:.1f} g salt.\n")

    # realism MILP
    p("## 5. Realistic basket (MILP)\n")
    p("Extra rules: vegetables >= 250 g, fruit >= 200 g, milk/drinks/yoghurt <= 500 g, no raw flour, "
      "rice/pasta <= 150 g, at least 10 foods each at >= 20 g.\n")
    mm = load(drop=keys(name=r"^Flour"))
    n = len(mm.keys)
    G2, h2, _ = rows(mm)
    grp = np.array(mm.groups)
    veg = np.where(grp == "veg", 1.0, 0)
    fruit = np.where(grp == "fruit", 1.0, 0)
    liquid_keys = set(keys(name=r"^(Milk|Drink|Yoghurt|Buttermilk|Kefir)"))
    liquid = np.array([1.0 if k in liquid_keys else 0 for k in mm.keys])
    cap = mm.cap.copy()
    for k in keys(name=r"^(Rice|Pasta)"):
        if k in mm.keys:
            cap[mm.keys.index(k)] = 1.5
    is_food = (mm.unit_g > 0).astype(float)
    Z = np.zeros((1, n))
    cons = [
        LinearConstraint(np.hstack([G2, np.zeros_like(G2)]), -np.inf, h2),
        LinearConstraint(np.r_[veg, np.zeros(n)][None], 2.5, np.inf),
        LinearConstraint(np.r_[fruit, np.zeros(n)][None], 2.0, np.inf),
        LinearConstraint(np.r_[liquid, np.zeros(n)][None], -np.inf, 5.0),
        LinearConstraint(np.hstack([np.eye(n), -np.diag(cap)]), -np.inf, 0),          # x <= cap*z
        LinearConstraint(np.hstack([np.eye(n), -0.2 * np.diag(is_food)]), 0, np.inf),  # x >= 0.2 z (foods)
        LinearConstraint(np.r_[np.zeros(n), is_food][None], 10, np.inf),
    ]
    r = milp(np.r_[mm.c, np.zeros(n)], constraints=cons, integrality=np.r_[np.zeros(n), np.ones(n)],
             bounds=Bounds(np.zeros(2 * n), np.r_[cap, np.ones(n)]))
    if r.status == 0:
        basket(mm, r.x[:n], r.fun, "Realistic optimum")
        p(f"Price of realism: +€{r.fun - v:.2f}/day over the raw optimum.\n")
    else:
        p(f"MILP status {r.status}: {r.message}\n")

    # protein sweep
    p("## 6. Protein sweep\n")
    p("| protein g/day | g/kg | min €/day | marginal €/g | new foods |\n|---:|---:|---:|---:|---|")
    prev, prev_used = None, set()
    W = m.profile["weight"]
    for prot in [round(gkg * W) for gkg in (0.8, 1.0, 1.2, 1.6, 2.0, 2.4, 2.8)]:
        r, *_ = solve(m, overrides={"protein": (prot, "")})
        if r.status != 0:
            p(f"| {prot} | {prot/W:.1f} | infeasible | | |"); continue
        used = {label(m.keys[i]) for i in range(len(m.keys)) if r.x[i] > 1e-6}
        mc = "" if prev is None else f"{(r.fun-prev[1])/(prot-prev[0]):.4f}"
        p(f"| {prot} | {prot/W:.2f} | {r.fun:.2f} | {mc} | {', '.join(sorted(used - prev_used)) if prev else ''} |")
        prev, prev_used = (prot, r.fun), used
    p()

    # ranges in the 5% near-optimal polytope
    p("## 7. Ranges within 5% of the optimum cost (flux-variability style)\n")
    Gc = np.vstack([G, m.c]); hc = np.append(h, 1.05 * v)
    p("| food | min g | max g |\n|---|---:|---:|")
    for i, k in enumerate(m.keys):
        if x[i] < 1e-7 and rc[i] > 0.05 * m.c[i]:
            continue                           # far from entering: skip the two LPs
        e = np.zeros(len(m.keys)); e[i] = 1
        lo = linprog(e, A_ub=Gc, b_ub=hc, bounds=list(zip(np.zeros(len(m.keys)), m.cap)), method="highs").fun
        hi = -linprog(-e, A_ub=Gc, b_ub=hc, bounds=list(zip(np.zeros(len(m.keys)), m.cap)), method="highs").fun
        if hi > 1e-6:
            f = m.unit_g[i] or 1
            p(f"| {label(k)} | {lo*f:.0f} | {hi*f:.0f} |")
    p()

    # nutrient totals for the base optimum, incl. K1/K2
    p("## 8. Nutrient totals at the base optimum\n")
    tot = nutrient_totals(m, x)
    p("| nutrient | intake | lower | upper |\n|---|---:|---:|---:|")
    for r in m.reqs:
        val = tot[r["name"]]
        if r["kind"] == "en":
            e = 4.0 if r["cols"] in ("CHO", "PROT", "NVSUGAF") else 9.0
            val = 100 * e * val / tot["energy"]
            unit = "en%"
        else:
            unit = r["unit"]
        p(f"| {r['name']} | {val:.1f} {unit} | {r['lower']} | {r['upper']} |")
    k2 = m.N["VITK1"] @ x  # placeholder to keep column order obvious
    p()

    # ---- stage 3 ----
    def chains_of(k):
        f = FOODS.get(k)
        return (int(f["n_chains"]), f["chains"]) if f else (10, "all (tablet)")

    def flag(k):
        return " ⚠" if chains_of(k)[0] < 3 else ""

    p("## 9. Availability\n")
    p("Foods sold at fewer than 3 of the 10 chains are marked ⚠ (unrealistic). Chains per food in the basket:\n")
    p("| food | g/day | chains | sold at |\n|---|---:|---:|---|")
    for i in np.argsort(-(x * np.where(m.unit_g > 0, m.unit_g, 1))):
        if x[i] > 1e-6:
            n_ch, ch = chains_of(m.keys[i])
            p(f"| {label(m.keys[i])}{flag(m.keys[i])} | {x[i]*m.unit_g[i]:.0f} | {n_ch} | {ch} |")
    m3 = load(min_chains=3)
    r3, *_ = solve(m3)
    p(f"\nOnly foods sold at >= 3 chains ({len(m3.keys)} foods): **€{r3.fun:.2f}/day** (+€{r3.fun - v:.2f}).\n")

    p("## 10. Why each food is in the basket: the price split\n")
    p("At the optimum each food's price splits exactly over the binding requirements: c_i = Σ_j y_j·a_ji "
      "(complementary slackness). The share y_j·a_ji / c_i is the part of the price that pays for nutrient j. "
      "Negative shares are upper limits the food pushes against (salt, energy maximum). A food at its cap is "
      "worth more than it costs; the excess is its *cap rent*.\n")
    p("| food | €/100 g | 1st | 2nd | penalised by | cap rent €/100 g |\n|---|---:|---|---|---|---:|")
    split = explain.price_split(m, res, G, lab)
    for i in sorted(split, key=lambda i: -x[i] * m.c[i]):
        s = split[i]
        tops = explain.top_shares(s, 2) + [("", 0)] * 2
        neg = ", ".join(f"{k} {100*v/s['price']:.0f}%" for k, v in sorted(s["shares"].items(), key=lambda t: t[1])
                        if v < -1e-9)
        p(f"| {label(m.keys[i])} | {s['price']:.3f} | {tops[0][0]} {100*tops[0][1]:.0f}% | "
          + (f"{tops[1][0]} {100*tops[1][1]:.0f}%" if tops[1][0] else "") + f" | {neg} | "
          + (f"{s['cap_rent']:.3f}" if s["cap_rent"] > 1e-9 else "") + " |")
    p("\n(Shares are of the food's positive value; 1st/2nd = the nutrients it is mainly bought for.)\n")

    p("## 11. Alternatives: remove the biggest food, see what replaces it\n")
    p("Each line removes one more food (the biggest by grams, three branches per level, three levels) and "
      "re-solves. Every line is a complete, valid diet.\n")
    tree = explain.removal_tree(m, depth=3, branch=3)
    for nd in tree[1:]:
        ind = "  " * (len(nd["path"]) - 1)
        what = f"without {label(nd['path'][-1])}"
        if nd["infeasible"]:
            p(f"{ind}- {what}: **infeasible**"); continue
        if nd["same_as"]:
            p(f"{ind}- {what}: same diet as without {' + '.join(label(k) for k in nd['same_as'])}"); continue
        rep = ", ".join(f"{label(k)}{flag(k)} +{g:.0f} g" for k, g in nd["replaced_by"])
        p(f"{ind}- {what}: €{nd['cost']:.2f} ({nd['delta']:+.2f}) → {rep}")
    p()

    p("## 12. Diagnostic: drop one requirement at a time\n")
    p("What each rule costs: the saving if it were dropped, and the foods that leave or enter.\n")
    p("| requirement | saving €/day | leaves | enters |\n|---|---:|---|---|")
    for name, d, gone, new in explain.nutrient_removal(m, res):
        if d is None:
            p(f"| {name} | (unbounded or infeasible) | | |"); continue
        if d > -0.005 and not gone and not new:
            continue
        p(f"| {name} | {-d:.2f} | {', '.join(label(m.keys[i]) for i in gone)} | "
          f"{', '.join(label(m.keys[i]) + flag(m.keys[i]) for i in new)} |")
    p("\n(Requirements whose removal changes nothing are left out.)\n")

    os.makedirs("reports", exist_ok=True)
    open(f"reports/{pr['name']}.md", "w").write("\n".join(out) + "\n")


for name in args.profile or all_profiles():
    report(name)
