"""Stage 6: everything the app computes, as plain data, behind a disk cache.  Used by app.py.

Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources.

Every result is keyed by (function, settings, data version) and stored as a pickle in CACHE_DIR, outside git.
The data version is a hash of the data files and the model code, so new prices or a code change make old
entries unreachable; `clear_outdated()` deletes them. The cache keeps at most `limit_mb` (default 500 MB),
evicting the least recently used entries first (a hit touches the file's mtime).
"""
import csv
import dataclasses
import hashlib
import json
import os
import pickle
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

import categories as CAT
import dishes as D
import explain
import kinds as K
import lp
import meals as M
import plan as P
import profiles as PR
import supplements as S
from profiles import all_profiles, load_profile

ROOT = Path(__file__).resolve().parent
CACHE_DIR = Path(os.environ.get("NEVO_DIET_CACHE", "~/.cache/nevo-diet")).expanduser()
PR.USER_FILE = Path(os.environ.get("NEVO_DIET_PROFILES", "~/.config/nevo-diet/profiles.json")).expanduser()
SETTINGS_FILE = Path(os.environ.get("NEVO_DIET_SETTINGS", "~/.config/nevo-diet/settings.json")).expanduser()
VERSION_FILES = ["data/catalog_foods.tsv", "data/catalog_prices.tsv", "data/requirements.tsv", "data/profiles.tsv",
                 "data/dinners.tsv", "data/amino_foods.tsv", "lp.py", "plan.py", "meals.py", "dishes.py",
                 "explain.py", "profiles.py", "appcore.py", "categories.py", "cooking.py", "data/cooking.tsv",
                 "data/retention.tsv", "data/supplements.tsv", "data/supplement_prices.tsv", "supplements.py"]
EPS = 1e-7

DEFAULTS = {"profile": "avg_man", "chain": "ah", "cook_flip": [], "mode": "pure", "budget": 3.0,
            "strictness": "medium", "pattern": "brunch", "batch": True, "min3": False, "excluded": [],
            "weight": None, "height": None, "kcal": None, "protein": None,
            "my_foods": [], "food_limits": [], "no_categories": [], "no_kinds": [], "compare_ticks": False, "food_cost": 0.05,
            "fruit": 0.0, "cache_mb": 500,
            "pill_mode": "ticked", "pills_on": list(S.DEFAULT_ON), "pill_anywhere": True, "pill_prices": {}, "pill_exact": [], "food_columns": ["kcal", "protein", "fibre"], "dish_columns": ["kcal", "protein"]}
ALL_CHAINS = "all"      # pure mode only: every food at its cheapest chain
# How the chains are written for people; the data uses the keys.
CHAIN_NAMES = {"ah": "Albert Heijn", "dekamarkt": "DekaMarkt", "dirk": "Dirk", "hoogvliet": "Hoogvliet", "jumbo": "Jumbo",
               "lidl": "Lidl", "plus": "PLUS", "poiesz": "Poiesz", "spar": "Spar", "vomar": "Vomar"}
CHEAPEST = "cheapest"   # one chain, the one with the lowest price under the current settings; app.py resolves it

# Display names of the requirements (data/requirements.tsv `name`).
NICE = {"energy": "energy", "protein": "protein", "fibre": "fibre", "carbs": "carbohydrate", "fat": "fat",
        "satfat": "saturated fat", "trans": "trans fat", "linoleic": "linoleic acid", "ala": "ALA (omega-3)",
        "epa_dha": "EPA+DHA (fish fats)", "sodium": "sodium", "potassium": "potassium", "calcium": "calcium",
        "phosphorus": "phosphorus", "magnesium": "magnesium", "iron_abs": "iron (absorbed)", "iron": "iron",
        "zinc": "zinc", "copper": "copper", "iodine": "iodine", "selenium": "selenium", "vitA": "vitamin A",
        "retinol": "retinol", "thiamin": "thiamin (B1)", "riboflavin": "riboflavin (B2)", "niacin": "niacin (B3)",
        "vitB6": "vitamin B6", "folate": "folate", "folic_acid": "folic acid", "vitB12": "vitamin B12",
        "vitC": "vitamin C", "vitD": "vitamin D", "vitE": "vitamin E", "vitK1": "vitamin K1",
        "histidine": "histidine", "isoleucine": "isoleucine", "leucine": "leucine", "lysine": "lysine",
        "met_cys": "methionine+cysteine", "phe_tyr": "phenylalanine+tyrosine", "threonine": "threonine",
        "tryptophan": "tryptophan", "valine": "valine", "free_sugars": "free sugars", "fruit": "whole fruit",
        "magnesium_pills": "magnesium from pills"}
RULE_NICE = {"dinners_4": "at least 4 different dinners a week", "dinner_max2": "no dinner more than twice a week",
             "toppings_2": "at least 2 bread toppings a week", "veg_250": "250 g vegetables a day",
             "fruit_200": "200 g fruit a day"}


# Vitamins and minerals, in the order of the food coverage chart. The last four only have a maximum.
MICRO = ["potassium", "calcium", "phosphorus", "magnesium", "iron_abs", "zinc", "copper", "iodine", "selenium", "vitA",
         "thiamin", "riboflavin", "niacin", "vitB6", "folate", "vitB12", "vitC", "vitD", "vitE", "vitK1",
         "sodium", "iron", "retinol", "folic_acid"]
# Energy and macronutrients, in the order of the macro chart, with the kcal per gram requirement_rows uses.
MACRO = ["energy", "protein", "carbs", "fat", "satfat", "free_sugars", "fibre"]
KCAL_PER_G = {"protein": 4.0, "carbs": 4.0, "fat": 9.0, "satfat": 9.0, "free_sugars": 4.0}


def nice(r):
    return NICE.get(r, r)


def label(k):
    if k in S.SUPP:
        return S.name(k)
    if k == "_veg_median":
        return "vegetables sold per piece"
    f = P.FOODS.get(k)
    return f["name"] if f else k


# ---------------- settings file ----------------
def load_settings():
    s = dict(DEFAULTS)
    if SETTINGS_FILE.exists():
        s.update(json.loads(SETTINGS_FILE.read_text()))
    return s


def save_settings(s):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps({k: s[k] for k in DEFAULTS}, indent=1, ensure_ascii=False) + "\n")


# ---------------- cache ----------------
_limit = {"mb": DEFAULTS["cache_mb"]}


def set_limit(mb):
    _limit["mb"] = mb


def data_version():
    h = hashlib.sha256()
    for f in VERSION_FILES:
        st = (ROOT / f).stat()
        h.update(f"{f}:{st.st_size}:{st.st_mtime_ns}".encode())
    if PR.USER_FILE.exists():
        h.update(PR.USER_FILE.read_bytes())
    return h.hexdigest()[:12]


def cache_files():
    return sorted(CACHE_DIR.glob("*.pkl"), key=lambda p: p.stat().st_mtime) if CACHE_DIR.exists() else []


