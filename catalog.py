"""Merge the hand-mapped foods (data/foods.tsv) and the auto-matched ones (expand.py) into one catalog with a
price per food per chain.

    python3 catalog.py   -> data/catalog_foods.tsv, data/catalog_prices.tsv

Hand-mapped foods win when both map to the same NEVO code. Auto foods get a cooked counterpart (raw chicken ->
'Kip ... bereid', dried lentils -> 'gekookt') so the default 'as eaten' composition works for them too.
"""
import csv, json, re
from collections import defaultdict

from price import cheapest
from snapshot import latest_snapshot

NEVO = "data/nevo/NEVO2025_v9.0.csv"
GROUP = {"Vegetables": "veg", "Fruits": "fruit", "Legumes": "legume", "Cereal products and types of flour": "grain",
         "Bread": "bread", "Potatoes and tubers": "potato", "Milk and milk products": "dairy", "Cheese": "cheese",
         "Eggs": "egg", "Fish, crustacean and shellfish": "fish", "Meat and poultry": "meat",
         "Cold meat cuts": "coldcut", "Fats and oils": "fat", "Nuts and seeds": "nut",
         "Meat substitutes and dairy substitutes": "meat_sub", "Savoury bread spreads": "spread",
         "Sugar, sweets and sweet sauces": "sweet", "Non-alcoholic beverages": "drink", "Miscellaneous foods": "misc"}
COOKED_GROUPS = {"grain", "legume", "meat", "fish", "potato", "veg", "egg"}
RAW_OK = re.compile(r"^(sla|tomaat|komkommer|paprika|radijs|rauwkost|tauge|avocado|olijven|augurk|kappertjes|"
                    r"waterkers|rucola|veldsla|ijsbergsla|kers|bieslook|peterselie|basilicum|munt)", re.I)
PREP_ORDER = ["gekookt", "bereid", "gebakken", "gegrild", "gestoomd", "gestoofd"]


def num(s):
    return float(s.replace(",", ".")) if s.strip() else None


def cooked_partner(row, by_name):
    """NEVO 'as eaten' entry for a raw/dried food: same name with the state word swapped."""
    name = row["Voedingsmiddelnaam/Dutch food name"]
    m = re.search(r"\b(rauw|onbereid|gedroogd)\b", name)
    if not m:
        return None
    base = (name[: m.start()] + name[m.end():]).strip()
    for prep in PREP_ORDER:
        for cand in (f"{base} {prep}", f"{name[: m.start()]}{prep}{name[m.end():]}".strip()):
            if cand in by_name:
                return by_name[cand]
    return None


def protein_yield(raw, cooked, group):
    """Cooked weight per raw weight from protein conservation, clamped to plausible kitchen yields."""
    pr, pc = num(raw["PROT (g)"]), num(cooked["PROT (g)"])
    lo, hi, default = {"grain": (1.8, 3.2, 2.5), "legume": (1.8, 3.2, 2.4), "meat": (0.6, 0.95, 0.75),
                       "fish": (0.65, 1.0, 0.85), "egg": (0.95, 1.05, 1.0)}.get(group, (0.85, 1.1, 1.0))
    if group in ("veg", "potato"):
        return 1.0                       # protein is too noisy in vegetables (see FINDINGS.md)
    if pr and pc and lo <= pr / pc <= hi:
        return round(pr / pc, 3)
    return default


