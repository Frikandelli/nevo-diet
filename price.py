"""Match each food in data/foods.tsv to supermarket products (Checkjebon data) and
write data/prices.tsv with the cheapest price per 100 g *edible* portion.

Usage: python3 price.py [--chain ah] [--show 3]
"""
import argparse, csv, json, re

from snapshot import latest_snapshot

UNIT_G = {"g": 1, "gr": 1, "gram": 1, "grm": 1, "kg": 1000, "kilo": 1000, "kilogram": 1000,
          "ml": 1, "milliliter": 1, "mililiters": 1, "cl": 10, "centiliter": 10, "l": 1000, "liter": 1000}
NUM = r"(\d+(?:[.,]\d+)?)"
UNIT = r"(kilogram|kilo|kg|gram|grm|gr|g|milliliter|mililiters|ml|centiliter|cl|liter|l)\b"


def parse_grams(size, name, piece_g):
    """Pack weight in grams (ml counted as g), or None if it can't be determined."""
    for text in (size or "", name):
        t = text.lower().replace("•", " ")
        m = re.search(NUM + r"\s*x\s*" + NUM + r"\s*" + UNIT, t)
        if m:
            return float(m[1].replace(",", ".")) * float(m[2].replace(",", ".")) * UNIT_G[m[3]]
        m = re.search(NUM + r"\s*" + UNIT, t)
        if m:
            return float(m[1].replace(",", ".")) * UNIT_G[m[2]]
        if piece_g:
            m = re.search(r"(\d+)\s*(stuks?|st)\b", t)
            if m:
                return int(m[1]) * piece_g
            if re.search(r"per stuk|per 1 st|per tros|^$", t) and text is size:
                return piece_g
    return None


def cheapest(foods, products):
    """Cheapest matching product per food. products: [(chain, product dict)]. Returns {key: (eur/100g, row)}."""
    out = {}
    for f in foods:
        inc, exc = re.compile(f["query"], re.I), re.compile(f["exclude"], re.I)
        piece_g, edible = float(f["piece_g"]), float(f["edible"])
        cands = []
        for chain, p in products:
            price = float(p.get("p") or 0)
            if not inc.search(p["n"]) or exc.search(p["n"]) or price < 0.05:
                continue
            g = parse_grams(p.get("s", ""), p["n"], piece_g)
            if not g:
                continue
            if f["key"].startswith("oil"):
                g *= 0.92  # ml -> g
            if f.get("canned") == "1":
                g *= 0.6   # NEVO canned vegetables/legumes are per 100 g drained
            cands.append((price / g * 100 / edible, chain, price, g, p["n"], p.get("s", "")))
        cands.sort()
        if cands:
            out[f["key"]] = cands
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chain", help="restrict to one chain, e.g. ah, jumbo, lidl, dirk")
    ap.add_argument("--show", type=int, default=3, help="candidates to print per food")
    ap.add_argument("--out", default="data/prices.tsv")
    a = ap.parse_args()

    stores = json.load(open(latest_snapshot()))
    products = [(s["n"], p) for s in stores for p in s["d"] if not a.chain or s["n"] == a.chain]
    foods = list(csv.DictReader(open("data/foods.tsv"), delimiter="\t"))
    found = cheapest(foods, products)

    out = []
    for f in foods:
        cands = found.get(f["key"], [])
        print(f"{f['key']:18}", "NO MATCH" if not cands else "")
        for c in cands[: a.show]:
            print(f"   €{c[0]:.3f}/100g  {c[1]:9} €{c[2]:.2f} {c[3]:6.0f} g  {c[4]}  [{c[5]}]")
        if cands:
            c = cands[0]
            out.append({"key": f["key"], "eur_per_100g": f"{c[0]:.4f}", "chain": c[1],
                        "pack_eur": c[2], "pack_g": round(c[3]), "product": c[4]})
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=out[0].keys(), delimiter="\t")
        w.writeheader(); w.writerows(out)
    print(f"\n{len(out)}/{len(foods)} foods priced -> {a.out}")


if __name__ == "__main__":
    main()
