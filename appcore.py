"""Stage 6: everything the app computes, as plain data, behind a disk cache.  Used by app.py.

Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources.

Every result is keyed by (function, settings, data version) and stored as a pickle in CACHE_DIR, outside git.
The data version is a hash of the data files and the model code, so new prices or a code change make old
entries unreachable; `clear_outdated()` deletes them. The cache keeps at most `limit_mb` (default 500 MB),
evicting the least recently used entries first (a hit touches the file's mtime).
"""
import csv
import hashlib
import json
import os
import pickle
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

import dishes as D
import explain
import lp
import meals as M
import plan as P
import profiles as PR
from profiles import all_profiles, load_profile

ROOT = Path(__file__).resolve().parent
CACHE_DIR = Path(os.environ.get("NEVO_DIET_CACHE", "~/.cache/nevo-diet")).expanduser()
PR.USER_FILE = Path(os.environ.get("NEVO_DIET_PROFILES", "~/.config/nevo-diet/profiles.json")).expanduser()
SETTINGS_FILE = Path(os.environ.get("NEVO_DIET_SETTINGS", "~/.config/nevo-diet/settings.json")).expanduser()
VERSION_FILES = ["data/catalog_foods.tsv", "data/catalog_prices.tsv", "data/requirements.tsv", "data/profiles.tsv",
                 "data/dinners.tsv", "data/amino_foods.tsv", "lp.py", "plan.py", "meals.py", "dishes.py",
                 "explain.py", "profiles.py", "appcore.py"]
EPS = 1e-7

DEFAULTS = {"profile": "avg_man", "chain": "ah", "cooked": True, "mode": "pure", "budget": 3.0,
            "strictness": "medium", "pattern": "brunch", "batch": True, "min3": False, "excluded": [],
            "weight": None, "height": None, "kcal": None, "protein": None,
            "cache_mb": 500, "food_columns": ["kcal", "protein", "fibre"], "dish_columns": ["kcal", "protein"]}
ALL_CHAINS = "all"      # pure mode only: every food at its cheapest chain

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
        "tryptophan": "tryptophan", "valine": "valine", "free_sugars": "free sugars"}
RULE_NICE = {"dinners_4": "at least 4 different dinners a week", "dinner_max2": "no dinner more than twice a week",
             "toppings_2": "at least 2 bread toppings a week", "veg_250": "250 g vegetables a day",
             "fruit_200": "200 g fruit a day", "kcal_30": "no food above 30% of energy"}


# Vitamins and minerals, in the order of the food coverage chart. The last four only have a maximum.
MICRO = ["potassium", "calcium", "phosphorus", "magnesium", "iron_abs", "zinc", "copper", "iodine", "selenium", "vitA",
         "thiamin", "riboflavin", "niacin", "vitB6", "folate", "vitB12", "vitC", "vitD", "vitE", "vitK1",
         "sodium", "iron", "retinol", "folic_acid"]


def nice(r):
    return NICE.get(r, r)


def label(k):
    if k == "vitD_tablet":
        return "vitamin D tablet"
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
        tmp = p.with_suffix(".tmp")
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


def person(base, weight=None, height=None, kcal=None, protein=None):
    """What to pass as `profile`: the plain name while nothing is changed, so its cached solutions stay valid."""
    if not any((weight, height, kcal, protein)):
        return base
    return {"base": base, "weight": weight, "height": height, "kcal": kcal, "protein": protein}


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


def model(profile, chain, cooked, excluded=(), min3=False):
    return lp.load(drop=tuple(excluded), cooked=cooked, chain=None if chain == ALL_CHAINS else chain,
                   min_chains=3 if min3 else 0, profile=profile)


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
    """Per micronutrient and food in the diet: the amount that food gives and its % of the minimum (of the maximum for
    nutrients that only have one)."""
    reqs = {r["name"]: r for r in m.reqs}
    out = []
    for n in MICRO:
        r = reqs[n]
        if not (r["lower"] or float(r["upper"] or 0)):
            continue
        side, ref = ("minimum", float(r["lower"])) if r["lower"] else ("maximum", float(r["upper"]))
        a = sum(m.N[c] for c in r["cols"].split("+")) * x
        for i in np.flatnonzero((x > EPS) & (a > 0)):
            out.append({"food": (names or {}).get(m.keys[i], label(m.keys[i])), "nutrient": nice(n), "side": side,
                        "amount": float(a[i]), "unit": r["unit"], "pct": float(100 * a[i] / ref),
                        "total_pct": float(100 * a.sum() / ref)})
    return out