def main():
    nevo = {r["NEVO-code"]: r for r in csv.DictReader(open(NEVO, encoding="utf-8"), delimiter="|")}
    by_name = {r["Voedingsmiddelnaam/Dutch food name"]: r for r in nevo.values()}
    stores = json.load(open(latest_snapshot()))
    chains = [s["n"] for s in stores if s["d"]]

    foods, prices = [], []
    auto = defaultdict(dict)
    for r in csv.DictReader(open("data/auto_prices.tsv"), delimiter="\t"):
        auto[r["nevo"]][r["chain"]] = r

    # 1) hand-mapped foods, priced per chain with their own regexes; chains where only the automatic matcher
    #    found the same NEVO food count too (the hand regexes only fit some chains' naming)
    curated = list(csv.DictReader(open("data/foods.tsv"), delimiter="\t"))
    by_chain = {ch: cheapest(curated, [(s["n"], p) for s in stores if s["n"] == ch for p in s["d"]]) for ch in chains}
    for f in curated:
        for ch, m in auto.get(f["nevo"], {}).items():
            own = by_chain[ch].get(f["key"])
            if not own or float(m["eur_per_100g"]) < own[0][0]:
                # auto price used its own edible factor (incl. 0.6 drained for canned); re-base it on the hand
                # food's, which for canned foods is edible x 0.6 too (price.py). Before 2026-11-01 the 0.6 was
                # missing here, so auto prices for canned hand foods came out 40% too cheap.
                hand_ed = float(f["edible"]) * (0.6 if f.get("canned") == "1" else 1.0)
                ed = hand_ed / float(m["edible"] or 1)
                by_chain[ch][f["key"]] = [(float(m["eur_per_100g"]) / ed, ch, float(m["pack_eur"]),
                                           float(m["pack_g"]), m["product"], "")]
        sold = [ch for ch in chains if f["key"] in by_chain[ch]]
        foods.append({"key": f["key"], "nevo": f["nevo"], "name": nevo[f["nevo"]]["Engelse naam/Food name"],
                      "group": f["group"], "nevo_cooked": f["nevo_cooked"], "yield": f["yield"],
                      "source": "hand", "n_chains": len(sold), "chains": ",".join(sold)})
        for ch in sold:
            c = by_chain[ch][f["key"]][0]
            prices.append({"key": f["key"], "chain": ch, "eur_per_100g": round(c[0], 4), "product": c[4],
                           "pack_eur": c[2], "pack_g": round(c[3])})
    hand_codes = {f["nevo"] for f in curated}

    # 2) auto-matched foods
    for code, per_chain in sorted(auto.items()):
        if code in hand_codes:
            continue
        row = nevo[code]
        g = GROUP[row["Food group"]]
        key = "n" + code
        ck, y = "", ""
        if g in COOKED_GROUPS and not RAW_OK.search(row["Voedingsmiddelnaam/Dutch food name"]):
            partner = cooked_partner(row, by_name)
            if partner:
                ck, y = partner["NEVO-code"], protein_yield(row, partner, g)
        foods.append({"key": key, "nevo": code, "name": row["Engelse naam/Food name"], "group": g,
                      "nevo_cooked": ck, "yield": y, "source": "auto",
                      "n_chains": len(per_chain), "chains": ",".join(sorted(per_chain))})
        for ch, m in per_chain.items():
            prices.append({"key": key, "chain": ch, "eur_per_100g": m["eur_per_100g"], "product": m["product"],
                           "pack_eur": m["pack_eur"], "pack_g": m["pack_g"]})

    for path, rows in (("data/catalog_foods.tsv", foods), ("data/catalog_prices.tsv", prices)):
        with open(path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
            w.writeheader(); w.writerows(rows)
    # Which price snapshot the catalog is built from: the snapshot itself isn't in git, so without this a clone can't
    # tell how old its prices are (the app's Data and Settings pages show it).
    with open("data/catalog_snapshot.txt", "w") as fh:
        fh.write(latest_snapshot().split("/")[-1] + "\n")
    n_cooked = sum(1 for f in foods if f["nevo_cooked"])
    print(f"{len(foods)} foods ({len(curated)} hand, {len(foods) - len(curated)} auto), {n_cooked} with a cooked "
          f"entry; {len(prices)} food x chain prices; {sum(f['n_chains'] >= 3 for f in foods)} sold at >= 3 chains")


if __name__ == "__main__":
    main()
