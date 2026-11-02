"""Grow the food list automatically: match every supermarket product with a weight/volume on the label
to a basic NEVO food by name, and write per-chain prices.

    python3 expand.py            -> data/auto_matches.tsv (product level), data/auto_prices.tsv (food x chain)
    python3 expand.py --sample 60  also prints a random sample of accepted matches for review

Only basic foods: composite products (ready meals, sauces, snacks, "X met Y") are skipped, since the LP can
combine basic foods itself. A product is dropped when its match is ambiguous.
"""
import argparse, csv, json, random, re, unicodedata
from collections import defaultdict

from price import parse_grams
from snapshot import latest_snapshot

NEVO = "data/nevo/NEVO2025_v9.0.csv"
BASIC_GROUPS = {
    "Potatoes and tubers", "Vegetables", "Fruits", "Legumes", "Nuts and seeds", "Cereal products and types of flour",
    "Bread", "Milk and milk products", "Cheese", "Eggs", "Fish, crustacean and shellfish", "Meat and poultry",
    "Cold meat cuts", "Fats and oils", "Meat substitutes and dairy substitutes", "Savoury bread spreads",
    "Non-alcoholic beverages", "Sugar, sweets and sweet sauces", "Miscellaneous foods",
}
# Sweets/beverages only for bread toppings, juices and plant drinks; everything else there is a treat or a soda.
GROUP_FILTER = {
    "Sugar, sweets and sweet sauces": re.compile(r"jam|hagelslag|vlokken|appelstroop|honing|stroop|muisjes|pasta (choc|speculoos)|chocoladepasta", re.I),
    "Non-alcoholic beverages": re.compile(r"^sap |^drink|melk|^water", re.I),
    "Miscellaneous foods": re.compile(r"^zout", re.I),
}
STATE = {  # word -> state
    "rauw": "raw", "onbereid": "raw", "vers": "raw", "gedroogd": "dried", "gedroogde": "dried", "droog": "dried",
    "diepvries": "frozen", "blik": "canned", "glas": "canned", "pot": "canned", "gekookt": "cooked",
    "gekookte": "cooked", "gebakken": "fried", "gefrituurd": "fried", "bereid": "prepared", "gegrild": "grilled",
    "gegrilde": "grilled", "gestoomd": "steamed", "gestoofd": "stewed", "gerookt": "smoked", "gerookte": "smoked",
}
FILLER = {"gem", "m", "z", "v", "obv", "en", "of", "incl", "excl", "av", "met", "zonder", "van", "op", "basis",
          "in", "de", "het", "een", "voor", "per", "ca", "x", "uit", "nl", "eu", "toegevoegd", "e", "d", "ed"}
# Product words that mean "not a basic food" (unless the NEVO name has them too)
NONFOOD = re.compile(r"\b(danio|tyrrells|kettle|purina|vitakraft|friskies|kitekat|brekkies|beefsticks|doritos|tuc|lays|pringles|croky|chio|"
                     r"cheetos|wokkels|bugles|sultana|whey|gekonfijte|gekonfijt|"
                     r"afwasmiddel|wasmiddel|geur|koffie|snelfiltermaling|maling|capsules|pads|jus|mix voor|"
                     r"pie|pets?|good boy|whiskas|felix|sheba|gourmet gold|pedigree|catisfactions|dreamies|spray|"
                     r"shampoo|deo|douche|zeep|tandpasta|wasmiddel|thee|tea|infusion|koffiebonen|espresso|"
                     r"bier|wijn|rum|likeur|vodka|whisky|gin|jenever|cider|limonade|frisdrank|energy|cola|"
                     r"siroop|ranja|chocolade|chocola|bonbons?|snoep|drop|kauwgom|cakemix|bakmix|"
                     r"vleesvervanger|vegetarische|vega)\b|chips\b|"
                     r"katten|honden|droogvoer|natvoer|\bfrolic\b|\biams\b|perfect fit|\bkitten")  # pet food (stage 4)