def cache_size_mb():
    return sum(p.stat().st_size for p in cache_files()) / 1e6


def evict():
    files = cache_files()
    total = sum(p.stat().st_size for p in files)
    while files and total > _limit["mb"] * 1e6:
        f = files.pop(0)
        total -= f.stat().st_size
        f.unlink(missing_ok=True)


def clear_outdated():
    v = data_version()
    n = 0
    for f in cache_files():
        if not f.name.startswith(v):
            f.unlink(missing_ok=True); n += 1
    return n


def clear_all():
    for f in cache_files():
        f.unlink(missing_ok=True)


def cached(fn):
    def path(**kw):
        key = hashlib.sha256(json.dumps([fn.__name__, kw], sort_keys=True, default=str).encode()).hexdigest()[:24]
        return CACHE_DIR / f"{data_version()}_{fn.__name__}_{key}.pkl"

    def wrapper(**kw):
        p = path(**kw)
        if p.exists():
            try:
                out = pickle.loads(p.read_bytes())
                os.utime(p)                             # most recently used
                return out
            except Exception:
                p.unlink(missing_ok=True)
        t = time.time()
        out = fn(**kw)
        out["seconds"] = time.time() - t
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        # A run that's been replaced by a newer one can still be computing the same thing: each writes its own file.
        tmp = p.with_suffix(f".{threading.get_ident()}.tmp")
        tmp.write_bytes(pickle.dumps(out))
        tmp.replace(p)
        evict()
        return out
    wrapper.__name__ = fn.__name__
    wrapper.is_cached = lambda **kw: path(**kw).exists()
    return wrapper


# ---------------- model helpers ----------------
def chains():
    return P.CHAINS


def profiles():
    return {n: load_profile(n)["label"] for n in all_profiles()}


def person(base, weight=None, height=None, kcal=None, protein=None, fruit=None):
    """What to pass as `profile`: the plain name while nothing is changed, so its cached solutions stay valid."""
    if not any((weight, height, kcal, protein, fruit)):
        return base
    return {"base": base, "weight": weight, "height": height, "kcal": kcal, "protein": protein, "fruit": fruit}


def person_info(spec):
    p = load_profile(spec)
    return {"weight": p["weight"], "height": p.get("height_cm") or (float(p["height_m"]) * 100 if p["height_m"] else None),
            "kcal": p["energy"], "protein": p["protein"]}


# ---------------- the user's own profiles and limits ----------------
def is_own(name):
    return name in PR.user_profiles()


def is_standard(name):
    return name in PR.standard_rows()


def _write_profiles(rows_):
    PR.USER_FILE.parent.mkdir(parents=True, exist_ok=True)
    PR.USER_FILE.write_text(json.dumps(rows_, indent=1, ensure_ascii=False) + "\n")


def profile_fields(name):
    """The profile's values as the form shows them, with the activity level a fixed-calories profile implies."""
    p = load_profile(name)
    pal = PR.num(p["pal"])
    if pal is None:
        pal = p["energy"] / PR.schofield(p["sex"], p["age"], p["weight"])
    return {"label": p["label"], "sex": p["sex"], "age": p["age"], "weight": p["weight"],
            "height": float(p["height_m"]) * 100 if p["height_m"] else None, "pal": pal, "kcal": PR.num(p["kcal"]),
            "protein_per_kg": PR.num(p["protein_g_per_kg"]), "source": p.get("source") or ""}


def save_profile(name, new_name=None, **changed):
    """Save the changed fields of `name`, on top of its row, as itself or as a new profile. Returns the key saved under."""
    row = dict(PR.rows_()[name])
    field = {"label": "label", "sex": "sex", "age": "age", "weight": "weight_kg", "pal": "pal", "kcal": "kcal",
             "protein_per_kg": "protein_g_per_kg", "source": "source"}
    for k, v in changed.items():
        if k == "height":
            row["height_m"] = "" if v is None else v / 100
        else:
            row[field[k]] = "" if v is None else v
    key = name
    if new_name is not None:
        slug = re.sub(r"[^a-z0-9]+", "_", new_name.lower()).strip("_") or "profile"
        rows_ = PR.rows_()
        key, i = slug, 2
        while key in rows_:
            key, i = f"{slug}_{i}", i + 1
    own = PR.user_profiles()
    own[key] = {k: v for k, v in row.items() if k != "name"}
    _write_profiles(own)
    return key


def delete_profile(name):
    """Remove the user's profile; for a standard one that puts the original back."""
    own = PR.user_profiles()
    own.pop(name, None)
    _write_profiles(own)


def limit_rows(spec):
    """One row per requirement: the current min and max, and what they are without the user's changes."""
    p = load_profile(spec)
    defaults = {r["name"]: r for r in PR.requirements({**p, "limits": {}})}
    out = []
    for r in PR.requirements(p):
        d = defaults[r["name"]]
        out.append({"key": r["name"], "nutrient": nice(r["name"]), "unit": "% of energy" if r["kind"] == "en" else r["unit"],
                    "min": PR.num(r["lower"]), "max": PR.num(r["upper"]), "standard min": PR.num(d["lower"]),
                    "standard max": PR.num(d["upper"]), "evidence": r["evidence"], "source": r["source"], "link": r["url"]})
    return out


def limit_errors(rows_):
    return [f"{r['nutrient']}: the minimum is above the maximum" for r in rows_
            if r["min"] is not None and r["max"] is not None and r["min"] > r["max"]]


def set_limits(name, rows_):
    """Keep the rows that differ from the standard values as the profile's own limits."""
    same = lambda a, b: (a is None and b is None) or (a is not None and b is not None and abs(a - b) <= 5e-4 * abs(b))
    limits = {r["key"]: {"lower": r["min"], "upper": r["max"]} for r in rows_
              if not (same(r["min"], r["standard min"]) and same(r["max"], r["standard max"]))}
    own = PR.user_profiles()
    row = own.get(name) or {k: v for k, v in PR.rows_()[name].items() if k != "name"}
    row["limits"] = limits
    if not limits:
        row.pop("limits")
    if is_standard(name) and row == {k: v for k, v in PR.standard_rows()[name].items() if k != "name"}:
        own.pop(name, None)
    else:
        own[name] = row
    _write_profiles(own)


# ---------------- your own foods and the category ticks ----------------
def own_spec(my_foods):
    """What the solvers get from the My foods box: [food, grams a day, exact?], foods gone from the catalog left out."""
    out = []
    for f in my_foods:
        if f["key"] in P.FOODS and f.get("grams"):
            out.append([f["key"], float(f["grams"]) / (7 if f.get("per") == "week" else 1), f.get("how") != "at least"])
    return sorted(out)


# ---------------- your own limits on foods and kinds ----------------
# A limit is kept in the settings as {"key": food key or KIND_PREFIX + kind, "grams": g, "per": "day" | "week"}: at most
# that much of the food, or of all the foods of that kind together. There are none by default.
KIND_PREFIX = "kind:"


