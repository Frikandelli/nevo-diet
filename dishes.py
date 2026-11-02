"""Price NEVO's dishes from their ingredients.  python3 dishes.py [--chain ah] -> dishes.md

Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources.

NEVO's recipe file lists, per dish, its ingredients as a percentage of the dish (as they go into the dish,
often already prepared: "potatoes boiled"). An ingredient can itself be a recipe; those are expanded
recursively. Each leaf ingredient is priced from the catalog:
  - a catalog food with that NEVO code: its price per 100 g edible;
  - a cooked NEVO code that is the "as eaten" partner of a catalog food (catalog_foods.nevo_cooked): the raw
    food's price / cooked grams per raw gram (yield, or raw/cooked protein for 'P'), so you buy raw;
  - free: water, herbs and spices (small amounts, see FREE);
otherwise the dish is not priceable at that chain. The dish's *nutrients* stay NEVO's own values for the dish
(unchanged NEVO data, as decided); the ingredients only give the price and what goes on the shopping list.
"""
import argparse
import csv
import re
from collections import defaultdict

NEVO_F = "data/nevo/NEVO2025_v9.0.csv"
RECIPES = "data/nevo/NEVO2025_v9.0_Recepten_Recipes.csv"
NEVO = {r["NEVO-code"]: r for r in csv.DictReader(open(NEVO_F, encoding="utf-8"), delimiter="|")}
COL = {k.split(" (")[0]: k for k in next(iter(NEVO.values())).keys()}
DISH_GROUPS = ("Mixed dishes", "Soups")
# Leaves that cost nothing worth counting: tap water, herbs, spices, flavourings (a few grams per dish).
FREE = re.compile(r"^(water|kraanwater)|kruiden|specerij|peper|kerrie|paprikapoeder|nootmuskaat|kaneel|"
                  r"knoflookpoeder|laurier|tijm|oregano|basilicum|peterselie|bieslook|dille|kurkuma|komijn|"
                  r"gember gemalen|azijn|bouillon|aroma|bakpoeder|gist|selderij blad", re.I)


def num(s):
    return float(s.replace(",", ".")) if s and s.strip() else None


def recipes():
    rec = defaultdict(list)
    for r in csv.DictReader(open(RECIPES, encoding="utf-8"), delimiter="|"):
        rec[r["NEVO-code"]].append((r["Ingr_NEVO-code"], num(r["Ingr_relatieve_hoeveelheid/Ingr_relative_amount"]) / 100))
    return rec


REC = recipes()


def catalog(chain):
    """code -> (key, €/100 g, grams bought per gram of this code). Raw codes 1:1; cooked partners via yield."""
    foods = {r["key"]: r for r in csv.DictReader(open("data/catalog_foods.tsv"), delimiter="\t")}
    price = {}
    for r in csv.DictReader(open("data/catalog_prices.tsv"), delimiter="\t"):
        if r["chain"] == chain:
            price[r["key"]] = float(r["eur_per_100g"])
    out = {}
    for k, f in foods.items():
        if k not in price:
            continue
        cand = [(f["nevo"], 1.0)]
        if f["nevo_cooked"]:
            if f["yield"] == "P":
                y = num(NEVO[f["nevo"]][COL["PROT"]]) / num(NEVO[f["nevo_cooked"]][COL["PROT"]])
            else:
                y = float(f["yield"] or 1)
            cand.append((f["nevo_cooked"], 1 / y))       # buy 1/y g raw per g cooked
        for code, per in cand:
            c = price[k] * per
            if code not in out or c < out[code][1]:
                out[code] = (k, c, per)
    return out


DUTCH = {c: r[COL["Voedingsmiddelnaam/Dutch food name"]] for c, r in NEVO.items()}
BY_DUTCH = {v: c for c, v in DUTCH.items()}
COOKED_WORD = re.compile(r"\s*\b(gekookt|gebakken|gestoofd|gegrild|gesmoord|bereid|gaar|gestoomd)\b.*$")
YIELD_GROUPS = ("Cereal products and types of flour", "Legumes", "Meat and poultry", "Fish, crustacean and shellfish",
                "Potatoes and tubers")
MINOR = 0.015          # an unpriceable leaf under 1.5% of the dish is left out (and reported)


def cooked_to_raw(code):
    """(raw code, raw grams per cooked gram) for a cooked NEVO entry, by name: "Ui gekookt" -> "Ui rauw"."""
    base = COOKED_WORD.sub("", DUTCH.get(code, ""))
    if base == DUTCH.get(code, ""):
        return None
    for cand in (base + " rauw", base + " gedroogd", base):
        rc = BY_DUTCH.get(cand)
        if rc and rc != code:
            per = 1.0
            if NEVO[code]["Food group"] in YIELD_GROUPS:
                pr, pc = num(NEVO[rc][COL["PROT"]]), num(NEVO[code][COL["PROT"]])
                per = pc / pr if pr and pc else 1.0            # raw g per cooked g
            return rc, per
    return None


STATE_WORDS = {"rauw", "gekookt", "gebakken", "bereid", "gem", "onbereid", "gedroogd", "blik", "glas", "blik/glas",
               "diepvries", "vers", "m", "z", "w", "wo", "en", "of", "in"}


def tokens(name):
    return {t.rstrip("-s") for t in re.split(r"[\s/,()-]+", name.lower()) if t and t not in STATE_WORDS}


ANIMAL_PREFIX = (("runder", "rund"), ("varkens", "varkens"), ("kip", "kip"), ("kalkoen", "kalkoen"),
                 ("lams", "lams"), ("kalfs", "kalfs"))


def head(name):
    return re.split(r"[\s/,()-]+", name.lower())[0].rstrip("-")