COMPOSITE = re.compile(r"\b(soup|saus|soep|salade|maaltijd|pizza|lasagne|wrap|chips|koek|koekje|koekjes|reep|repen|snack|"
                       r"gevuld|gevulde|kinder|baby|maanden|hond|honden|kat|katten|kattenvoer|hondenvoer|dier|"
                       r"proefpakket|smaak|ijs|dessert|pudding|vla|toetje|shake|smoothie|taart|cake|muffin|"
                       r"spread|dip|tapenade|pesto|marinade|gemarineerd|gemarineerde|kruidenmix|bouillon|"
                       r"schotel|ovenschotel|stamppot|nasi|bami|curry|roerbak|wokmix|kit|pakket|box)\b")
MODIFIERS = {"light", "lactosevrij", "ongezoet", "ongezouten", "gezouten", "suikervrij", "protein", "eiwit",
             "vegan", "vegetarisch", "plantaardig", "zero", "halfvolle", "volle", "magere", "mager", "volvet",
             "gezoet", "zoet", "verrijkt", "geroosterd", "gebrand", "ongebrand", "gepeld", "zuur", "zoetzuur"}
FORM_WORDS = {"jam", "gelei", "confiture", "compote", "puree", "poeder", "siroop", "stroop", "pasta", "sap", "olie"}
CANNED_HINT = re.compile(r"\b(hak|bonduelle|blik|pot|glas|in water|in tomatensaus|op sap|op siroop|uitgelekt|"
                         r"in eigen sap|in \w*olie|olijfolie|zonnebloemolie)\b")
DRAINED = 0.6     # NEVO canned vegetables/legumes are per 100 g drained; a can is ~60% solids [assumption]
# Refuse when bought whole (NEVO is per 100 g edible part). Approximate values, USDA-style refuse percentages.
EDIBLE = [(r"^banaan", 0.64), (r"^sinaasappel|^mandarijn|^grapefruit", 0.73), (r"^meloen|^ananas", 0.52),
          (r"^mango|^avocado", 0.70), (r"^appel |^peer ", 0.90), (r"^kiwi", 0.86), (r"^ui |^knoflook", 0.90),
          (r"^aardappel", 0.85), (r"^wortel", 0.90), (r"^kool (witte|rode|groene|spits|savooie)", 0.80),
          (r"^kool (bloem|broccoli)|^broccoli", 0.65), (r"^prei", 0.60), (r"^selderij knol", 0.75),
          (r"^pompoen", 0.70), (r"^ei kippen", 0.88), (r"drumstick|kippenpoot|vleugel|^kip m vel", 0.70),
          (r"^mosselen rauw", 0.20)]   # mussels in the shell: ~200 g meat per kg (maxvandaag.nl rule of thumb; conservative)


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()
    s = re.sub(r"\b(z|zonder) vel\b", "zondervel", s)
    s = re.sub(r"\b(m|met) vel\b", "metvel", s)
    s = re.sub(r"\b(z|zonder) suiker\b|\bongezoet\b", "zondersuiker", s)
    s = re.sub(r"\b(m|met|z|zonder) schil\b", "", s)      # peel: price already handles the edible part
    s = re.sub(r"\d+([.,]\d+)?\s*(x\s*)?\d*\s*(g|gr|gram|kg|kilo|ml|cl|l|liter|stuks?|st)\b", " ", s)
    return re.sub(r"[^a-z0-9+]+", " ", s).split()


DIMINUTIVE = re.compile(r"(tjes|jes|tje|je)$")
HARMLESS = {"hollandse", "hollands", "vers", "verse", "biologisch", "biologische", "bio", "scharrel", "fijn",
            "fijne", "grof", "grove", "vlokken", "witte", "wit", "bruine", "rode", "groene", "gele", "zachte", "zacht", "naturel", "klassiek", "original", "voordeelverpakking", "voordeel", "groot",
            "mini", "stuk", "stukken", "plakken", "gesneden", "heel", "half", "los", "zak", "bak", "doos", "netje"}
