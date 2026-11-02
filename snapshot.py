import glob


def latest_snapshot():
    """Newest data/checkjebon_YYYY-MM-DD.json (run fetch_prices.py if there is none)."""
    files = sorted(glob.glob("data/checkjebon_*.json"))
    if not files:
        raise SystemExit("no price snapshot: run python3 fetch_prices.py")
    return files[-1]