def limit_target(key):
    """A limit's food or kind in words: 'Oat flakes', or 'pasta and noodles (kind, 14 foods)'."""
    if key.startswith(KIND_PREFIX):
        kind = key[len(KIND_PREFIX):]
        return f"{kind} (kind, {K.COUNT.get(kind, 0)} foods)"
    return label(key)


def limit_name(key):
    """The limit's name as a requirement row: what the nutrient tables, the price split and the messages call it."""
    return f"limit: {key[len(KIND_PREFIX):]} (kind)" if key.startswith(KIND_PREFIX) else f"limit: {label(key)}"


def limit_choices():
    """{key: text} for the Limits search: every kind of food, then every food (supplements have no grams)."""
    kinds = {KIND_PREFIX + k: f"kind: {k} ({K.COUNT[k]} foods)" for k in K.KINDS if k != "supplements"}
    foods = {k: label(k) for k in sorted(P.FOODS, key=lambda k: label(k).lower())}
    return {**kinds, **foods}


def limit_spec(food_limits):
    """What the solvers get from the Limits box: [name, food keys, grams a day], a limit on a food or kind that's gone
    from the catalog left out. Sorted, so the same limits give the same cache key."""
    out = []
    for f in food_limits:
        key, g = f["key"], f.get("grams")
        if g is None:
            continue
        members = K.members([key[len(KIND_PREFIX):]]) if key.startswith(KIND_PREFIX) else {key}
        members = sorted(members & set(P.FOODS))
        if members:
            out.append([limit_name(key), members, float(g) / (7 if f.get("per") == "week" else 1)])
    return sorted(out)


def at_limit(m, x):
    """The foods in this diet that sit at one of your limits (theirs or their kind's): the plan wants more of them."""
    out = set()
    for r in m.reqs:
        if r["kind"] != "food":
            continue
        a = m.N[r["cols"]]
        if a @ x >= float(r["upper"]) * (1 - 1e-6) - 1e-6:
            out |= {m.keys[i] for i in np.flatnonzero((a > 0) & (x > EPS))}
    return out


def effective_excluded(excluded, no_cats, own=()):
    """Your single ✗ marks plus everything the ticks remove. Your own foods stay in, whatever these say."""
    return sorted((set(excluded) | CAT.members(no_cats)) - {o[0] for o in own})


def categories(allergies=False):
    return [{"key": k, "label": lab, "covers": covers, "n": len(CAT.members([k]))}
            for k, lab, covers in (CAT.ALLERGIES if allergies else CAT.CATEGORIES)]


def own_conflicts(own, no_cats):
    """{your own food: 'gluten, soy'}: allergy ticks that one of your own foods goes against. Your food stays, but you should know."""
    ticked = set(no_cats) & CAT.ALLERGY_KEYS
    hit = CAT.removed_by(ticked)
    return {o[0]: hit[o[0]] for o in own if o[0] in hit}


def removed_by(no_cats):
    return CAT.removed_by(no_cats)


def food_choices(chain):
    """{food: name} for the My foods search, by name; foods this chain doesn't sell say so."""
    _prices()
    by = _PR["by"]              # not prices_of(): that checks the data version, and this asks 1,200 times per page
    def name(k):
        away = chain != ALL_CHAINS and not any(r["chain"] == chain for r in by.get(k, ()))
        return label(k) + (f" (⚠ not at {chain})" if away else "")
    return {k: name(k) for k in sorted((k for k in P.FOODS if by.get(k)), key=label)}


def product_of(k, chain):
    """(price row of the cheapest product of this food at the chain, else anywhere; was it elsewhere?)"""
    prods = prices_of(k)
    here = [r for r in prods if chain == ALL_CHAINS or r["chain"] == chain]
    best = min(here or prods, key=lambda r: float(r["eur_per_100g"]), default=None)
    return best, bool(best) and not here


def compare(now, before, own):
    """What changed between two plans: a row per food whose amount or cost moved, your own foods first."""
    mine = {o[0] for o in own}
    rows_ = []
    for k in {*now["grams"], *before["grams"]}:
        g1, g0 = now["grams"].get(k, 0.0), before["grams"].get(k, 0.0)
        e1, e0 = now["eur"].get(k, 0.0), before["eur"].get(k, 0.0)
        if abs(g1 - g0) >= 1 or abs(e1 - e0) >= 0.005:
            rows_.append({"": "★" if k in mine else "", "food": label(k), "before": g0, "now": g1, "change": g1 - g0,
                          "€/day change": e1 - e0, "_mine": k in mine})
    rows_.sort(key=lambda r: (not r["_mine"], -abs(r["change"])))
    return [{k: v for k, v in r.items() if k != "_mine"} for r in rows_]


def compare_dinners(now, before):
    """Dinners whose number of evenings changed."""
    d1, d0 = ({d["dinner"]: d["evenings"] for d in r["dinners"]} for r in (now, before))
    return [{"dinner": d, "evenings before": d0.get(d, 0), "evenings now": d1.get(d, 0)}
            for d in sorted({*d0, *d1}) if d0.get(d, 0) != d1.get(d, 0)]


def _misses(m, x):
    """The limits this diet breaks, in words: what stands in the way of a real plan."""
    out = []
    for r in requirement_rows(m, totals_of(m, x)):
        if not r["ok"]:
            low = r["lower"] is not None and r["intake"] < r["lower"]
            out.append({"nutrient": r["nutrient"], "unit": r["unit"], "intake": r["intake"],
                        "side": "minimum" if low else "maximum", "limit": r["lower"] if low else r["upper"]})
    return out


def why_not(m, own):
    """No adequate diet: which limits stand in the way, and how much of each of your foods would still work.
    The limits come from the diet that misses them by the least (each miss relative to its limit, an LP)."""
    if not (m.unit_g > 0).any():              # no food left (supplements alone can't make a diet)
        return {"misses": [], "amounts": [], "empty": True}
    G, h, _ = lp.rows(m)
    n, k = G.shape[1], G.shape[0]
    energy = next((float(r["lower"]) for r in m.reqs if r["name"] == "energy" and r["lower"]), 2000.0)
    scale = np.where(np.abs(h) > 0, np.abs(h), energy)                # energy-share rows have h = 0 and are in kcal
    res = linprog(np.r_[1e-6 * m.c, 1 / scale], A_ub=np.hstack([G, -np.eye(k)]), b_ub=h,
                  bounds=list(zip(m.lb, m.cap)) + [(0, None)] * k, method="highs")
    amounts = []
    for key, wanted, _exact in own:
        if key not in m.keys:
            continue
        i = m.keys.index(key)
        lb, cap = m.lb.copy(), m.cap.copy()
        lb[i], cap[i] = 0.0, np.inf
        e = np.zeros(n)
        e[i] = 1
        most = linprog(-e, A_ub=G, b_ub=h, bounds=list(zip(lb, cap)), method="highs")
        least = linprog(e, A_ub=G, b_ub=h, bounds=list(zip(lb, cap)), method="highs")
        amounts.append({"key": key, "food": label(key), "wanted": wanted,
                        "most": -most.fun * 100 if most.status == 0 else None,
                        "least": least.fun * 100 if least.status == 0 else None})
    return {"misses": _misses(m, res.x[:n]) if res.status == 0 else [], "amounts": amounts}