def binding_names(m, res, G, h, lab):
    slack = h - G @ res.x
    return sorted({name for j, (name, side) in enumerate(lab) if slack[j] < 1e-6 * max(1, abs(h[j]))
                   and abs(res.ineqlin.marginals[j]) > 1e-9})


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
@cached
def pure(profile, chain, cooked, excluded, min3):
    m = model(profile, chain, cooked, excluded, min3)
    res, G, h, lab = lp.solve(m)
    if res.status != 0:
        return {"ok": False, "message": res.message}
    x = res.x
    grams = x * m.unit_g
    basket = []
    for i in np.argsort(-(x * m.c)):
        if x[i] <= EPS:
            continue
        k = m.keys[i]
        prods = prices_of(k)
        best = min((r for r in prods if chain == ALL_CHAINS or r["chain"] == chain),
                   key=lambda r: float(r["eur_per_100g"]), default=None)
        basket.append({"key": k, "food": label(k), "group": m.groups[i],
                       "amount": f"{grams[i]:.0f} g" if m.unit_g[i] else f"{x[i]:.2f} tablet",
                       "g_day": float(grams[i]), "eur_day": float(x[i] * m.c[i]),
                       "at_cap": bool(abs(x[i] - m.cap[i]) < 1e-7),
                       "product": best["product"] if best else "AH Care Vitamine D3 25 µg",
                       "chain": best["chain"] if best else "ah",
                       "n_chains": int(P.FOODS[k]["n_chains"]) if k in P.FOODS else 1})
    split = explain.price_split(m, res, G, lab)
    shares = []
    for i, s in split.items():
        for req, eur in s["shares"].items():
            shares.append({"food": label(m.keys[i]), "nutrient": nice(req), "eur_per_100g": eur,
                           "price": s["price"]})
        if s["cap_rent"] > 1e-9:
            shares.append({"food": label(m.keys[i]), "nutrient": "cap rent", "eur_per_100g": -s["cap_rent"],
                           "price": s["price"]})
    lam = res.ineqlin.marginals
    shadow = {}
    for j, (name, side) in enumerate(lab):
        if abs(lam[j]) > 1e-12:
            shadow[name] = shadow.get(name, 0.0) + float(-lam[j])
    return {"ok": True, "cost": float(res.fun), "basket": basket, "reqs": requirement_rows(m, totals_of(m, x)),
            "by_food": food_coverage(m, x), "binding": binding_names(m, res, G, h, lab), "shares": shares, "shadow": shadow,
            "rc": {m.keys[i]: float(res.lower.marginals[i]) for i in range(len(m.keys))},
            "grams": {m.keys[i]: float(grams[i]) for i in range(len(m.keys)) if x[i] > EPS},
            "n_foods": len(m.keys)}


@cached
def removal(profile, chain, cooked, excluded, min3):
    m = model(profile, chain, cooked, excluded, min3)
    nodes = explain.removal_tree(m, depth=3, branch=3)
    out = []
    for n in nodes:
        out.append({"path": [label(k) for k in n["path"]], "depth": len(n["path"]),
                    "infeasible": n["infeasible"], "same_as": [label(k) for k in n["same_as"]] if n.get("same_as") else None,
                    "cost": n.get("cost"), "delta": n.get("delta"),
                    "replaced_by": [(label(k), float(g)) for k, g in n.get("replaced_by", [])]})
    return {"nodes": out}