# Product words that labels use but NEVO names don't (word -> NEVO words)
PRODUCT_SYN = {"gouda": "kaas goudse", "goudse": "kaas goudse", "kipdijfilet": "kip zondervel", "kippendijfilet": "kip zondervel",
               "kipdijen": "kip zondervel", "tafelzout": "zout", "keukenzout": "zout", "jodiumzout": "zout jodium",
               "zilvervliesrijst": "rijst zilvervlies", "volkorenbrood": "tarwebrood volkoren",
               "tarwebloem": "bloem tarwe", "rundergehakt": "gehakt runder", "varkensgehakt": "gehakt varkens",
               "kippenvleugels": "kip vleugel", "havermout": "havervlokken", "winterpeen": "wortel winterpeen",
               "bospeen": "wortel bospeen", "penne": "pasta", "spaghetti": "pasta", "macaroni": "pasta",
               "fusilli": "pasta", "farfalle": "pasta", "tagliatelle": "pasta", "uien": "ui", "kipfilets": "kipfilet",
               "scharreleieren": "kippenei", "eieren": "kippenei", "tomatenblokjes": "tomaat blik",
               "havermelk": "haverdrink", "snijwaren": "vleeswaar", "vleeswaren": "vleeswaar",
               "broodbeleg": "vleeswaar", "yog": "yoghurt", "hoemoes": "hummus", "choco": "chocolademelk"}
HEAD_BLOCK = HARMLESS | {"volkoren", "halfvolle", "volle", "magere", "light", "ongezouten", "gezouten"}


def stem(w):
    if w in ("eieren", "eiren"): return "ei"
    if len(w) > 6:
        w = DIMINUTIVE.sub("", w)          # kippenlevertjes -> kippenlever
    for suf in ("eren", "en", "es", "s", "e"):
        if w.endswith(suf) and len(w) - len(suf) >= 2:
            w = w[: -len(suf)]; break
    if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "aeiou":
        w = w[:-1]                         # kippen -> kipp -> kip
    w = re.sub(r"(aa|ee|oo|uu)", lambda m: m[0][0], w)   # peer/peren -> per
    return re.sub(r"z$", "s", w)           # kazen -> kas


def nevo_aliases(row):
    """Name variants: compounds resolved ('Kool bloem-' -> 'bloemkool'), plus synonyms.
    Returns (text, optional words): words in 'a/b' or 'a en b' lists are optional ('Linzen groene en bruine')."""
    out = []
    for i, text in enumerate([row["Voedingsmiddelnaam/Dutch food name"]] +
                             [x for x in re.split(r"/(?=[A-Z])", row["Synoniem"]) if x.strip()]):
        text = text.lower()
        optional = set()
        for m in re.finditer(r"([a-z]+)(?:/([a-z]+))+", text):
            optional |= set(m[0].split("/"))
        for m in re.finditer(r"([a-z]+) en ([a-z]+)", text):
            optional |= {m[1], m[2]}
        optional |= {"goudse"} & set(text.split())     # most Dutch 'belegen 48+' is Gouda-type
        toks = text.replace("/", " ").split()
        if i == 0 and len(toks) > 1 and toks[1].endswith("-"):
            toks = [toks[1][:-1] + toks[0]] + toks[2:]
        out.append((" ".join(toks), optional))
    return out


def tokens(text, syn=False):
    text = re.sub(r"\bsap (\w+)", r"\1sap", text.lower()) if syn else text   # 'sap sinaasappel' -> sinaasappelsap
    t = [re.sub(r"(?<=.{4})(stukken|stukjes|blokjes|reepjes|plakjes|plakken|filets)$", "", w)
         for w in norm(text.replace("-", " "))]
    if syn:
        t = [x for w in t for x in PRODUCT_SYN.get(w, w).split()]
    return {"core": [w for w in t if w not in FILLER and w not in STATE and not any(c.isdigit() for c in w)],
            "state": {STATE[w] for w in t if w in STATE}, "words": set(t)}


