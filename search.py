"""Helper: python3 search.py nevo <regex> | python3 search.py price <regex>"""
import csv, json, re, sys

from snapshot import latest_snapshot
kind, pat = sys.argv[1], re.compile(sys.argv[2], re.I)
if kind == "nevo":
    with open("data/nevo/NEVO2025_v9.0.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter="|"):
            if pat.search(r["Voedingsmiddelnaam/Dutch food name"]) or pat.search(r["Engelse naam/Food name"]):
                print(f'{r["NEVO-code"]:>5} | {r["Voedingsmiddelnaam/Dutch food name"][:45]:45} | {r["Engelse naam/Food name"][:45]:45} | {r["ENERCC (kcal)"]} kcal P{r["PROT (g)"]}')
else:
    for s in json.load(open(latest_snapshot())):
        for p in s["d"]:
            if pat.search(p["n"]):
                print(f'{s["n"]:9} {p["p"]:6.2f}  {p.get("s",""):14}  {p["n"]}')
