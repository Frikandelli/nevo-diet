import glob

import supplements as S


def latest_snapshot():
    """Newest data/checkjebon_YYYY-MM-DD.json (run fetch_prices.py if there is none)."""
    files = sorted(glob.glob("data/checkjebon_*.json"))
    if not files:
        raise SystemExit("no price snapshot: run python3 fetch_prices.py")
    return files[-1]


def catalog_date():
    """The date of the Checkjebon snapshot the committed catalog was built from (data/catalog_snapshot.txt, written by
    catalog.py), for report headers: the snapshot file itself isn't in git."""
    try:
        name = open("data/catalog_snapshot.txt").read().strip()
    except FileNotFoundError:
        return "unknown date"
    return name.removeprefix("checkjebon_").removesuffix(".json")


def food_name(k, foods):
    """A food's name for reports: the NEVO English name (catalog_foods.tsv `name`), for hand-mapped foods too."""
    if k in S.SUPP:
        return S.name(k)
    return foods[k]["name"] if k in foods else k
