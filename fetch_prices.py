"""Download the latest Checkjebon price snapshot (MIT, github.com/supermarkt/checkjebon)
to data/checkjebon_<commit date>.json.  python3 fetch_prices.py"""
import json, urllib.request

API = "https://api.github.com/repos/supermarkt/checkjebon/commits?path=data/supermarkets.json&per_page=1"
RAW = "https://raw.githubusercontent.com/supermarkt/checkjebon/main/data/supermarkets.json"

date = json.load(urllib.request.urlopen(API))[0]["commit"]["committer"]["date"][:10]
path = f"data/checkjebon_{date}.json"
urllib.request.urlretrieve(RAW, path)
print(f"saved {path}")
