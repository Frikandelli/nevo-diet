"""Which foods are cooked, and what cooking does to them. Used by lp.load.

Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources.

Every food gets a default from the first rule in data/cooking.tsv whose `match` (a regex on the NEVO name of the food as
bought) and `group` fit:
  must     cooked by default; counting it raw gets a warning in the app (raw meat, frozen vegetables, dried pulses ...);
  usual    cooked by default, fine raw too (Brussels sprouts, kale, onions ...);
  raw      raw by default, can be cooked (tomatoes, oat flakes ...);
  as_sold  no choice: NEVO's values already describe the food as eaten (tinned, smoked, bread, cheese ...).
A food no rule matches is `usual` if it has a cooked NEVO partner, else `as_sold`.

What "cooked" means for a food, in this order:
  1. its cooked NEVO partner (catalog_foods.nevo_cooked) x the yield, as before;
  2. otherwise its raw NEVO values x the USDA retention factor of the rule's `usda` class (data/retention.tsv), per
     nutrient; nutrients USDA gives no factor for (protein, fat, fibre, vitamins D, E and K, iodine, selenium, amino
     acids) are kept at 100%;
  3. otherwise (no partner, no class) the raw values: the food is still counted as cooked, without a change.
A retention factor is the share of the nutrient in the food as bought that is still there once it's cooked, so it
applies per gram bought, with no yield needed: x stays in grams as bought. The USDA classes are "boiled" or "simmered"
wherever USDA has one (model rule, DESIGN.md: cooking means boiling).

    python3 cooking.py /path/to/retn06.txt    rebuilds data/retention.tsv from USDA's file (only the classes used)
"""
import csv
import re
import sys
from functools import lru_cache
from types import SimpleNamespace

SOURCE = "USDA Table of Nutrient Retention Factors, Release 6 (2007), retn06.txt"
# USDA nutrient number -> NEVO columns. Haem iron follows iron, retinol follows vitamin A, niacin equivalents follow
# niacin (the tryptophan part isn't lost, so that is cautious).
USDA_TO_NEVO = {"301": ["CA"], "303": ["FE", "HAEM"], "304": ["MG"], "305": ["P"], "306": ["K"], "307": ["NA"],
                "309": ["ZN"], "312": ["CU"], "392": ["VITA_RAE", "RETOL"], "401": ["VITC"], "404": ["THIA"],
                "405": ["RIBF"], "406": ["NIAEQ"], "415": ["VITB6"], "417": ["FOL"], "431": ["FOLAC"],
                "418": ["VITB12"]}
DEFAULTS = ("must", "usual", "raw", "as_sold")


@lru_cache(maxsize=1)
def rules():
    out = list(csv.DictReader(open("data/cooking.tsv"), delimiter="\t"))
    for r in out:
        assert r["default"] in DEFAULTS, r
    return out


@lru_cache(maxsize=1)
def retention():
    """{usda class: {NEVO column: factor (0-1)}}"""
    out = {}
    for r in csv.DictReader(open("data/retention.tsv"), delimiter="\t"):
        out.setdefault(r["usda"], {})[r["nevo_col"]] = float(r["factor"])
    return out


def info(name, group, has_partner):
    """How one food is cooked: default (must/usual/raw/as_sold), usda class, cookable, why."""
    for r in rules():
        if re.search(r["match"], name, re.I) and (not r["group"] or re.fullmatch(r["group"], group)):
            d, usda, why = r["default"], r["usda"], r["why"]
            break
    else:
        d, usda, why = ("usual" if has_partner else "as_sold"), "", ""
    if d == "as_sold" and has_partner:
        d = "usual"
    cookable = d != "as_sold" and bool(has_partner or usda or d == "must")
    return SimpleNamespace(default=d, usda=usda if not has_partner else "", cookable=cookable, why=why,
                           ticked=cookable and d in ("must", "usual"))


def cooked_keys(how, flip=()):
    """The keys counted as cooked: the default ticks, with the keys in `flip` turned the other way.
    how: {key: info(...)}. A flip on a food that can't be cooked does nothing."""
    return {k for k, i in how.items() if i.cookable and i.ticked != (k in flip)}


def build(retn06):
    """data/retention.tsv from USDA's retn06.txt: the classes data/cooking.tsv uses, the nutrients lp.py reads."""
    used = {r["usda"] for r in rules() if r["usda"]}
    rows = []
    for line in open(retn06, encoding="latin-1"):
        f = [x.strip("~") for x in line.rstrip("\r\n").split("^")]
        code, name, nut, factor = f[0], f[2], f[3], f[5]
        if code in used and nut in USDA_TO_NEVO:
            for col in USDA_TO_NEVO[nut]:
                rows.append({"usda": code, "usda_name": name, "nevo_col": col, "factor": int(factor) / 100,
                             "source": SOURCE})
    missing = used - {r["usda"] for r in rows}
    assert not missing, f"not in {retn06}: {missing}"
    with open("data/retention.tsv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"data/retention.tsv: {len(used)} classes, {len(rows)} factors")


if __name__ == "__main__":
    build(sys.argv[1])
