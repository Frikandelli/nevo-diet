"""Kinds of food, for leaving out a whole kind at once: wheat flour, pasta and noodles, rice, oily fish, cabbages ...

Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources.

Finer than the category ticks in categories.py ("no grain products" takes out flour, pasta, rice, oats and bread at
once; "no pasta and noodles" only the pasta). Every catalog food has exactly one kind, from the first rule in
data/kinds.tsv whose `group` (the food's group in the catalog, `|` for several) and `match` (a regex on its NEVO English
name) fit; a food no rule fits gets "other <group>". Leaving out a kind is the same as a ✗ on each of its foods: in the
realistic week the dinners with one of them as an ingredient go too, as with a ✗. This is a grouping for the app's
ticks only; no nutrient value depends on it.
"""
import csv
import re

import supplements as S

RULES = [(r["kind"], set(r["group"].split("|")), re.compile(r["match"]))
         for r in csv.DictReader(open("data/kinds.tsv", encoding="utf-8"), delimiter="\t")]
_FOODS = list(csv.DictReader(open("data/catalog_foods.tsv", encoding="utf-8"), delimiter="\t"))


def kind_of(name, group):
    for kind, groups, rx in RULES:
        if group in groups and rx.search(name):
            return kind
    return f"other {group}"


KIND = {f["key"]: kind_of(f["name"], f["group"]) for f in _FOODS}
KIND.update({k: "supplements" for k in S.SUPP})       # every supplement: the Supplements page
# In the order of the rules file (it goes roughly through the shop), then anything else.
KINDS = list(dict.fromkeys([k for k, _, _ in RULES if k in set(KIND.values())] + sorted(set(KIND.values()))))
COUNT = {k: sum(v == k for v in KIND.values()) for k in KINDS}


def members(kinds):
    """The foods of these kinds."""
    kinds = set(kinds)
    return {k for k, v in KIND.items() if v in kinds}


def removed_by(kinds):
    """{food: its kind} for the foods these kinds leave out."""
    kinds = set(kinds)
    return {k: v for k, v in KIND.items() if v in kinds}


if __name__ == "__main__":
    for k in KINDS:
        names = [f["name"] for f in _FOODS if KIND[f["key"]] == k]
        print(f"{k:36} {COUNT[k]:3}  {'; '.join(names[:6])}{' ...' if len(names) > 6 else ''}")
