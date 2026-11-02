"""Compare the profiles across chains.  python3 compare.py -> profiles.md

Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources.
"""
import csv

import numpy as np

from lp import load, solve
from profiles import all_profiles, load_profile

NEVO_EN = {r["NEVO-code"]: r["Engelse naam/Food name"] for r in
           csv.DictReader(open("data/nevo/NEVO2025_v9.0.csv", encoding="utf-8"), delimiter="|")}
FOODS = {r["key"]: r for r in csv.DictReader(open("data/catalog_foods.tsv"), delimiter="\t")}
CHAINS = sorted({r["chain"] for r in csv.DictReader(open("data/catalog_prices.tsv"), delimiter="\t")})
# Nutrients reported as "binding"; energy/fat-type rows bind almost always and say little.
SKIP = {"energy"}


def label(k):
    f = FOODS.get(k)
    return k if not f or f["source"] == "hand" else NEVO_EN[f["nevo"]][:26]


out = []
def p(s=""):
    print(s); out.append(s)


def summary(m, r, G, h, lab):
    sl = h - G @ r.x
    binding = [n for j, (n, s) in enumerate(lab) if sl[j] < 1e-7 and n not in SKIP]
    grams = r.x * np.where(m.unit_g > 0, m.unit_g, 0)
    top = [f"{label(m.keys[i])} {grams[i]:.0f} g" for i in np.argsort(-r.x * m.c)[:4] if r.x[i] > 1e-6]
    return binding, top


p("# Five profiles compared\n")
p("_Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources "
  "(Checkjebon prices 2026-10-30)._\n")
p("Cooked composition, absorbed iron (haem 25%, non-haem 10%), zinc at EFSA's high-phytate level, "
  "WHO 2007 amino acids. Details per profile in `reports/<profile>.md`.\n")
p("## Profiles\n")
p("| profile | sex | age | weight kg | kcal | protein g | source |\n|---|---|---:|---:|---:|---:|---|")
for n in all_profiles():
    pr = load_profile(n)
    p(f"| {pr['label']} | {pr['sex']} | {pr['age']} | {pr['weight']:.1f} | {pr['energy']:.0f} | {pr['protein']:.0f} "
      f"| {pr['source']} |")

p("\n## Cost per day (€), cheapest product per food at that chain\n")
p("`best` = cheapest chain for every food (shopping everywhere). Blank = infeasible at that chain.\n")
p("| profile | best | " + " | ".join(CHAINS) + " |\n|---|---:|" + "---:|" * len(CHAINS))
details = {}
for n in all_profiles():
    cells = []
    m = load(profile=n)
    r, G, h, lab = solve(m)
    details[n] = (r.fun, *summary(m, r, G, h, lab))
    cells.append(f"**{r.fun:.2f}**")
    for ch in CHAINS:
        mc = load(profile=n, chain=ch)
        rc, *_ = solve(mc)
        cells.append(f"{rc.fun:.2f}" if rc.status == 0 else "")
    p(f"| {load_profile(n)['label']} | " + " | ".join(cells) + " |")

p("\n## What binds and what's in the basket (best prices)\n")
p("| profile | €/day | binding requirements | biggest costs |\n|---|---:|---|---|")
for n, (cost, binding, top) in details.items():
    p(f"| {load_profile(n)['label']} | {cost:.2f} | {', '.join(binding)} | {', '.join(top)} |")
p()
open("profiles.md", "w").write("\n".join(out) + "\n")
