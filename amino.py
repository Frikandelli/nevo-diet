"""Essential amino acids per catalog food, from USDA FoodData Central SR Legacy (public domain).

python3 amino.py  ->  data/amino_foods.tsv (committed), data/amino_families.tsv, and a check printed to stdout.

NEVO has only tryptophan. Amino acids per gram of protein are fairly stable within a kind of food (cereal
protein is low in lysine, legume protein low in methionine), so each catalog food gets the median USDA profile
of its *family* (oats, rice, wheat, legumes, soy, dairy, ...), in mg amino acid per g protein. lp.load()
multiplies that by the food's NEVO protein (cooked or raw), so amounts follow NEVO's protein values.

Setup: download https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_csv_2018-04.zip and
unzip it into data/usda/ (not in git; only the derived tables are).
"""
import csv
import re
import statistics as st
from collections import defaultdict

USDA = "data/usda/FoodData_Central_sr_legacy_food_csv_2018-04/"
# USDA nutrient ids -> our names. Met+Cys and Phe+Tyr are summed, as in the WHO 2007 requirements.
AA_IDS = {1221: "HIS", 1212: "ILE", 1213: "LEU", 1214: "LYS", 1215: "MET", 1216: "CYS", 1217: "PHE",
          1218: "TYR", 1211: "THR", 1210: "TRP", 1219: "VAL"}
AAS = ["HIS", "ILE", "LEU", "LYS", "SAA", "AAA", "THR", "TRP", "VAL"]

# Digestibility discount on amino acids (model decision, DESIGN.md): ~5% animal, ~15% plant protein.
ANIMAL = {"dairy", "egg", "meat", "fish"}
DIGEST = {True: 0.95, False: 0.85}

# family: (USDA category ids, regex on the USDA description). Profile = median over those USDA foods.
FAMILIES = {
    "soy":       ({16}, r"^(Soybeans|Tofu|Tempeh|Soymilk|Soy flour)"),
    "peanut":    ({16}, r"^Peanut"),
    "legume":    ({16}, r"^(Beans|Lentils|Peas|Chickpeas|Lupins|Broadbeans|Cowpeas|Hummus|Falafel)"),
    "oats":      ({8, 20}, r"^(Oat|Cereals, oats)"),
    "rice":      ({20}, r"^Rice"),
    "maize":     ({20}, r"^(Corn|Cornmeal)"),
    "rye":       ({20}, r"^Rye"),
    "barley":    ({20}, r"^Barley"),
    "buckwheat": ({20}, r"^Buckwheat"),
    "quinoa":    ({20}, r"^Quinoa"),
    "millet":    ({20}, r"^Millet"),
    "spelt":     ({20}, r"^Spelt"),
    "wheat":     ({18, 20}, r"^(Wheat flour|Wheat, |Bulgur|Couscous|Semolina|Pasta|Spaghetti|Macaroni|"
                            r"Bread, (white|whole-wheat|wheat))"),
    "potato":    ({11}, r"^Potato"),
    "sweet_potato": ({11}, r"^Sweet potato"),
    "cassava":   ({11}, r"^Cassava"),
    "vegetable": ({11}, r"^(?!Potato|Sweet potato|Cassava|Soybeans|Peas and|Beans)"),
    "fruit":     ({9}, r""),
    "nut":       ({12}, r""),
    "coconut":   ({12}, r"^Nuts, coconut"),
    "dairy":     ({1}, r"^(?!Egg)"),
    "egg":       ({1}, r"^Egg"),
    "meat":      ({5, 7, 10, 13, 17}, r""),
    "fish":      ({15}, r""),
    "yeast":     ({18}, r"[Yy]east"),
    "cocoa":     ({19}, r"(Cocoa|[Cc]hocolate)"),
    "mixed":     (set(range(1, 21)), r""),     # fallback: every USDA food
}

