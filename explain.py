"""Stage 3 analyses on a solved LP: why each food is in the basket, what replaces it, what each rule costs.

Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources.

Duality used here. The LP is  min c·x  s.t.  G x <= h,  0 <= x <= cap.  HiGHS returns multipliers
lam_j <= 0 for the rows and mu_i <= 0 for the caps, with reduced cost  r_i = c_i - sum_j lam_j G_ji - mu_i >= 0.
(A food you asked for sits on a lower bound, so r_i can be above 0 while it's in the basket: you pay more for it than the
requirements think it's worth. Then c_i = sum_j lam_j G_ji + mu_i + r_i, which is why the check below has r_i in it.)
For a food in the basket (0 < x_i) and not at its cap, r_i = 0, so its price splits exactly over the binding
requirements:  c_i = sum_j lam_j G_ji. A lower-bound row has G_ji = -a_ji, so its share lam_j G_ji = y_j a_ji
is the part of the price "paying for" nutrient j (y_j = -lam_j >= 0 is the shadow price). An upper-bound row
(sodium, energy max) gives a negative share: the food is penalised for pushing against that limit. A food at
its cap has mu_i < 0: it is worth more than it costs, and the difference -mu_i is its "cap rent".
"""
import dataclasses
from collections import defaultdict

import numpy as np

from lp import solve

EPS = 1e-7


def grams(m, x):
    """Grams bought per day (tablets count as 0 g)."""
    return x * m.unit_g


def price_split(m, res, G, lab):
    """{food index: {"price", "cap_rent", "shares": {req name: €/100 g}}} for every food in the basket.
    Shares of one food sum to price + cap_rent (checked)."""
    lam = res.ineqlin.marginals
    mu = res.upper.marginals
    forced = res.lower.marginals
    out = {}
    for i in np.where(res.x > EPS)[0]:
        contrib = lam * G[:, i]
        by = defaultdict(float)
        for j, (name, _side) in enumerate(lab):
            if abs(contrib[j]) > 1e-12:
                by[name] += contrib[j]
        total = sum(by.values())
        assert abs(total - (m.c[i] - mu[i] - forced[i])) < 1e-6 * max(1, m.c[i]), (m.keys[i], total, m.c[i], mu[i], forced[i])
        out[i] = {"price": m.c[i], "cap_rent": -mu[i], "shares": dict(by)}
    return out


def top_shares(split, n=2):
    """The n requirements with the largest positive share, as (name, fraction of the positive total)."""
    pos = {k: v for k, v in split["shares"].items() if v > 0}
    tot = sum(pos.values()) or 1.0
    return [(k, v / tot) for k, v in sorted(pos.items(), key=lambda t: -t[1])[:n]]


def without(m, keys):
    """Copy of the model with these foods unavailable (cap 0)."""
    cap = m.cap.copy()
    for k in keys:
        cap[m.keys.index(k)] = 0.0
    return dataclasses.replace(m, cap=cap)


def removal_tree(m, depth=3, branch=3, overrides=None):
    """Remove the biggest foods (by grams) one at a time and re-solve, `branch` children per node, `depth` levels.
    Returns a list of nodes: dict(path=[removed keys], cost, delta (vs parent), replaced_by=[(key, +g)],
    infeasible=bool, same_as=None or an earlier path with the same set of removed foods).
    The root (path=[]) is the base optimum. Repeated sets are listed once more but not expanded.
    Your own foods are never removed: they're what you said you'll eat."""
    nodes, seen = [], {}

    def visit(path, parent_x, parent_cost):
        key = frozenset(path)
        if key in seen:
            nodes.append({"path": path, "infeasible": False, "same_as": seen[key]})
            return
        seen[key] = path
        mm = without(m, path)
        r, *_ = solve(mm, overrides=overrides)
        if r.status != 0:
            nodes.append({"path": path, "infeasible": True})
            return
        node = {"path": path, "cost": r.fun, "x": r.x, "infeasible": False, "same_as": None,
                "delta": None if parent_cost is None else r.fun - parent_cost, "replaced_by": []}
        if parent_x is not None:
            dg = grams(m, r.x) - grams(m, parent_x)
            node["replaced_by"] = [(m.keys[i], dg[i]) for i in np.argsort(-dg)[:4] if dg[i] > 5]
        nodes.append(node)
        if len(path) < depth:
            g = grams(m, r.x)
            for i in [i for i in np.argsort(-g) if g[i] > EPS and not (m.lb is not None and m.lb[i] > 0)][:branch]:
                visit(path + [m.keys[i]], r.x, r.fun)

    visit([], None, None)
    return nodes


def nutrient_removal(m, base_res):
    """Drop one requirement at a time (both sides). Returns [(name, delta €/day or None if unbounded/infeasible,
    foods leaving, foods entering)], sorted by saving."""
    base_in = set(np.where(base_res.x > EPS)[0])
    out = []
    for r in m.reqs:
        res, *_ = solve(m, overrides={r["name"]: ("", "")})
        if res.status != 0:
            out.append((r["name"], None, [], []))
            continue
        now = set(np.where(res.x > EPS)[0])
        out.append((r["name"], res.fun - base_res.fun, sorted(base_in - now), sorted(now - base_in)))
    return sorted(out, key=lambda t: (t[1] is None, t[1] if t[1] is not None else 0))