def why_not_week(mm, info, pk, chain, pattern, strictness, batch, own):
    """The same for a week of meals. This takes up to half a minute per question: the path to an error message only."""
    lay = M.closest_week(mm, info, pk, chain, pattern, strictness, no_batch=not batch)
    amounts = []
    for key, wanted, _exact in own:
        if key in mm.keys:
            most = M.most_of(mm, info, pk, chain, mm.keys.index(key), pattern, strictness, no_batch=not batch)
            amounts.append({"key": key, "food": label(key), "wanted": wanted, "most": most, "least": None})
    return {"misses": _misses(mm, _week_intake(mm, info, lay)) if lay else [], "amounts": amounts, "n_dinners": len(info),
            "rules": lay is None}


def _week_intake(mm, info, lay):
    """Grams (units) a day of every food and dish in a solved week, for the nutrient totals."""
    x = np.zeros(len(mm.keys))
    for i in lay["active"]:
        x[i] = M.val(lay, ("y", i)) / 7
    for j in range(len(info)):
        x[lay["n_food"] + j] = M.val(lay, ("G", j)) / 7
    return x


_HOW = {}


def cook_info():
    """{key: cooking.info(...)} for every food in the catalog: the default tick, and whether it can be cooked at all."""
    if not _HOW:
        _HOW.update(lp.load(chain=None).how)
    return _HOW


def cook_state(m, k):
    """For the tables: (True cooked / False raw / None no choice, a must-cook food counted raw?)."""
    h = m.how.get(k)
    if not h or not h.cookable:
        return None, False
    return k in m.cooked, h.default == "must" and k not in m.cooked


def raw_but_must(flip):
    """The foods you set to raw that are meant to be cooked (raw meat, frozen vegetables, dried pulses ...)."""
    how = cook_info()
    return sorted((k for k in flip if k in how and how[k].cookable and how[k].default == "must" and how[k].ticked),
                  key=label)


def model(profile, chain, cooked, excluded=(), min3=False, own=(), flip=(), limits=(), pills=None):
    return lp.load(drop=tuple(excluded), cooked=cooked, flip=frozenset(flip), chain=None if chain == ALL_CHAINS else chain,
                   min_chains=3 if min3 else 0, profile=profile, own=own, limits=limits,
                   pills=pills)


def requirement_rows(m, totals):
    """Per requirement: intake, lower/upper, % of the binding side, ok flag. Energy-share rows in en%."""
    out = []
    for r in m.reqs:
        val, unit = totals[r["name"]], r["unit"]
        lo = float(r["lower"]) if r["lower"] else None
        hi = float(r["upper"]) if r["upper"] else None
        if r["kind"] == "en":
            e = 4.0 if r["cols"] in ("CHO", "PROT", "NVSUGAF") else 9.0
            val = 100 * e * val / totals["energy"] if totals["energy"] else 0.0
            unit = "% of energy"
        if lo is None and hi is None:
            continue
        ok = (lo is None or val >= lo * (1 - 1e-3)) and (hi is None or val <= hi * (1 + 1e-3))
        out.append({"name": r["name"], "nutrient": nice(r["name"]), "unit": unit, "intake": val, "lower": lo,
                    "upper": hi, "pct_lower": 100 * val / lo if lo else None,
                    "pct_upper": 100 * val / hi if hi else None, "ok": ok, "kind": r["kind"]})
    return out


def totals_of(m, x):
    return {r["name"]: float(sum(m.N[c] for c in r["cols"].split("+")) @ x) for r in m.reqs}


def food_coverage(m, x, names=None):
    """Per micronutrient with a limit and food in the diet: the amount that food gives and its % of the minimum (of the
    maximum for nutrients that only have one). A full grid: every food x every nutrient, zeros included, so a nutrient
    the diet has none of still gets its column in the chart and its rows in the table."""
    reqs = {r["name"]: r for r in m.reqs}
    out = []
    for n in MICRO:
        r = reqs[n]
        if not (r["lower"] or float(r["upper"] or 0)):
            continue
        side, ref = ("minimum", float(r["lower"])) if r["lower"] else ("maximum", float(r["upper"]))
        a = sum(m.N[c] for c in r["cols"].split("+")) * x
        for i in np.flatnonzero(x > EPS):
            out.append({"food": (names or {}).get(m.keys[i], label(m.keys[i])), "nutrient": nice(n), "side": side,
                        "amount": float(a[i]), "unit": r["unit"], "pct": float(100 * a[i] / ref),
                        "total_pct": float(100 * a.sum() / ref)})
    return out


def macro_split(m, x, names=None):
    """Per macronutrient and food in the diet: the amount that food gives and its share of the day's total. For the
    energy-giving ones also the % of the day's energy it brings (KCAL_PER_G, as in requirement_rows). A full grid, zeros
    included: a macro the diet has none of (free sugars, often) keeps its column, with a share of 0 for every food."""
    reqs = {r["name"]: r for r in m.reqs}
    kcal = float(m.N["ENERCC"] @ x)
    out = []
    for n in MACRO:
        r = reqs[n]
        a = sum(m.N[c] for c in r["cols"].split("+")) * x
        tot = float(a.sum())
        e = KCAL_PER_G.get(n)
        for i in np.flatnonzero(x > EPS):
            out.append({"food": (names or {}).get(m.keys[i], label(m.keys[i])), "nutrient": nice(n),
                        "amount": float(a[i]), "unit": r["unit"], "pct": float(100 * a[i] / tot) if tot > 0 else 0.0,
                        "day_total": tot, "pct_energy": float(100 * e * a[i] / kcal) if e and kcal else None})
    return out


def binding_sides(m, res, G, h, lab):
    """[(requirement, 'lo' | 'hi')] for the limits that set the price: tight, with a shadow price."""
    slack = h - G @ res.x
    return sorted({(name, side) for j, (name, side) in enumerate(lab) if slack[j] < 1e-6 * max(1, abs(h[j]))
                   and abs(res.ineqlin.marginals[j]) > 1e-9})


def binding_names(m, res, G, h, lab):
    return sorted({name for name, _side in binding_sides(m, res, G, h, lab)})


_PR = {}


def _prices():
    v = data_version()
    if _PR.get("v") != v:
        _PR["v"], _PR["rows"] = v, list(csv.DictReader(open(ROOT / "data/catalog_prices.tsv"), delimiter="\t"))
        by = {}
        for r in _PR["rows"]:
            by.setdefault(r["key"], []).append(r)
        _PR["by"] = by
    return _PR["rows"]


def prices_of(k):
    _prices()
    return _PR["by"].get(k, [])