@cached
def cost_curve(profile, chain, cooked, excluded, min3, req, steps=(1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0)):
    m = model(profile, chain, cooked, excluded, min3)
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
def wiggle(profile, chain, cooked, excluded, min3, slack=0.05):
    """Flux-variability ranges: min and max grams of each food over all diets within `slack` of the optimum."""
    m = model(profile, chain, cooked, excluded, min3)
    res, G, h, lab = lp.solve(m)
    if res.status != 0:
        return {"rows": []}
    x, rc = res.x, res.lower.marginals
    Gc, hc = np.vstack([G, m.c]), np.append(h, (1 + slack) * res.fun)
    bounds = list(zip(np.zeros(len(m.keys)), m.cap))
    rows_ = []
    for i, k in enumerate(m.keys):
        if x[i] < EPS and rc[i] > slack * res.fun:       # entering it costs more than the whole slack
            continue
        e = np.zeros(len(m.keys)); e[i] = 1
        a = linprog(e, A_ub=Gc, b_ub=hc, bounds=bounds, method="highs")
        b = linprog(-e, A_ub=Gc, b_ub=hc, bounds=bounds, method="highs")
        if b.status != 0 or -b.fun < 1e-6:
            continue
        f = m.unit_g[i] or 1
        rows_.append({"food": label(k), "min": float(a.fun * f), "max": float(-b.fun * f), "opt": float(x[i] * f),
                      "unit": "g" if m.unit_g[i] else "tablet"})
    return {"rows": rows_, "slack": slack}


@cached
def chain_table(cooked, excluded, min3):
    rows_ = []
    for prof, lab in profiles().items():
        for ch in [ALL_CHAINS] + chains():
            m = model(prof, ch, cooked, excluded, min3)
            res, *_ = lp.solve(m)
            rows_.append({"profile": lab, "profile_key": prof, "chain": ch,
                          "cost": float(res.fun) if res.status == 0 else None})
    return {"rows": rows_}


# ---------------- realistic: a week of meals ----------------
@cached
def realistic(profile, chain, cooked, excluded, strictness, pattern, batch):
    m = lp.load(drop=tuple(excluded), cooked=cooked, chain=chain, min_chains=0, profile=profile)
    mm, info = M.dish_model(m, chain, pattern)
    pk = P.packs(chain)
    lay = M.solve_week(mm, info, pk, chain, pattern, strictness, no_batch=not batch)
    if lay is None:
        return {"ok": False, "message": "no feasible week with these settings"}
    val = lambda k: M.val(lay, k)
    dinners = []
    for j, d in enumerate(info):
        k = round(val(("k", j)))
        if k:
            g = val(("G", j)) * 100 / k
            dinners.append({"dinner": d["note"], "nevo_dish": f"{d['name']} (NEVO {d['code']})", "evenings": k,
                            "g_per_evening": g, "hands_on_min": d["min"], "kind": d["role"],
                            "eur_portion": g / 100 * d["price"]})
    direct = []
    for i in sorted(lay["direct"], key=lambda i: -val(("y", i))):
        y = val(("y", i))
        if y > 1e-4:
            direct.append({"food": label(mm.keys[i]), "amount": f"{y*100/7:.0f} g" if mm.unit_g[i] else
                           f"{y/7:.2f} tablet", "g_day": y * 100 / 7 if mm.unit_g[i] else 0.0, "group": mm.groups[i]})
    shop, money = [], []
    for i in lay["active"]:
        u = val(("y", i)) + sum(d["leaves"].get(mm.keys[i], 0) * val(("G", j)) for j, d in enumerate(info))
        if u < 1e-4:
            continue
        k = mm.keys[i]
        if not mm.unit_g[i]:
            shop.append({"product": "AH Care Vitamine D3 25 µg (300 tablets)", "food": label(k),
                         "buy": f"{u/7:.2f} a day", "eur_week": u * mm.c[i]})
            continue
        g, eur, prod, pg = pk.get(k, (0, 0, "?", 0))
        if lay["kind"][i] == "pantry":
            weeks = g / (u * 100) if u else 0
            shop.append({"product": f"{prod} ({pg:.0f} g, €{eur:.2f})", "food": label(k),
                         "buy": f"1 pack per {weeks:.1f} weeks ({u*100:.0f} g/week)", "eur_week": u * mm.c[i]})
        else:
            n, L = round(val(("n", i))), lay["kind"][i]
            shop.append({"product": f"{prod} ({pg:.0f} g, €{eur:.2f})", "food": label(k),
                         "buy": f"{n} every {'week' if L == 1 else f'{L} weeks'}", "eur_week": n * eur / L})
    vm = sum(d["leaves"].get("_veg_median", 0) * val(("G", j)) for j, d in enumerate(info))
    if vm > 1e-4:
        vegmed = D.veg_median(D.catalog(chain)) or 0
        shop.append({"product": "vegetables sold per piece (celery, cucumber, courgette ...)",
                     "food": "dish ingredients", "buy": f"{vm*100:.0f} g/week", "eur_week": vm * vegmed})
    shop.sort(key=lambda r: -r["eur_week"])
    # nutrients per day
    x_all = np.zeros(len(mm.keys))
    for i in lay["active"]:
        x_all[i] = val(("y", i)) / 7
    for j in range(len(info)):
        x_all[lay["n_food"] + j] = val(("G", j)) / 7
    # rule savings: each bent rule made hard on its own
    bent = []
    for b in lay["broken"]:
        f = M.solve_week(mm, info, pk, chain, pattern, strictness, forced={b: 0}, no_batch=not batch)
        bent.append({"rule": RULE_NICE.get(b, b), "saving_day": (f["cost"] - lay["cost"]) / 7 if f else None})
    return {"ok": True, "cost": lay["cost"] / 7, "dinners": dinners, "direct": direct, "shop": shop,
            "reqs": requirement_rows(mm, totals_of(mm, x_all)),
            "by_food": food_coverage(mm, x_all, {d["key"]: d["note"] for d in info}), "bent": bent, "n_dishes": len(info),
            "mip_seconds": lay["seconds"]}


