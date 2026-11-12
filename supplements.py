"""Supplements: vitamin and mineral pills, fish and algae oil, psyllium. What is in them, what the model counts of that,
and what they cost.  python3 supplements.py  updates the supermarket prices from the newest Checkjebon snapshot.

Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources.

data/supplements.tsv        one row per supplement (a composition): the label's amounts per unit (a tablet, a capsule,
                            a 5 g spoon), in the label's units, with the label's source and date.
data/supplement_prices.tsv  the products that sell it: shop, units per pack, pack price. Supermarket products come from
                            the Checkjebon snapshot (source "checkjebon", `link` = Checkjebon's product link, refreshed by
                            this script); drugstore products were copied by hand from the shop's website (source "shop
                            website", with the date).

A supplement enters the linear program as a pseudo-food per unit (lp.load, unit_g = 0), with the label converted into
what the norms count (`counted`). The conversions, all model rules (docs/data.md):
  folic acid      x1.7 as folate (DFE), and x1 against the folic acid maximum (EFSA 2014; methylfolate: EFSA 2022)
  vitamin E       natural (d-alpha) x1; synthetic (dl-alpha) x0.67: the label's mg alpha-TE count dl-alpha at 74% of
                  natural, the norms (IOM 2000, EFSA 2015) at 50% (0.45 mg alpha-tocopherol per mg acetate, vs 0.67)
  vitamin B12     by dose: absorbed = min(dose x 0.5, 1.2 µg) + 1% of the dose (intrinsic factor takes up at most
                  ~1.2 µg per dose, about 1% passes passively: the St John's study of absorption by dose and the Cochrane
                  review of oral B12, links in docs/data.md); counted as the food B12 that is absorbed as much:
                  absorbed / 0.5. So 1000 µg counts as 22 µg, 100 µg as 4.4 µg
  iron            as non-haem iron: 10% absorbed, like iron from plants (lp.NONHAEM_ABS)
  vitamin A       retinol (retinyl acetate, the form in every product here) x1, and against the retinol maximum
  the rest        x1: no Dutch or EFSA norm gives a factor for pills (magnesium oxide is said to be absorbed worse than
                  citrate, but there is no agreed number)
The ~9 kcal of oil in a capsule is left out. Magnesium from pills gets its own maximum of 250 mg a day (EFSA: the upper
limit is for supplements only), as the computed column MG_SUPP.
"""
import csv
import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SUPP_FILE, PRICE_FILE = ROOT / "data/supplements.tsv", ROOT / "data/supplement_prices.tsv"

SUPP = {r["key"]: r for r in csv.DictReader(open(SUPP_FILE, encoding="utf-8"), delimiter="\t")}
DEFAULT_ON = ["vitD_tablet"]      # the plan's one supplement unless you tick others (the Supplements page)
SHOP_NAMES = {"deonlinedrogist": "De Online Drogist", "vitaminstore": "Vitaminstore"}

# B12 by dose (see the docstring)
B12_FOOD, B12_ACTIVE_MAX, B12_PASSIVE = 0.5, 1.2, 0.01
SYNTHETIC_E = 0.45 / 0.67
FOLATE_DFE = 1.7
MG_SUPP_MAX = 250.0

# label column -> (model column(s), label unit, nutrient in words)
LABEL = {
    "vitA_ug": (("VITA_RAE", "RETOL"), "µg", "vitamin A"), "vitD_ug": (("VITD",), "µg", "vitamin D"),
    "vitE_mg": (("VITE",), "mg", "vitamin E"), "vitK1_ug": (("VITK1",), "µg", "vitamin K1"),
    "vitC_mg": (("VITC",), "mg", "vitamin C"), "B1_mg": (("THIA",), "mg", "thiamin"),
    "B2_mg": (("RIBF",), "mg", "riboflavin"), "niacin_mg": (("NIAEQ",), "mg", "niacin"),
    "B6_mg": (("VITB6",), "mg", "vitamin B6"), "folate_ug": (("FOL", "FOLAC"), "µg", "folic acid"),
    "B12_ug": (("VITB12",), "µg", "vitamin B12"), "Ca_mg": (("CA",), "mg", "calcium"),
    "Mg_mg": (("MG", "MG_SUPP"), "mg", "magnesium"), "Fe_mg": (("FE",), "mg", "iron"), "Zn_mg": (("ZN",), "mg", "zinc"),
    "Cu_mg": (("CU",), "mg", "copper"), "I_ug": (("ID",), "µg", "iodine"), "Se_ug": (("SE",), "µg", "selenium"),
    "K_mg": (("K",), "mg", "potassium"), "EPA_mg": (("F20:5CN3",), "mg", "EPA"), "DHA_mg": (("F22:6CN3",), "mg", "DHA"),
    "fibre_g": (("FIBT",), "g", "fibre"), "kcal": (("ENERCC",), "kcal", "energy"),
}