# ---------------- pure LP ----------------
def _bare(m, res, food_cost):
    """What the cost per food does: the plain LP's price and number of foods, next to this basket's."""
    plain = lp.solve(m)[0] if food_cost else res
    return {"cost": float(plain.fun), "n": int((plain.x > EPS).sum())}


@cached
def pure(profile, chain, cooked, excluded, min3, own=(), flip=(), limits=(), food_cost=0.0, pills=None):
    m = model(profile, chain, cooked, excluded, min3, own, flip, limits, pills)
    mine = {o[0] for o in own}
    res, G, h, lab = lp.solve_few(m, food_cost)
    if res.status != 0:
        return {"ok": False, "message": res.message, "why": why_not(m, own)}
    x = res.x
    grams = x * m.unit_g
    capped = at_limit(m, x)
    basket = []
    for i in np.argsort(-(x * m.c)):
        if x[i] <= EPS:
            continue
        k = m.keys[i]
        best, away = product_of(k, chain)
        cook, warn = cook_state(m, k)
        basket.append({"key": k, "food": label(k), "group": m.groups[i], "mine": k in mine, "away": away,
                       "cook": cook, "raw_warn": warn,
                       "amount": f"{grams[i]:.0f} g" if m.unit_g[i] else pill_amount(m, i, x[i]),
                       "g_day": float(grams[i]), "eur_day": float(x[i] * m.c[i]),
                       "at_limit": k in capped,
                       "product": best["product"] if best else pill_product(m, k),
                       "chain": best["chain"] if best else pill_shop(m, k),
                       "n_chains": int(P.FOODS[k]["n_chains"]) if k in P.FOODS else None})
    split = explain.price_split(m, res, G, lab)
    shares = []
    for i, s in split.items():
        if m.keys[i] in mine:                # it's in the basket because you put it there, not because of what it pays for
            continue
        for req, eur in s["shares"].items():
            shares.append({"food": label(m.keys[i]), "nutrient": nice(req), "eur_per_100g": eur,
                           "price": s["price"]})
        if s["cap_rent"] > 1e-9:
            shares.append({"food": label(m.keys[i]), "nutrient": "cap rent", "eur_per_100g": -s["cap_rent"],
                           "price": s["price"]})
    lam = res.ineqlin.marginals
    outside = m.c - G.T @ lam        # below 0: it would lower the price, but by less than the cost of adding a food
    shadow = {}
    for j, (name, side) in enumerate(lab):
        if abs(lam[j]) > 1e-12:
            shadow[name] = shadow.get(name, 0.0) + float(-lam[j])
    return {"ok": True, "cost": float(res.fun), "basket": basket, "reqs": requirement_rows(m, totals_of(m, x)),
            "by_food": food_coverage(m, x), "macros": macro_split(m, x), "binding": binding_names(m, res, G, h, lab),
            "binding_sides": binding_sides(m, res, G, h, lab), "shares": shares, "shadow": shadow,
            "rc": {m.keys[i]: float(res.lower.marginals[i] if x[i] > EPS else outside[i]) for i in range(len(m.keys))},
            "grams": {m.keys[i]: float(grams[i]) for i in range(len(m.keys)) if x[i] > EPS},
            "eur": {m.keys[i]: float(x[i] * m.c[i]) for i in range(len(m.keys)) if x[i] > EPS},
            "own_eur": sum(float(x[i] * m.c[i]) for i in range(len(m.keys)) if m.keys[i] in mine),
            "units": {k: float(x[i]) for i, k in enumerate(m.keys) if k in m.pills and x[i] > EPS},
            "free_pills": free_pills(m, x),
            "n_foods": len(m.keys), "bare": _bare(m, res, food_cost)}


@cached
def removal(profile, chain, cooked, excluded, min3, own=(), flip=(), limits=(), pills=None):
    m = model(profile, chain, cooked, excluded, min3, own, flip, limits, pills)
    nodes = explain.removal_tree(m, depth=3, branch=3)
    out = []
    for n in nodes:
        out.append({"path": [label(k) for k in n["path"]], "depth": len(n["path"]),
                    "infeasible": n["infeasible"], "same_as": [label(k) for k in n["same_as"]] if n.get("same_as") else None,
                    "cost": n.get("cost"), "delta": n.get("delta"),
                    "replaced_by": [(label(k), float(g)) for k, g in n.get("replaced_by", [])]})
    return {"nodes": out}


@cached
def cost_curve(profile, chain, cooked, excluded, min3, req, own=(), flip=(), limits=(), pills=None, steps=(1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0)):
    m = model(profile, chain, cooked, excluded, min3, own, flip, limits, pills)
    r = next(r for r in m.reqs if r["name"] == req)
    lo, hi = r["lower"], r["upper"]
    pts = []
    for f in steps:
        new_lo = float(lo) * f
        new_hi = hi if not hi or float(hi) >= new_lo else ""          # a pushed-up minimum may pass the maximum
        res, *_ = lp.solve(m, overrides={req: (new_lo, new_hi)})
        pts.append({"nutrient": nice(req), "pct": 100 * f, "level": new_lo, "unit": r["unit"],
                    "cost": float(res.fun) if res.status == 0 else None,
                    "upper_dropped": bool(hi) and new_hi == ""})
    return {"points": pts}


@cached
def wiggle(profile, chain, cooked, excluded, min3, own=(), flip=(), limits=(), pills=None, slack=0.05, min_g=1.0):
    """Flux-variability ranges: min and max grams of each food over all diets within `slack` of the optimum.

    Which foods can be skipped follows from duality: for any adequate diet x, cost(x) - optimum >= rc_i * x_i (every
    other term of the gap is >= 0), so within the slack food i takes at most slack * optimum / rc_i units. A food is
    only left out when that bound is under `min_g` grams. (Before 2026-11-09 this skipped every food with rc_i above the
    slack itself, which silently assumed it would enter at 100 g: foods that fit in at 20-90 g were missing.)
    A food outside the cheapest diet has 0 as its minimum (the cheapest diet itself is within the slack), so it only
    needs the maximising LP."""
    m = model(profile, chain, cooked, excluded, min3, own, flip, limits, pills)
    res, G, h, lab = lp.solve(m)
    if res.status != 0:
        return {"rows": []}
    x, rc = res.x, res.lower.marginals
    Gc, hc = np.vstack([G, m.c]), np.append(h, (1 + slack) * res.fun)
    bounds = list(zip(m.lb, m.cap))
    rows_ = []
    for i, k in enumerate(m.keys):
        f = m.unit_g[i] or 1
        if x[i] < EPS and rc[i] > 0 and slack * res.fun / rc[i] * f < min_g:
            continue
        e = np.zeros(len(m.keys)); e[i] = 1
        b = linprog(-e, A_ub=Gc, b_ub=hc, bounds=bounds, method="highs")
        if b.status != 0 or -b.fun * f < min_g:
            continue
        lo = 0.0
        if x[i] > EPS:
            a = linprog(e, A_ub=Gc, b_ub=hc, bounds=bounds, method="highs")
            lo = float(a.fun * f) if a.status == 0 else 0.0
        rows_.append({"food": label(k), "group": m.groups[i], "min": lo, "max": float(-b.fun * f), "opt": float(x[i] * f),
                      "unit": "g" if m.unit_g[i] else S.SUPP[k]["unit"], "in_diet": bool(x[i] > EPS)})
    return {"rows": rows_, "slack": slack}