def brands(min_products=25):
    """Words that start many product names in the price data (AH, Jumbo, g'woon, Alpro...): brands, not food."""
    first = defaultdict(int)
    for s in json.load(open(latest_snapshot())):
        for p in s["d"]:
            t = norm(p["n"])
            if t:
                first[t[0]] += 1
    return {w for w, n in first.items() if n >= min_products}


def build_index():
    """NEVO aliases with precomputed stems, indexed by the stem of their head word; plus the food vocabulary."""
    allrows = list(csv.DictReader(open(NEVO, encoding="utf-8"), delimiter="|"))
    vocab = {stem(w) for r in allrows for w in norm(r["Voedingsmiddelnaam/Dutch food name"].replace("-", " "))
             if len(w) >= 4} - {stem(w) for w in HARMLESS | FILLER | set(STATE)}
    for r in allrows:
        for text, _ in nevo_aliases(r):
            vocab |= {stem(w) for w in norm(text.replace("-", " ")) if len(w) >= 5} - {stem(w) for w in HARMLESS}
    food_heads = {stem(norm(r["Voedingsmiddelnaam/Dutch food name"].replace("-", " "))[0]) for r in allrows}
    vocab -= {stem(b) for b in brands()} - food_heads    # 'jumbo' is a brand; 'kip' starts products but is food
    by_head = defaultdict(list)
    for r in allrows:
        g = r["Food group"]
        if r["Voedingsmiddelnaam/Dutch food name"].lower().startswith("water"):
            continue
        if g not in BASIC_GROUPS or (g in GROUP_FILTER and not GROUP_FILTER[g].search(r["Voedingsmiddelnaam/Dutch food name"])):
            continue
        for text, optional in nevo_aliases(r):
            t = tokens(text)
            if t["core"] and t["core"][0] not in HEAD_BLOCK | HEAD_BLOCK_EXTRA:
                t["stems"] = [(stem(w), len(w), w in optional, w) for w in t["core"]]
                by_head[t["stems"][0][0]].append((r, t))
    return by_head, vocab


def candidates(by_head, pst):
    """Aliases whose head occurs in the product: exactly, inside a compound, or as the start of a longer NEVO word."""
    out = []
    for h, lst in by_head.items():
        if h in pst or (len(h) >= 4 and any(h in p for p in pst)) or any(len(p) >= 5 and h.startswith(p) for p in pst):
            out += lst
    return out


def forms(w):
    """A Dutch word with its plural/diminutive forms: kip/kippen, peer/peren, boon/bonen, kaas/kazen."""
    out = {w, w + "s", w + "en", w + "n", w + "'s", w + "tjes", w + "jes", w + "tje", w + "je"}
    if re.search(r"[^aeiou][aeiou][^aeiouy]$", w):
        out.add(w + w[-1] + "en")                             # kip -> kippen
    m = re.search(r"(aa|ee|oo|uu)([^aeiou])$", w)
    if m:
        out.add(w[: m.start()] + m[1][0] + m[2].replace("s", "z").replace("f", "v") + "en")   # peer -> peren
    return out


def same(a, p):
    """Product word p is the NEVO word a (or a plural/diminutive of it)."""
    if a == p:
        return True
    if min(len(a), len(p)) <= 3:
        return False                       # 'ij' (Brouwerij 't IJ) is not 'ijs'
    if p in forms(a) or a in forms(p):
        return True
    return min(len(a), len(p)) >= 6 and stem(a) == stem(p)   # stems only for long words (bonne != bonen)


def is_food(w, vocab):
    """A food word, or a compound ending in one (kipgrillworst ends in grillworst)."""
    return stem(w) in vocab or any(stem(w[i:]) in vocab for i in range(1, len(w) - 4))


