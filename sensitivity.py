"""How much do cooking losses and absorption change the answer?  python3 sensitivity.py -> reports/sensitivity.md

Cooking: each food as usually eaten, NEVO 'as eaten' entries x yield or USDA retention factors (cooking.py, lp.load(cooked=True)).
Absorption: NEVO is not corrected for bioavailability (background doc §4.4), so we vary the
assumptions that the Dutch norms (set for a typical mixed diet) quietly make.
"""
import copy
import csv

import numpy as np

import lp
from lp import load, solve

NEVO_EN = {r["NEVO-code"]: r["Engelse naam/Food name"] for r in
           csv.DictReader(open("data/nevo/NEVO2025_v9.0.csv", encoding="utf-8"), delimiter="|")}
FOODS = {r["key"]: r for r in csv.DictReader(open("data/catalog_foods.tsv"), delimiter="\t")}


def name_of(k):
    f = FOODS.get(k)
    return k if not f or f["source"] == "hand" else NEVO_EN[f["nevo"]][:28]

out = []
def p(s=""):
    print(s); out.append(s)


def run(m, label, base=None, overrides=None):
    r, G, h, lab = solve(m, overrides=overrides)
    if r.status != 0:
        p(f"| {label} | infeasible | | |"); return None
    sl = h - G @ r.x
    binding = ", ".join(n for j, (n, s) in enumerate(lab) if sl[j] < 1e-7 and n in
                        ("iron_abs", "zinc", "calcium", "vitC", "folate", "thiamin", "potassium", "riboflavin"))
    top = ", ".join(f"{name_of(m.keys[i])} {r.x[i]*m.unit_g[i]:.0f}" for i in np.argsort(-r.x * m.unit_g)[:5] if r.x[i] > 1e-6)
    d = "" if base is None else f"{r.fun - base:+.2f}"
    p(f"| {label} | {r.fun:.2f} | {d} | {binding} | {top} |")
    return r.fun


p("# Sensitivity: cooking losses and absorption\n")
p("_Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources._\n")
p(f"Profile: `{lp.PROFILE}` (lp.PROFILE). Base for every row: cooked, absorbed iron (non-haem 10%), zinc 14.0 mg.\n")
p("| scenario | €/day | Δ | binding (selected) | top foods (g bought) |\n|---|---:|---:|---|---|")
raw = load(cooked=False)
b = run(raw, "base: raw NEVO values")
ck = load(cooked=True)
c = run(ck, "cooked (as usually eaten: NEVO prepared entries x yield, or USDA retention factors)", b)

p("| **absorption, varied around the cooked base** (base: zinc 14.0 mg, absorbed iron with non-haem 10%) | | | | |")
for z in (9.4, 11.7, 14.0, 16.3):
    run(ck, f"zinc PRI {z} mg (EFSA, phytate 300/600/900/1200 mg)", c, overrides={"zinc": (z, 25)})
for nh in (0.15, 0.10, 0.05):
    run(load(nonhaem=nh), f"absorbed iron, non-haem absorption {nh:.0%}", c)
run(ck, "total iron >= 11 mg instead of absorbed iron (the plain Dutch norm)", c,
    overrides={"iron_abs": ("", ""), "iron": (11, 40)})
soy = copy.deepcopy(ck); soy.N["CA"][soy.keys.index("soy_drink")] *= 0.75
run(soy, "soy-drink calcium 75% as available as milk calcium", c)
worst = load(nonhaem=0.05); worst.N["CA"][worst.keys.index("soy_drink")] *= 0.75
run(worst, "all pessimistic: zinc 16.3, non-haem 5%, soy Ca 75%", c, overrides={"zinc": (16.3, 25)})
p()
open("reports/sensitivity.md", "w").write("\n".join(out) + "\n")