@cached
def worth(profile, chain, cooked, excluded, min3, own=(), flip=(), limits=(), pills=None):
    """Every food's price next to what it is worth to this diet, at the plain LP's shadow prices: worth_i = sum over the
    requirements of shadow price x the food's content (a maximum counts against it). Dual feasibility says no food is
    worth more than it costs (reduced cost = price - worth >= 0), and complementary slackness that the foods in the diet
    are worth exactly their price. Per 100 g; supplements (priced per tablet) are left out."""
    m = model(profile, chain, cooked, excluded, min3, own, flip, limits, pills)
    res, G, h, lab = lp.solve(m)
    if res.status != 0:
        return {"rows": [], "cost": None}
    w = G.T @ res.ineqlin.marginals
    rows_ = []
    for i, k in enumerate(m.keys):
        if not m.unit_g[i]:
            continue
        rows_.append({"food": label(k), "group": m.groups[i], "price": float(m.c[i]), "worth": float(w[i]),
                      "reduced_cost": float(m.c[i] - w[i]), "g_day": float(res.x[i] * 100),
                      "in_diet": bool(res.x[i] > EPS), "mine": bool(m.lb[i] > 0)})
    return {"rows": rows_, "cost": float(res.fun)}


@cached
def limit_costs(profile, chain, cooked, excluded, min3, own=(), flip=(), limits=(), pills=None, step=0.10):
    """What each limit that sets the price costs: the plain LP solved again with that one limit 10% looser and 10%
    stricter (a minimum x0.9 / x1.1, a maximum x1.1 / x0.9). Exact, not the shadow-price estimate, which only holds
    for small steps; `estimate` is that linear estimate, for comparison. A stricter minimum that passes the maximum
    drops the maximum, as in cost_curve."""
    m = model(profile, chain, cooked, excluded, min3, own, flip, limits, pills)
    res, G, h, lab = lp.solve(m)
    if res.status != 0:
        return {"rows": []}
    base = float(res.fun)
    lam = res.ineqlin.marginals
    slack = h - G @ res.x
    reqs = {r["name"]: r for r in m.reqs}
    totals = totals_of(m, res.x)
    kcal = totals["energy"]
    rows_ = []
    for j, (name, side) in enumerate(lab):
        if side not in ("lo", "hi") or abs(lam[j]) < 1e-9 or slack[j] > 1e-6 * max(1, abs(h[j])):
            continue
        r = reqs[name]
        lo, hi = (float(r["lower"]) if r["lower"] else None), (float(r["upper"]) if r["upper"] else None)
        level = lo if side == "lo" else hi
        out = {}
        for how, f in (("looser", 1 - step if side == "lo" else 1 + step), ("stricter", 1 + step if side == "lo" else 1 - step)):
            new_lo, new_hi = (level * f, hi) if side == "lo" else (lo, level * f)
            if new_lo is not None and new_hi is not None and new_lo > new_hi:
                new_lo, new_hi = (new_lo, None) if side == "lo" else (None, new_hi)
            r2, *_ = lp.solve(m, overrides={name: ("" if new_lo is None else new_lo, "" if new_hi is None else new_hi)})
            out[how] = float(r2.fun) - base if r2.status == 0 else None
        # d cost / d level = shadow price (per unit; for an en% limit per percentage point: shadow x kcal / 100)
        per_unit = -lam[j] * (kcal / 100 if r["kind"] == "en" else 1.0)
        rows_.append({"nutrient": nice(name), "side": "minimum" if side == "lo" else "maximum", "level": level,
                      "unit": "% of energy" if r["kind"] == "en" else r["unit"],
                      "looser": out["looser"], "stricter": out["stricter"], "estimate": float(per_unit * step * level)})
    rows_.sort(key=lambda r: -(r["stricter"] if r["stricter"] is not None else 1e9))
    return {"rows": rows_, "cost": base, "step": step}


def _ranked(rows_):
    """Cheapest first, chains without a plan last. best: the chain to shop at, None if no chain has a plan."""
    rows_.sort(key=lambda r: (r["cost"] is None, r["cost"] or 0.0, r["chain"]))
    return {"rows": rows_, "best": rows_[0]["chain"] if rows_[0]["cost"] is not None else None}


@cached
def chain_prices(profile, cooked, excluded, min3, own=(), flip=(), limits=(), food_cost=0.0, pills=None):
    """The pure LP at every chain, for the "cheapest" option."""
    rows_ = []
    for ch in chains():
        res, *_ = lp.solve_few(model(profile, ch, cooked, excluded, min3, own, flip, limits, pills), food_cost)
        rows_.append({"chain": ch, "cost": float(res.fun) if res.status == 0 else None})
    return _ranked(rows_)