# ---------------- foods and dishes tables ----------------
FOOD_COLS = {"kcal": ("ENERCC", "kcal"), "protein": ("PROT", "g"), "fat": ("FAT", "g"), "carbs": ("CHO", "g"),
             "fibre": ("FIBT", "g"), "sat. fat": ("FASAT", "g"), "sodium": ("NA", "mg"), "calcium": ("CA", "mg"),
             "iron": ("FE", "mg"), "absorbed iron": ("FE_ABS", "mg"), "zinc": ("ZN", "mg"), "iodine": ("ID", "µg"),
             "vitamin A": ("VITA_RAE", "µg"), "vitamin B12": ("VITB12", "µg"), "vitamin C": ("VITC", "mg"),
             "vitamin D": ("VITD", "µg"), "folate": ("FOL", "µg"), "potassium": ("K", "mg"),
             "magnesium": ("MG", "mg"), "selenium": ("SE", "µg"), "lysine": ("AA_LYS", "mg")}


@cached
def foods_table(profile, chain, cooked, min3):
    """Every food in the catalog (excluded ones too, so they can be put back): prices and nutrients per 100 g."""
    m = model(profile, chain, cooked, (), min3)
    out = []
    for i, k in enumerate(m.keys):
        prods = [r for r in prices_of(k) if chain == ALL_CHAINS or r["chain"] == chain]
        best = min(prods, key=lambda r: float(r["eur_per_100g"]), default=None)
        row = {"key": k, "food": label(k), "group": m.groups[i],
               "chains": int(P.FOODS[k]["n_chains"]) if k in P.FOODS else 1,
               "€/100 g": float(m.c[i]) if m.unit_g[i] else None,
               "product": best["product"] if best else ("AH Care Vitamine D3 25 µg, 1 tablet" if not m.unit_g[i] else ""),
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
    """Run fetch_prices.py, expand.py and catalog.py; return the number of outdated cache entries cleared."""
    for script in ("fetch_prices.py", "expand.py", "catalog.py"):
        log(f"running {script} ...")
        r = subprocess.run([sys.executable, script], cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"{script} failed:\n{r.stderr[-2000:]}")
        log((r.stdout.strip().splitlines() or [""])[-1])
    return clear_outdated()