def num(v):
    return float(v) if v not in ("", None) else None


def name(k):
    return SUPP[k]["name"] if k in SUPP else k


def b12_counted(dose):
    """µg of food B12 a dose counts as: absorbed the same amount (see the docstring)."""
    return (min(dose * B12_FOOD, B12_ACTIVE_MAX) + B12_PASSIVE * dose) / B12_FOOD


def categories(k):
    """The category and allergy ticks that remove this supplement (categories.py): 'supplements', and what its
    `categories` column adds (fish oil: fish; a beef gelatin capsule: meat ...)."""
    return {"supplements"} | {c for c in SUPP[k].get("categories", "").split("|") if c}


def counted(k):
    """What one unit of supplement k counts as: ({model column: amount}, [rows for the page]).
    A row: nutrient, label amount and unit, factor, counted amount, why."""
    s = SUPP[k]
    cols, rows_ = {}, []
    for lab, (targets, unit, what) in LABEL.items():
        v = num(s[lab])
        if not v:
            continue
        for col in targets:
            f, why = 1.0, ""
            if col == "VITE" and s["vitE_form"] == "synthetic":
                f, why = SYNTHETIC_E, "synthetic (dl-alpha) vitamin E counts two thirds"
            elif col == "FOL":
                f, why = FOLATE_DFE, f"{s['folate_form']} counts 1.7x as folate (DFE)"
            elif col == "VITB12":
                f, why = b12_counted(v) / v, f"absorbed {b12_counted(v) * B12_FOOD:.2g} µg of {v:g}: the food B12 absorbed as much"
            elif col == "FE":
                why = "counts as non-haem iron: 10% absorbed"
            elif col in ("F20:5CN3", "F22:6CN3"):
                f = 0.001                                          # the label's mg -> NEVO's g
            elif col == "RETOL":
                why = "retinol: counts against the retinol maximum too"
            elif col == "FOLAC":
                why = "and against the folic acid maximum"
            elif col == "MG_SUPP":
                why = f"and against the {MG_SUPP_MAX:.0f} mg maximum for magnesium from pills"
            cols[col] = cols.get(col, 0.0) + v * f
            if col not in ("RETOL", "FOLAC", "MG_SUPP") or why:
                shown = v * f if col not in ("F20:5CN3", "F22:6CN3") else v
                rows_.append({"nutrient": what if col not in ("RETOL", "FOLAC", "MG_SUPP") else
                              {"RETOL": "retinol", "FOLAC": "folic acid (max)", "MG_SUPP": "magnesium from pills"}[col],
                              "label": v, "unit": unit, "factor": f if col not in ("F20:5CN3", "F22:6CN3") else 1.0,
                              "counted": shown, "why": why})
    return cols, rows_


def contents(k):
    """One line: what's on the label, e.g. 'vitamin D 25 µg' or 'calcium 400 mg, magnesium 187.5 mg (oxide), ...'."""
    s, out = SUPP[k], []
    for lab, (_, unit, what) in LABEL.items():
        v = num(s[lab])
        if v and lab != "kcal":
            form = {"vitE_mg": s["vitE_form"], "Mg_mg": s["Mg_form"],
                    "folate_ug": s["folate_form"] if s["folate_form"] != "folic acid" else ""}.get(lab, "")
            out.append(f"{what} {v:g} {unit}" + (f" ({form})" if form else ""))
    return ", ".join(out)


def products():
    rows_ = []
    for r in csv.DictReader(open(PRICE_FILE, encoding="utf-8"), delimiter="\t"):
        if r["key"] not in SUPP or not r["price"]:
            continue
        r = dict(r)
        r["units"], r["price"] = int(r["units"]), float(r["price"])
        r["per_unit"] = r["price"] / r["units"]
        rows_.append(r)
    return rows_


_OFFERS = {}


def offers(k):
    """Every product of supplement k with a price, cheapest per unit first."""
    if not _OFFERS:
        for r in sorted(products(), key=lambda r: r["per_unit"]):
            _OFFERS.setdefault(r["key"], []).append(r)
    return _OFFERS.get(k, [])