def score(alias, pst, vocab, words):
    """(coverage of the alias' required words, head matched, matched weight, product food words left unexplained).
    Optional words (from 'a/b' lists) add to the matched weight but never to coverage."""
    hit = req_hit = req_tot = 0.0
    head_ok = False
    used = set()
    for k, (sa, wgt, optional, aw) in enumerate(alias["stems"]):
        got = 0.0
        for w in words:
            g = 0.0
            if same(aw, w) or (aw == "olie" and w.endswith("olie")):
                g = 1.0                    # olie ~ olijfolie/zonnebloemolie when fish is packed in it
            elif len(aw) >= 4 and w.endswith(aw) and stem(w[: -len(aw)]) not in vocab:
                g = 0.6                    # scharrelkippenlever ~ kippenlever, but not kokosmelk ~ melk
            elif len(aw) >= 5 and aw in w and not any(stem(x) in vocab for x in w.split(aw) if len(x) >= 3):
                g = 0.4
            elif len(w) >= 5 and aw.startswith(w):
                g = 0.5                    # haring ~ haringfilet
            if g:
                used.add(w)
                got = max(got, g)
        hit += got * wgt
        if not optional:
            req_tot += wgt; req_hit += got * wgt
        head_ok |= k == 0 and got >= (0.5 if not optional else 1.0)
    leftover = sum(len(w) for w in words if w not in used and is_food(w, vocab))
    cov = req_hit / req_tot if req_tot else (1.0 if head_ok else 0.0)
    return cov, head_ok, hit, leftover


LIQUID_GROUPS = {"Milk and milk products", "Non-alcoholic beverages", "Fats and oils",
                 "Meat substitutes and dairy substitutes", "Savoury sauces", "Miscellaneous foods"}
COMPOUND_COMPOSITE = re.compile(r"(soep|soup|salade|saus|toetje|drink|drank|smoothie|shot|salsa|stoof|stoofpotje|"
                                r"biscuits?|snoepjes|repen|chips|crackers?|koek|koekjes|cake|snack|spread|bowl|"
                                r"potje|ijsje|beleg)$")
HEAD_BLOCK_EXTRA = {"zure", "zuur", "zoete", "oude", "oud", "jonge", "jong", "belegen", "extra", "franse", "griekse",
                    "turkse", "italiaanse", "spaanse", "verse", "gerookte", "gekookte", "gebakken", "gegrilde",
                    "gedroogde", "gemengde", "gem", "pure", "puur", "romige", "zachte", "harde", "kleine", "grote"}