def substitute(code, cat):
    """A price proxy for an ingredient the chain doesn't sell as such (the dish's nutrients stay NEVO's):
    1) same NEVO food group and same head noun (first word) and another shared word -> the closest name;
    2) same group and head noun only -> the median-priced one of that family;
    3) meat cuts: the same animal (runder-, varkens-, kip ...) -> median-priced of that animal.
    Returns (code, how) or None."""
    import difflib
    name, grp = DUTCH.get(code, ""), NEVO.get(code, {}).get("Food group")
    if grp is None:
        return None
    hd, tk = head(name), tokens(name)
    fam = [c for c in cat if c in NEVO and NEVO[c]["Food group"] == grp and head(DUTCH[c]) == hd]
    if not fam and grp == "Meat and poultry":
        for pre, want in ANIMAL_PREFIX:
            if name.lower().startswith(pre):
                fam = [c for c in cat if c in NEVO and NEVO[c]["Food group"] == grp
                       and DUTCH[c].lower().startswith(want)]
                break
    if not fam:
        return None
    close = [c for c in fam if len(tk & tokens(DUTCH[c])) >= 2]
    if close:
        return max(close, key=lambda c: difflib.SequenceMatcher(None, name, DUTCH[c]).ratio()), "close"
    fam.sort(key=lambda c: cat[c][1])
    if grp == "Fats and oils":
        return fam[0], "cheapest of the family"          # any cooking oil or fat will do
    return fam[len(fam) // 2], "family median"


def veg_median(cat):
    p = sorted(v[1] for c, v in cat.items() if c in NEVO and NEVO[c]["Food group"] == "Vegetables" and v[2] == 1.0)
    return p[len(p) // 2] if p else None


def expand(code, share, cat, leaves, missing, subs, depth=0):
    """Add the dish's leaf ingredients (key -> grams bought per gram of dish) into `leaves`."""
    name = DUTCH.get(code, code)
    if code in cat:
        k, _, per = cat[code]
        leaves[k] += share * per
        return
    if FREE.search(name):
        return
    if code in REC and depth < 4:
        for ing, s in REC[code]:
            expand(ing, share * s, cat, leaves, missing, subs, depth + 1)
        return
    raw = cooked_to_raw(code)
    if raw and (raw[0] in cat or raw[0] in REC):
        expand(raw[0], share * raw[1], cat, leaves, missing, subs, depth + 1)
        return
    alt = substitute(raw[0] if raw else code, cat)
    if alt:
        subs[name] = f"{DUTCH[alt[0]]} ({alt[1]})"
        k, _, per = cat[alt[0]]
        leaves[k] += share * (raw[1] if raw else 1.0) * per
        return
    if NEVO.get(code, {}).get("Food group") == "Vegetables" and veg_median(cat):
        subs[name] = "median vegetable price (sold per piece only)"
        leaves["_veg_median"] += share
        return
    missing[name] += share


def price_dish(code, cat):
    """(€ per 100 g dish or None, leaves {key: g bought per g dish}, missing {ingredient: share}, subs, minor)."""
    leaves, missing, subs = defaultdict(float), defaultdict(float), {}
    for ing, s in REC[code]:
        expand(ing, s, cat, leaves, missing, subs)
    minor = {k: v for k, v in missing.items() if v < MINOR}
    if sum(missing.values()) - sum(minor.values()) > 1e-9:
        return None, dict(leaves), dict(missing), subs, minor
    price = {k: c / per for k, c, per in cat.values()}            # €/100 g bought of each key
    price["_veg_median"] = veg_median(cat)
    return sum(g * price[k] for k, g in leaves.items()), dict(leaves), {}, subs, minor


def dishes():
    return [c for c in REC if NEVO[c]["Food group"] in DISH_GROUPS]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chain", default="ah")
    a = ap.parse_args()
    from collections import Counter
    chains = sorted({r["chain"] for r in csv.DictReader(open("data/catalog_prices.tsv"), delimiter="\t")})
    out = ["# NEVO dishes priced from their ingredients\n",
           "_Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources._\n",
           f"{len(dishes())} dishes (NEVO groups Mixed dishes and Soups). A dish counts at a chain when every "
           "ingredient maps to a product sold there (water, herbs and spices free).\n",
           "| chain | priceable dishes |\n|---|---:|"]
    miss_all = Counter()
    for ch in chains:
        cat = catalog(ch)
        n = 0
        for d in dishes():
            p, _, miss, *_ = price_dish(d, cat)
            n += p is not None
            if ch == a.chain:
                for k in miss:
                    miss_all[k] += 1
        out.append(f"| {ch} | {n} |")
    cat = catalog(a.chain)
    out += [f"\n## Dishes at {a.chain}\n", "| dish | €/100 g | kcal/100 g | protein g | € per 500 kcal |",
            "|---|---:|---:|---:|---:|"]
    rows = []
    for d in dishes():
        p, leaves, miss, subs, minor = price_dish(d, cat)
        if p is None:
            continue
        kcal = num(NEVO[d][COL["ENERCC"]]) or 0
        rows.append((500 * p / kcal if kcal else 99, d, p, kcal, num(NEVO[d][COL["PROT"]]) or 0))
    for per500, d, p, kcal, prot in sorted(rows):
        out.append(f"| {NEVO[d]['Engelse naam/Food name'][:50]} ({d}) | {p:.3f} | {kcal:.0f} | {prot:.1f} | {per500:.2f} |")
    out += [f"\n## Ingredients that block the most dishes at {a.chain}\n", "| ingredient | dishes |", "|---|---:|"]
    out += [f"| {k} | {v} |" for k, v in miss_all.most_common(25)]
    open("dishes.md", "w").write("\n".join(out) + "\n")
    print("\n".join(out[:20]))


if __name__ == "__main__":
    main()