# ---------------- realistic: a week of meals ----------------
@cached
def realistic(profile, chain, cooked, excluded, strictness, pattern, batch, no_cats=(), own=(), food_cost=0.0, flip=(), limits=(),
              pills=None):
    """excluded: your single ✗ marks; no_cats: the category ticks. A tick that follows ingredients removes the foods and
    every dinner with them. A cooking basic (oil, salt ...) is only no longer eaten as such: dinners keep their spoonful."""
    hard = effective_excluded(excluded, set(no_cats) & CAT.FOLLOWS_INGREDIENTS, own)
    m = lp.load(drop=tuple(hard), cooked=cooked, chain=chain, min_chains=0, profile=profile, own=own,
                flip=frozenset(flip), limits=limits, pills=pills)
    if not (m.unit_g > 0).any():
        return {"ok": False, "message": "no foods left", "why": {"misses": [], "amounts": [], "empty": True}}
    for k in CAT.basics_in_dinners(no_cats) - {o[0] for o in own}:
        if k in m.keys:
            m.cap[m.keys.index(k)] = 0.0
    mm, info = M.dish_model(m, chain, pattern, no_cats)
    pk = P.packs(chain)
    mine = {o[0] for o in own}
    lay = M.solve_week(mm, info, pk, chain, pattern, strictness, no_batch=not batch, food_cost=food_cost)
    if lay is None:
        return {"ok": False, "message": "no feasible week with these settings",
                "why": why_not_week(mm, info, pk, chain, pattern, strictness, batch, own)}
    val = lambda k: M.val(lay, k)
    dinners = []
    for j, d in enumerate(info):
        k = round(val(("k", j)))
        if k:
            g = val(("G", j)) * 100 / k
            dinners.append({"dinner": d["note"], "nevo_dish": f"{d['name']} (NEVO {d['code']})", "evenings": k,
                            "g_per_evening": g, "hands_on_min": d["min"], "kind": d["role"],
                            "eur_portion": g / 100 * d["price"]})
    x_all = _week_intake(mm, info, lay)            # grams a day of every food and dish, for the nutrient totals
    capped = at_limit(mm, x_all)
    direct = []
    for i in sorted(lay["direct"], key=lambda i: -val(("y", i))):
        y = val(("y", i))
        if y > 1e-4:
            cook, warn = cook_state(m, mm.keys[i])
            direct.append({"key": mm.keys[i], "cook": cook, "raw_warn": warn, "at_limit": mm.keys[i] in capped,
                           "food": label(mm.keys[i]) + (" ★" if mm.keys[i] in mine else ""),
                           "amount": f"{y*100/7:.0f} g" if mm.unit_g[i] else
                           pill_amount(mm, i, y / 7, week=True), "g_day": y * 100 / 7 if mm.unit_g[i] else 0.0, "group": mm.groups[i]})
    shop, grams, eur_day = [], {}, {}
    for i in lay["active"]:
        u = val(("y", i)) + sum(d["leaves"].get(mm.keys[i], 0) * val(("G", j)) for j, d in enumerate(info))
        if u < 1e-4:
            continue
        k = mm.keys[i]
        if not mm.unit_g[i]:
            o = mm.pills[k]["offer"]
            shop.append({"product": pill_product(mm, k) + (f" ({o['units']} × {S.SUPP[k]['unit']})" if o else ""),
                         "food": label(k), "buy": f"{u:.0f} a week" + (f", 1 pack per {o['units'] / u:.0f} weeks" if o else ""),
                         "eur_week": u * mm.c[i]})
            eur_day[k] = shop[-1]["eur_week"] / 7
            continue
        grams[k] = u * 100 / 7
        if k not in pk:                        # one of your own foods that this chain doesn't sell
            best, _ = product_of(k, chain)
            shop.append({"product": f"{best['product']} (⚠ at {best['chain']})", "food": label(k),
                         "buy": f"{u*100:.0f} g/week", "eur_week": u * mm.c[i]})
            eur_day[k] = shop[-1]["eur_week"] / 7
            continue
        g, eur, prod, pg = pk[k]
        if lay["kind"][i] == "pantry":
            weeks = g / (u * 100) if u else 0
            shop.append({"product": f"{prod} ({pg:.0f} g, €{eur:.2f})", "food": label(k),
                         "buy": f"1 pack per {weeks:.1f} weeks ({u*100:.0f} g/week)", "eur_week": u * mm.c[i]})
        else:
            n, L = round(val(("n", i))), lay["kind"][i]
            shop.append({"product": f"{prod} ({pg:.0f} g, €{eur:.2f})", "food": label(k),
                         "buy": f"{n} every {'week' if L == 1 else f'{L} weeks'}", "eur_week": n * eur / L})
        eur_day[k] = shop[-1]["eur_week"] / 7
    vm = sum(d["leaves"].get("_veg_median", 0) * val(("G", j)) for j, d in enumerate(info))
    if vm > 1e-4:
        vegmed = D.veg_median(D.catalog(chain)) or 0
        shop.append({"product": "vegetables sold per piece (celery, cucumber, courgette ...)",
                     "food": "dish ingredients", "buy": f"{vm*100:.0f} g/week", "eur_week": vm * vegmed})
        grams["_veg_median"], eur_day["_veg_median"] = vm * 100 / 7, vm * vegmed / 7
    shop.sort(key=lambda r: -r["eur_week"])
    # rule savings: each bent rule made hard on its own
    bent = []
    for b in lay["broken"]:
        f = M.solve_week(mm, info, pk, chain, pattern, strictness, forced={b: 0}, no_batch=not batch, food_cost=food_cost)
        bent.append({"rule": RULE_NICE.get(b, b), "saving_day": (f["cost"] - lay["cost"]) / 7 if f else None})
    return {"ok": True, "cost": lay["cost"] / 7, "dinners": dinners, "direct": direct, "shop": shop,
            "reqs": requirement_rows(mm, totals_of(mm, x_all)),
            "by_food": food_coverage(mm, x_all, {d["key"]: d["note"] for d in info}),
            "macros": macro_split(mm, x_all, {d["key"]: d["note"] for d in info}), "bent": bent, "n_dishes": len(info),
            "grams": grams, "eur": eur_day, "own_eur": sum(e for k, e in eur_day.items() if k in mine),
            "mip_seconds": lay["seconds"],
            "units": {mm.keys[i]: val(("y", i)) / 7 for i in lay["direct"] if mm.keys[i] in mm.pills and val(("y", i)) > 1e-4},
            "free_pills": [label(mm.keys[i]) for i in lay["direct"] if mm.keys[i] in mm.pills and mm.pills[mm.keys[i]]["free"]
                           and val(("y", i)) > 1e-4]}


@cached
def week_prices(profile, cooked, excluded, strictness, pattern, batch, no_cats=(), own=(), food_cost=0.0, flip=(), limits=(),
                pills=None):
    """The realistic week at every chain, for the "cheapest" option. Packs and dinners differ per chain, so the pure LP's
    ranking doesn't settle this one. Ranked on the price shown; `bent` says how many meal rules that price bends."""
    rows_ = []
    for ch in chains():
        r = realistic(profile=profile, chain=ch, cooked=cooked, excluded=excluded, strictness=strictness, pattern=pattern,
                      batch=batch, no_cats=no_cats, own=own, food_cost=food_cost, flip=flip, limits=limits, pills=pills)
        rows_.append({"chain": ch, "cost": r["cost"] if r["ok"] else None, "bent": len(r["bent"]) if r["ok"] else None})
    return _ranked(rows_)


# ---------------- supplements ----------------
def pill_spec(mode, on, anywhere, prices, exact):
    """What the solvers get from the Supplements page (supplements.spec). exact: [{"key", "n", "per": "day" | "week"}]."""
    return S.spec(mode, on, anywhere, prices, [[e["key"], float(e["n"]) / (7 if e.get("per") == "week" else 1)]
                                               for e in exact if e.get("n")])


def pill_amount(m, i, per_day, week=False):
    """'0.40 tablet a day (2.8 a week)' in the pure LP; '3 tablets a week' in the realistic week (whole units)."""
    unit, wk = S.SUPP[m.keys[i]]["unit"], 7 * per_day
    if week:
        return f"{wk:.0f} {unit}{'' if round(wk) == 1 else 's'} a week"
    return f"{per_day:.2f} {unit} a day ({wk:.1f} a week)"


def pill_product(m, k):
    p = m.pills.get(k)
    if not p:
        return S.name(k)
    if p["yours"]:
        return "your price"
    return p["offer"]["product"] if p["offer"] else "⚠ no price: counted as free"


def pill_shop(m, k):
    p = m.pills.get(k)
    return S.shop_name(p["offer"]["shop"]) if p and p["offer"] and not p["yours"] else ""