def match(prod_name, idx, liquid=False):
    """Best NEVO food for a product name -> (row, 'ok') or (None, reason). liquid: sold per ml/l."""
    by_head, vocab = idx
    t = tokens(prod_name, syn=True)
    if not t["core"]:
        return None, "empty"
    pst = [stem(w) for w in t["core"]]
    if NONFOOD.search(" ".join(norm(prod_name))):
        return None, "nonfood"
    composite = COMPOSITE.search(" ".join(t["words"])) or any(
        COMPOUND_COMPOSITE.search(w) for w in t["words"] if len(w) > 5)
    # in "tonijnstukken in zonnebloemolie" the food is what comes before "in"
    words_all = norm(prod_name.replace("-", " "))
    cut = [i for i, w in enumerate(words_all) if w in ("in", "van") and i > 0]
    head_words = set(words_all[: cut[0]]) if cut else set(words_all)
    head_words |= {x for w in head_words for x in PRODUCT_SYN.get(w, "").split()}
    dried_hint = bool(re.search(r"\bzak\b", prod_name.lower()))
    canned_hint = bool(CANNED_HINT.search(prod_name.lower()))
    pstate = t["state"]
    best = []
    for r, a in candidates(by_head, pst):
        if liquid and r["Food group"] not in LIQUID_GROUPS:
            continue                       # 'Spa Touch watermelon-kiwi 750 ml' is not a kiwi
        if composite and not (COMPOSITE.search(" ".join(a["words"])) or
                              any(COMPOUND_COMPOSITE.search(w) for w in a["words"] if len(w) > 5)):
            continue
        cov, head, hit, leftover = score(a, pst, vocab, t["core"])
        if cov < 0.75 or not head or leftover > 0.4 * hit:
            continue
        if not any(same(a["stems"][0][3], w) or a["stems"][0][3] in w or (len(w) >= 5 and a["stems"][0][3].startswith(w))
                   for w in head_words):
            continue                       # head must come from the part before "in"
        if dried_hint and "canned" in a["state"] and r["Food group"] == "Legumes":
            continue
        pf = re.findall(r"(\d\d)\s?\+", prod_name)
        nf = re.findall(r"(\d\d)\s?\+", r["Voedingsmiddelnaam/Dutch food name"])
        if r["Food group"] == "Cheese" and not pf and nf and int(nf[0]) < 45:
            continue                       # no fat class on the label: assume full-fat (48+)
        if pf and nf and abs(int(pf[0]) - int(nf[0])) > 5:
            continue                       # Beemster belegen 48+ is not 'Kaas 30+'
        opts = [x for x in a["stems"][1:] if x[2]]
        if (opts and len(a["stems"]) == 1 + len(opts) and len(by_head[a["stems"][0][0]]) >= 12
                and not any(same(x[3], w) for x in opts for w in t["core"])):
            continue                       # 'Illy Bonen' doesn't say which beans: skip 'Bonen witte/bruine'

        if any(m in t["words"] and not any(m in aw for aw in a["words"]) for m in FORM_WORDS):
            continue                       # 'Hero jam blauwe bessen' is jam, not blueberries
        if any(m in t["words"] and m not in a["words"] for m in MODIFIERS):
            continue                       # light, lactosevrij, ... must be in the NEVO name
        if ({"met", "en"} & t["words"]) and not ({"m", "met", "en"} & a["words"]):
            continue                       # "X met Y" only for NEVO combos ("Doperwten m wortelen")
        nst = a["state"]
        if nst & {"cooked", "fried", "prepared", "grilled", "steamed", "stewed", "smoked"} and not (nst & pstate):
            continue                       # prepared NEVO entries need the word on the label
        if pstate - {"raw"} and not (pstate & nst):
            continue                       # label says frozen/canned/dried/smoked: NEVO must agree
        if canned_hint and "canned" not in nst and r["Food group"] in ("Legumes", "Vegetables", "Fruits", "Fish, crustacean and shellfish"):
            continue
        evidence = not (nst & {"canned", "dried"}) or bool(nst & pstate) or ("canned" in nst and canned_hint)
        if "dried" in nst and not evidence and r["Food group"] not in ("Legumes", "Cereal products and types of flour", "Nuts and seeds"):
            continue                       # dried fruit/veg only when the label says so (not 'Peren' -> dried pears)
        best.append((cov - leftover / 100, hit, evidence, r["NEVO-code"], r, nst))
    if not best:
        return None, "composite" if composite else "nomatch"
    best.sort(key=lambda b: (b[2], b[0], b[1]), reverse=True)
    top = best[0]
    rivals = [b for b in best[1:] if b[3] != top[3] and b[0] >= top[0] - 0.05]
    if not top[2]:
        # no state on the label: fine only if no close rival is stored differently (dried vs canned vs fresh)
        if any((b[5] & {"canned", "dried"}) != (top[5] & {"canned", "dried"}) for b in rivals):
            return None, "state-unclear"
    for b in rivals:
        if b[2] == top[2] and abs(b[0] - top[0]) < 1e-9 and abs(b[1] - top[1]) < 1e-9:
            e1, e2 = (float(x["ENERCC (kcal)"] or 0) for x in (top[4], b[4]))
            p1, p2 = (float(x["PROT (g)"].replace(",", ".") or 0) for x in (top[4], b[4]))
            if abs(e1 - e2) > 0.1 * max(e1, e2, 1) or abs(p1 - p2) > 0.1 * max(p1, p2, 1):
                return None, f"ambiguous:{top[3]}/{b[3]}"
    return top[4], "ok"