# catalog food -> family: first matching rule on (catalog group, NEVO English name). Order matters.
RULES = [
    (None, r"soy|soya|tofu|tempeh"), ("soy", None),
    (None, r"peanut"), ("peanut", None),
    (None, r"seitan"), ("wheat", None),   # USDA vital wheat gluten has no amino acid data
    (None, r"\boat|^muesli"), ("oats", None),
    (None, r"^rice|rice drink|drink rice|rice cake|flour rice"), ("rice", None),
    (None, r"\bcorn\b|maize|polenta"), ("maize", None),
    (None, r"\brye\b"), ("rye", None),
    (None, r"barley"), ("barley", None),
    (None, r"buckwheat"), ("buckwheat", None),
    (None, r"quinoa"), ("quinoa", None),
    (None, r"millet"), ("millet", None),
    (None, r"spelt"), ("spelt", None),
    (None, r"coconut"), ("coconut", None),
    (None, r"almond|hazelnut|cashew"), ("nut", None),
    (None, r"potato sweet"), ("sweet_potato", None),
    (None, r"cassava"), ("cassava", None),
    (None, r"yeast"), ("yeast", None),
    ("sweet", r"chocolate|cocoa|choc"), ("cocoa", None),
    (None, r"hummus|falafel|lupin|^beans|^peas|^lentils|^pulses"), ("legume", None),
    ("legume", None), ("legume", None),
    ("egg", None), ("egg", None),
    (None, r"^salad egg"), ("egg", None),
    ("dairy", None), ("dairy", None), ("cheese", None), ("dairy", None),
    ("meat", None), ("meat", None), ("coldcut", None), ("meat", None), ("snack", None), ("meat", None),
    (None, r"^salad (chicken|meat)"), ("meat", None),
    ("fish", None), ("fish", None), (None, r"^salad (fish|salmon|tuna|crab|shrimp)"), ("fish", None),
    ("grain", None), ("wheat", None), ("bread", None), ("wheat", None),
    ("potato", None), ("potato", None),
    ("veg", None), ("vegetable", None),
    ("fruit", None), ("fruit", None), ("drink", None), ("fruit", None),
    ("nut", None), ("nut", None),
]
RULES = list(zip(RULES[0::2], (fam for fam, _ in RULES[1::2])))


def family_of(group, name):
    for (g, rx), fam in RULES:
        if (g is None or g == group) and (rx is None or re.search(rx, name, re.I)):
            return fam
    return "mixed"


def usda_profiles():
    """{fdc_id: (description, category, {aa: mg per g protein})} for USDA foods with protein >= 1 g/100 g."""
    foods = {r["fdc_id"]: (r["description"], int(r["food_category_id"] or 0))
             for r in csv.DictReader(open(USDA + "food.csv", encoding="utf-8"))}
    want = set(AA_IDS) | {1003}
    val = defaultdict(dict)
    for r in csv.DictReader(open(USDA + "food_nutrient.csv", encoding="utf-8")):
        nid = int(r["nutrient_id"])
        if nid in want:
            val[r["fdc_id"]][nid] = float(r["amount"])
    # Some foods (rye grain) lack cystine: impute it from methionine with the median Cys/Met ratio of
    # complete foods in the same USDA category.
    ratio = defaultdict(list)
    for fid, v in val.items():
        if v.get(1003, 0) >= 1 and all(i in v for i in AA_IDS) and v[1215] > 0:
            ratio[foods[fid][1]].append(v[1216] / v[1215])
    out = {}
    for fid, v in val.items():
        prot = v.get(1003, 0)
        if prot < 1 or not all(i in v for i in AA_IDS if i != 1216):
            continue
        if 1216 not in v:
            if not ratio[foods[fid][1]]:
                continue
            v = {**v, 1216: v[1215] * st.median(ratio[foods[fid][1]])}
        g = {AA_IDS[i]: 1000 * v[i] / prot for i in AA_IDS}       # g/100 g -> mg per g protein
        prof = {"HIS": g["HIS"], "ILE": g["ILE"], "LEU": g["LEU"], "LYS": g["LYS"], "SAA": g["MET"] + g["CYS"],
                "AAA": g["PHE"] + g["TYR"], "THR": g["THR"], "TRP": g["TRP"], "VAL": g["VAL"]}
        out[fid] = (*foods[fid], prof)
    return out


