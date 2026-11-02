"""Profiles (data/profiles.tsv) and the requirements that follow from them (data/requirements.tsv).

requirements.tsv holds one row per nutrient. `lower`/`upper` are for men, `lower_f`/`upper_f` override them for
women (blank = same as men). `per` scales the number:
  energy   lower/upper are multiples of the profile's energy (kcal)
  protein  lower is a multiple of profile protein (g/kg x weight)
  MJ       per MJ of profile energy (fibre, thiamin, niacin)
  kg       per kg body weight (amino acids, mg/kg/day)
The sources are explained in SOURCES.md.
"""
import csv
import json
from pathlib import Path

KCAL_PER_MJ = 239.006

# Schofield (1985) basal metabolic rate, kcal/day = a * weight + b, by sex and age band.
SCHOFIELD = {("m", 18, 30): (15.057, 692.2), ("m", 30, 60): (11.472, 873.1),
             ("f", 18, 30): (14.818, 486.6), ("f", 30, 60): (8.126, 845.6)}
BMI_HEALTHY = 22.0   # EFSA reference body weight: BMI 22 at the population's height
# Henry (2005) resting energy, kcal/day = a * weight + b * height(m) + c, as used by EFSA 2013 and Gezondheidsraad 2022/19.
HENRY = {("m", 18, 30): (14.4, 313, 113), ("m", 30, 60): (11.4, 541, -137), ("m", 60, 200): (11.4, 541, -256),
         ("f", 18, 30): (10.4, 615, -282), ("f", 30, 60): (8.18, 502, -11.6), ("f", 60, 200): (8.52, 421, 10.7)}
USER_FILE = None     # the app points this at the user's own profiles; scripts and reports only use data/profiles.tsv


def num(s):
    return float(s) if s not in ("", None) else None


def schofield(sex, age, weight):
    a, b = next(v for (s, lo, hi), v in SCHOFIELD.items() if s == sex and lo <= age < hi)
    return a * weight + b


def henry(sex, age, weight, height_cm):
    a, b, c = next(v for (s, lo, hi), v in HENRY.items() if s == sex and lo <= age < hi)
    return a * weight + b * height_cm / 100 + c


def user_profiles():
    return json.loads(Path(USER_FILE).read_text()) if USER_FILE and Path(USER_FILE).exists() else {}


def standard_rows():
    return {r["name"]: r for r in csv.DictReader(open("data/profiles.tsv"), delimiter="\t")}


def rows_():
    rows = standard_rows()
    rows.update({n: {**r, "name": n} for n, r in user_profiles().items()})
    return rows


def load_profile(name):
    """`name` is a row of data/profiles.tsv, or a dict of arguments for `personalise`."""
    if isinstance(name, dict):
        return personalise(**name)
    rows = rows_()
    if name not in rows:
        raise SystemExit(f"unknown profile {name!r}; choose from {', '.join(rows)}")
    r = dict(rows[name])
    age = int(r["age"])
    w = num(r["weight_kg"]) or BMI_HEALTHY * num(r["height_m"]) ** 2
    kcal = num(r["kcal"])
    if kcal is None:
        bmr = henry(r["sex"], age, w, num(r["height_m"]) * 100) if r["weight_kg"] and r["height_m"] else schofield(r["sex"], age, w)
        kcal = bmr * num(r["pal"])
    r.update(age=age, weight=w, energy=kcal, protein=num(r["protein_g_per_kg"]) * w)
    return r


def personalise(base, weight=None, height=None, kcal=None, protein=None):
    """Profile `base` with its body or goals changed (None = as in the profile). weight in kg, height in cm, kcal the
    energy target, protein the minimum in g/day. Sex, age and activity stay the profile's.

    Without a target, energy follows the body: resting energy (Henry with a known height, otherwise Schofield) x the
    profile's activity level, and protein is the profile's g/kg x weight."""
    r = load_profile(base)
    known_height = num(r["height_m"]) * 100 if r["height_m"] else None
    h = height or known_height
    w = weight or (BMI_HEALTHY * (h / 100) ** 2 if height and not r["weight_kg"] else r["weight"])
    energy = r["energy"]
    if weight or height:
        pal = num(r["pal"]) or r["energy"] / schofield(r["sex"], r["age"], r["weight"])
        energy = (henry(r["sex"], r["age"], w, h) if h else schofield(r["sex"], r["age"], w)) * pal
    r.update(weight=w, height_cm=h, energy=kcal or energy, protein=protein or num(r["protein_g_per_kg"]) * w)
    return r


def all_profiles():
    return list(rows_())


def requirements(prof):
    """Requirement rows (name, cols, unit, kind, lower, upper, source) for this profile, numbers as strings."""
    out = []
    limits = prof.get("limits") or {}
    for r in csv.DictReader(open("data/requirements.tsv"), delimiter="\t"):
        lo, hi = r["lower"], r["upper"]
        if prof["sex"] == "f":
            lo, hi = r["lower_f"] or lo, r["upper_f"] or hi
        f = {"energy": prof["energy"], "protein": prof["protein"], "MJ": prof["energy"] / KCAL_PER_MJ,
             "kg": prof["weight"], "": 1.0}[r["per"]]
        scale = lambda s: "" if s == "" else f"{float(s) * f:.4g}"
        lower, upper = scale(lo), scale(hi)
        if r["name"] in limits:         # the user's own min and max, absolute; None = no limit
            own = limits[r["name"]]
            lower = "" if own["lower"] is None else f"{own['lower']:.4g}"
            upper = "" if own["upper"] is None else f"{own['upper']:.4g}"
        out.append({"name": r["name"], "cols": r["cols"], "unit": r["unit"], "kind": r["kind"],
                    "lower": "" if lower in ("0", "0.0") else lower, "upper": upper,
                    "source": r["source"], "url": r["url"], "evidence": r["evidence"]})
    return out


if __name__ == "__main__":
    for n in all_profiles():
        p = load_profile(n)
        print(f"{n:13} {p['sex']} {p['age']} {p['weight']:.1f} kg  {p['energy']:.0f} kcal  {p['protein']:.0f} g protein")