def edible(nevo_name, state):
    if state in ("canned",):
        return DRAINED
    for pat, f in EDIBLE:
        if re.search(pat, nevo_name.lower()):
            return f
    return 1.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0)
    a = ap.parse_args()
    idx = build_index()
    nevo_rows = {r["NEVO-code"]: r for r in csv.DictReader(open(NEVO, encoding="utf-8"), delimiter="|")}
    review = [(re.compile(r["product_regex"], re.I), r["action"]) for r in
              csv.DictReader(open("data/review.tsv"), delimiter="\t")]
    stores = json.load(open(latest_snapshot()))
    matches, reasons, cache = [], defaultdict(int), {}
    for s in stores:
        for p in s["d"]:
            price = float(p.get("p") or 0)
            g = parse_grams(p.get("s", ""), p["n"], 0)
            if price < 0.10 or not g:
                reasons["no price/weight"] += 1; continue
            if any(rx.search(p["n"]) and act == "exclude" for rx, act in review):
                reasons["excluded in review"] += 1; continue
            remap = [act.split(":")[1] for rx, act in review if act.startswith("remap:") and rx.search(p["n"])]
            liquid = bool(re.search(r"\d\s*(ml|cl|l|liter|milliliter)\b", (p.get("s") or p["n"]).lower()))
            key = (p["n"], liquid)
            if key not in cache:
                cache[key] = match(p["n"], idx, liquid)
            r, why = cache[key]
            if remap:
                r, why = nevo_rows[remap[0]], "ok"
            reasons[why.split(":")[0]] += 1
            if not r:
                continue
            nname = r["Voedingsmiddelnaam/Dutch food name"]
            canned = "blik" in nname.lower() or "glas" in nname.lower()
            drained = DRAINED if canned and r["Food group"] in ("Legumes", "Vegetables") else 1.0
            ed = drained if drained < 1 else edible(nname, "")
            if "olie" in nname.lower() and re.search(r"\b(ml|l|liter)\b", (p.get("s") or "").lower()):
                g *= 0.92
            matches.append({"chain": s["n"], "product": p["n"], "size": p.get("s", ""), "pack_eur": price,
                            "pack_g": round(g), "edible": ed, "eur_per_100g": round(price / g * 100 / ed, 4),
                            "nevo": r["NEVO-code"], "nevo_name": nname, "group": r["Food group"]})
    print("products by outcome:", dict(reasons))

    # drop price outliers per food (cheapest-match errors): < 35% of the median for that food
    by_food = defaultdict(list)
    for m in matches:
        by_food[m["nevo"]].append(m)
    kept = []
    for code, ms in by_food.items():
        med = sorted(x["eur_per_100g"] for x in ms)[len(ms) // 2]
        kept += [m for m in ms if m["eur_per_100g"] >= 0.35 * med]
    with open("data/auto_matches.tsv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(kept[0]), delimiter="\t", lineterminator="\n")
        w.writeheader(); w.writerows(sorted(kept, key=lambda m: (m["nevo_name"], m["chain"], m["eur_per_100g"])))

    # food x chain: cheapest matched product
    best = {}
    for m in kept:
        k = (m["nevo"], m["chain"])
        if k not in best or m["eur_per_100g"] < best[k]["eur_per_100g"]:
            best[k] = m
    with open("data/auto_prices.tsv", "w", newline="") as f:
        cols = ["nevo", "nevo_name", "group", "chain", "eur_per_100g", "edible", "product", "pack_eur", "pack_g"]
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        w.writeheader(); w.writerows(sorted(best.values(), key=lambda m: (m["nevo_name"], m["chain"])))
    foods = {m["nevo"] for m in kept}
    chains = defaultdict(set)
    for (code, ch) in best:
        chains[code].add(ch)
    print(f"{len(kept)} product matches -> {len(foods)} NEVO foods; "
          f"{sum(len(v) >= 3 for v in chains.values())} sold at >= 3 chains")
    per_chain = defaultdict(int)
    for (code, ch) in best:
        per_chain[ch] += 1
    print("foods per chain:", dict(sorted(per_chain.items(), key=lambda kv: -kv[1])))
    if a.sample:
        random.seed(23)
        for m in random.sample(kept, a.sample):
            print(f"  {m['chain']:9} {m['product'][:48]:48} -> {m['nevo']:>5} {m['nevo_name'][:42]}")


if __name__ == "__main__":
    main()