def main():
    usda = usda_profiles()
    fams = {}
    with open("data/amino_families.tsv", "w") as f:
        f.write("family\tn_usda\t" + "\t".join(f"{a}_mg_per_g_prot" for a in AAS) + "\t"
                + "\t".join(f"{a}_cv" for a in AAS) + "\texamples\n")
        for fam, (cats, rx) in FAMILIES.items():
            members = [p for d, c, p in usda.values() if c in cats and re.search(rx, d)]
            names = [d for d, c, p in usda.values() if c in cats and re.search(rx, d)]
            if not members:
                raise SystemExit(f"family {fam}: no USDA foods match")
            med = {a: st.median(p[a] for p in members) for a in AAS}
            cv = {a: (st.pstdev(p[a] for p in members) / st.mean(p[a] for p in members)) for a in AAS}
            fams[fam] = med
            f.write(f"{fam}\t{len(members)}\t" + "\t".join(f"{med[a]:.1f}" for a in AAS) + "\t"
                    + "\t".join(f"{cv[a]:.2f}" for a in AAS) + "\t" + "; ".join(names[:3]) + "\n")

    nevo = {r["NEVO-code"]: r for r in csv.DictReader(open("data/nevo/NEVO2025_v9.0.csv", encoding="utf-8"),
                                                     delimiter="|")}
    col = {k.split(" (")[0]: k for k in next(iter(nevo.values())).keys()}
    num = lambda s: float(s.replace(",", ".")) if s.strip() else None
    check = []
    with open("data/amino_foods.tsv", "w") as f:
        f.write("key\tfamily\tdigestibility\t" + "\t".join(f"{a}_mg_per_g_prot" for a in AAS) + "\n")
        for r in csv.DictReader(open("data/catalog_foods.tsv"), delimiter="\t"):
            name = nevo[r["nevo"]][col["Engelse naam/Food name"]]
            fam = family_of(r["group"], name)
            dig = DIGEST[fam in ANIMAL]
            f.write(f"{r['key']}\t{fam}\t{dig}\t" + "\t".join(f"{fams[fam][a]:.1f}" for a in AAS) + "\n")
            prot, trp = num(nevo[r["nevo"]][col["PROT"]]), num(nevo[r["nevo"]][col["TRP"]])
            if prot and prot >= 2 and trp:
                check.append((1000 * trp / 1000 / prot, fams[fam]["TRP"], fam, name))  # NEVO TRP is mg/100 g

    # Check: NEVO's own tryptophan per g protein against the family profile.
    by = defaultdict(list)
    for nv, us, fam, name in check:
        by[fam].append(nv / us)
    print("Tryptophan check: NEVO mg TRP per g protein / USDA family median (1.00 = same)")
    print(f"{'family':12} {'n':>4} {'median':>7} {'p10':>6} {'p90':>6}")
    for fam, rs in sorted(by.items(), key=lambda t: -len(t[1])):
        rs.sort()
        print(f"{fam:12} {len(rs):4} {st.median(rs):7.2f} {rs[len(rs)//10]:6.2f} {rs[9*len(rs)//10]:6.2f}")
    allr = sorted(nv / us for nv, us, *_ in check)
    print(f"{'all':12} {len(allr):4} {st.median(allr):7.2f} {allr[len(allr)//10]:6.2f} {allr[9*len(allr)//10]:6.2f}")
    worst = sorted(check, key=lambda t: abs(t[0] / t[1] - 1), reverse=True)[:8]
    print("Largest differences:", "; ".join(f"{n[:28]} ({fa}) {a / b:.2f}" for a, b, fa, n in worst))


if __name__ == "__main__":
    main()