def free_pills(m, x):
    """The supplements in this diet that have no price (counted as free)."""
    return [label(k) for i, k in enumerate(m.keys) if k in m.pills and m.pills[k]["free"] and x[i] > EPS]


def supplement_rows(spec, chain, units=None, savings=None):
    """The Supplements page's table: every supplement with its price at this chain (or anywhere), whether the plan may use
    it, and how much of it the plan takes (units: {key: units a day}). savings: {key: € a day} from pill_savings."""
    chosen = {p["key"]: p for p in S.choose(spec, None if chain == ALL_CHAINS else chain)}
    exact = dict(spec["exact"])
    out = []
    for k, s in S.SUPP.items():
        price, offer, yours = S.price_of(k, spec, None if chain == ALL_CHAINS else chain)
        n = (units or {}).get(k, 0.0)
        out.append({"key": k, "supplement": s["name"], "type": s["type"], "contents": S.contents(k), "unit": s["unit"],
                    "€/unit": price, "yours": yours, "free": price is None,
                    "product": "your price" if yours else offer["product"] if offer else "",
                    "shop": "" if yours or not offer else S.shop_name(offer["shop"]),
                    "pack": f"{offer['units']} for €{offer['price']:.2f}" if offer else "",
                    "allowed": k in chosen, "ticked": k in spec["on"], "exact": exact.get(k),
                    "per_week": 7 * n, "eur_day": n * (price or 0.0),
                    "saves": (savings or {}).get(k), "note": s["note"]})
    return out


@cached
def pill_savings(profile, chain, cooked, excluded, min3, own=(), flip=(), limits=(), pills=None):
    """What each supplement is worth to the plain LP: the cost without it minus the cost with it, the others as they are.
    For one the plan may not use yet: what ticking it would save (at its price; no price = free). For one it may use:
    what it saves now (0 if the plan doesn't take it). Supplements at an exact amount are yours to set: None."""
    spec = pills or S.DEFAULT
    m = model(profile, chain, cooked, excluded, min3, own, flip, limits, {**spec, "mode": "all", "on": []})
    allowed = {p["key"] for p in S.choose(spec, None if chain == ALL_CHAINS else chain)}
    exact = dict(spec["exact"])
    base_cap = np.array([m.cap[i] if (k not in m.pills or k in allowed or k in exact) else 0.0
                         for i, k in enumerate(m.keys)])

    def cost(cap):
        res, *_ = lp.solve(dataclasses.replace(m, cap=cap))
        return float(res.fun) if res.status == 0 else None

    base = cost(base_cap)
    out = {}
    for i, k in enumerate(m.keys):
        if k not in m.pills or k in exact:
            continue
        cap = base_cap.copy()
        cap[i] = 0.0 if k in allowed else np.inf
        other = cost(cap)
        if base is None or other is None:
            out[k] = None
        else:
            out[k] = (other - base) if k in allowed else (base - other)
    return {"base": base, "saves": out}


# ---------------- foods and dishes tables ----------------
FOOD_COLS = {"kcal": ("ENERCC", "kcal"), "protein": ("PROT", "g"), "fat": ("FAT", "g"), "carbs": ("CHO", "g"),
             "fibre": ("FIBT", "g"), "sat. fat": ("FASAT", "g"), "sodium": ("NA", "mg"), "calcium": ("CA", "mg"),
             "iron": ("FE", "mg"), "absorbed iron": ("FE_ABS", "mg"), "zinc": ("ZN", "mg"), "iodine": ("ID", "µg"),
             "vitamin A": ("VITA_RAE", "µg"), "vitamin B12": ("VITB12", "µg"), "vitamin C": ("VITC", "mg"),
             "vitamin D": ("VITD", "µg"), "folate": ("FOL", "µg"), "potassium": ("K", "mg"),
             "magnesium": ("MG", "mg"), "selenium": ("SE", "µg"), "lysine": ("AA_LYS", "mg")}


@cached
def foods_table(profile, chain, cooked, min3, keep=(), flip=()):
    """Every food in the catalog (excluded ones too, so they can be put back): prices and nutrients per 100 g.
    keep: your own foods, listed even if this chain doesn't sell them."""
    m = model(profile, chain, cooked, (), min3, [[k, 0.0, False] for k in keep], flip)
    out = []
    for i, k in enumerate(m.keys):
        if not m.unit_g[i]:                     # a supplement: on the Supplements page
            continue
        best, away = product_of(k, chain)
        cook, warn = cook_state(m, k)
        row = {"key": k, "food": label(k), "group": m.groups[i], "cook": cook, "raw_warn": warn,
               "cook_why": m.how[k].why if k in m.how else "",
               "chains": int(P.FOODS[k]["n_chains"]) if k in P.FOODS else None,
               "€/100 g": float(m.c[i]) if m.unit_g[i] else None,
               "product": (best["product"] + (f" (⚠ at {best['chain']})" if away else "")) if best else "",
               "pack": f"{best['pack_g']} g, €{best['pack_eur']}" if best else ""}
        for name, (col, unit) in FOOD_COLS.items():
            if col in m.N:
                row[name] = float(m.N[col][i]) if m.unit_g[i] else None
        out.append(row)
    return {"rows": out, "units": {n: u for n, (c, u) in FOOD_COLS.items()}}


@cached
def dishes_table(chain):
    cat = D.catalog(chain)
    roles = {r["code"]: r for r in csv.DictReader(open(ROOT / "data/dinners.tsv"), delimiter="\t")}
    rows_ = []
    for code in D.dishes():
        price, leaves, miss, subs, minor = D.price_dish(code, cat)
        if price is None:
            continue
        row = D.NEVO[code]
        r = {"code": code, "dish": row["Engelse naam/Food name"], "dutch": D.DUTCH[code],
             "group": row["Food group"], "dinner": roles[code]["note"] if code in roles else "",
             "€/100 g": price, "€ per 400 g": 4 * price,
             "ingredients": ", ".join(f"{label(k) if k != '_veg_median' else 'vegetables per piece'} {100*g:.0f} g"
                                      for k, g in sorted(leaves.items(), key=lambda t: -t[1])),
             "substitutes": "; ".join(f"{a} → {b}" for a, b in subs.items()),
             "left out": ", ".join(minor)}
        for name, (col, unit) in FOOD_COLS.items():
            if col in D.COL:
                v = D.num(row[D.COL[col]])
                r[name] = v
        rows_.append(r)
    return {"rows": rows_, "n_total": len(D.dishes())}


# ---------------- price refresh ----------------
def refresh_prices(log):
    """Run fetch_prices.py, expand.py, catalog.py and supplements.py; return the number of outdated cache entries cleared."""
    for script in ("fetch_prices.py", "expand.py", "catalog.py", "supplements.py"):
        log(f"running {script} ...")
        r = subprocess.run([sys.executable, script], cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"{script} failed:\n{r.stderr[-2000:]}")
        log((r.stdout.strip().splitlines() or [""])[-1])
    return clear_outdated()