CHAIN_SHOPS = {"ah": "Albert Heijn", "plus": "PLUS", "jumbo": "Jumbo", "dekamarkt": "DekaMarkt", "spar": "Spar",
               "lidl": "Lidl", "dirk": "Dirk", "hoogvliet": "Hoogvliet", "poiesz": "Poiesz", "vomar": "Vomar"}


def shop_name(shop):
    return SHOP_NAMES.get(shop) or CHAIN_SHOPS.get(shop, shop)


def best(k, chain=None):
    """The cheapest product per unit: at the chain if one is given (None: any shop, drugstores too)."""
    return next((r for r in offers(k) if chain is None or r["shop"] == chain), None)


def spec(mode="ticked", on=DEFAULT_ON, anywhere=True, prices=None, exact=()):
    """What the solvers get (lp.load pills=...): plain JSON, so it can be part of a cache key.
    mode: 'ticked' (the supplements in `on`), 'priced' (every one with a price) or 'all' (no price = free).
    anywhere: the cheapest shop, drugstores too; else only your chain. prices: {key: your € per unit}.
    exact: [[key, units a day]]: exactly that much, whatever the mode."""
    return {"mode": mode, "on": sorted(on) if mode == "ticked" else [], "anywhere": bool(anywhere),
            "prices": {k: float(v) for k, v in sorted((prices or {}).items()) if k in SUPP and v is not None},
            "exact": sorted([k, float(n)] for k, n in exact if k in SUPP)}


DEFAULT = spec()


def price_of(k, sp, chain):
    """(€ per unit or None, the product row or None, your price?) under spec sp at this chain (None: every chain)."""
    sp = sp or DEFAULT
    yours = sp["prices"].get(k)
    offer = best(k, None if sp["anywhere"] or chain is None else chain)
    if yours is not None:
        return yours, offer, True
    return (offer["per_unit"] if offer else None), offer, False


def choose(sp, chain):
    """The supplements the plan may use: [{key, price, free, offer, yours, exact}]. A supplement without a price is
    free (price 0, free=True). Exact amounts always count, whatever the mode."""
    sp = sp or DEFAULT
    exact = dict(sp["exact"])
    out = []
    for k in SUPP:
        price, offer, yours = price_of(k, sp, chain)
        mode = sp["mode"]
        if not (k in exact or mode == "all" or (mode == "priced" and price is not None) or
                (mode == "ticked" and k in sp["on"])):
            continue
        out.append({"key": k, "price": price or 0.0, "free": price is None, "offer": offer, "yours": yours,
                    "exact": exact.get(k)})
    return out


def describe(sp):
    """The setting in a few words, for the sidebar and page headers."""
    sp = sp or DEFAULT
    base = {"priced": "every supplement with a price", "all": "every supplement (no price = free)"}.get(sp["mode"])
    if base is None:
        on = sp["on"]
        base = ("no supplements" if not on else f"{name(on[0]).lower()} only" if len(on) == 1 else
                f"{len(on)} ticked supplements")
    extra = [f"{len(sp['exact'])} exact"] if sp["exact"] else []
    if not sp["anywhere"]:
        extra.append("your chain only")
    return base + (f" ({', '.join(extra)})" if extra else "")


def main():
    """Update the supermarket prices (source "checkjebon") from the newest snapshot. A product the snapshot no longer has
    loses its price (it stays listed, so it can come back)."""
    files = sorted(glob.glob(str(ROOT / "data/checkjebon_*.json")))
    if not files:
        raise SystemExit("no price snapshot: run python3 fetch_prices.py")
    date = Path(files[-1]).stem.removeprefix("checkjebon_")
    snap = {(ch["n"], p["l"]): p for ch in json.load(open(files[-1], encoding="utf-8")) for p in ch["d"]}
    rows_ = list(csv.DictReader(open(PRICE_FILE, encoding="utf-8"), delimiter="\t"))
    changed = gone = 0
    for r in rows_:
        if r["source"] != "checkjebon":
            continue
        p = snap.get((r["shop"], r["link"]))
        new = f"{p['p']:.2f}" if p else ""
        changed += new != r["price"]
        gone += not p
        r["price"], r["date"] = new, date if p else r["date"]
    with open(PRICE_FILE, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_[0]), delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(rows_)
    print(f"supplement prices from {Path(files[-1]).name}: {changed} changed, {gone} not in the snapshot")


if __name__ == "__main__":
    main()
