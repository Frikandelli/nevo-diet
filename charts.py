"""The app's charts (Altair / Vega-Lite).  Used by the pages in views/.

Colours: the validated reference palette of the dataviz guidance (categorical slots in fixed order, light and dark
steps chosen separately, status red only for a limit that's broken). One emphasis colour plus grey wherever the
story is "this one versus the rest"; blue always means "sets the price" (a binding limit, a food in the diet). Every
chart has a hover tooltip; the pages put a table and an export under each one.

What's in the diet (views/nutrients.py): coverage, maximums, food_coverage, macro_split, money.
Why this diet (views/why.py): worth, price_split, limit_costs, cost_curves, wiggle, removal, chain_costs.
"""
import json
import math

import altair as alt
import pandas as pd

PALETTE = {
    "light": {"series": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"],
              "rest": "#c3c2b7", "other": "#898781", "ink": "#0b0b0b", "ink2": "#52514e", "grid": "#e1e0d9",
              "surface": "#fcfcfb", "critical": "#d03b3b"},
    "dark": {"series": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9"],
             "rest": "#5f5e5a", "other": "#898781", "ink": "#f0efec", "ink2": "#c3c2b7", "grid": "#2c2c2a",
             "surface": "#1a1a19", "critical": "#d03b3b"},
}
RAMP = {"light": ["#cde2fb", "#104281"], "dark": ["#184f95", "#cde2fb"]}     # sequential blue, near zero -> full
FONT = "system-ui, -apple-system, Segoe UI, sans-serif"
ROW = 20          # px per bar row


def _cfg(ch, t):
    p = PALETTE[t]
    return (ch.configure(font=FONT, background="transparent")
              .configure_axis(gridColor=p["grid"], domainColor=p["grid"], tickColor=p["grid"], labelColor=p["ink2"],
                              titleColor=p["ink2"], labelFont=FONT, titleFont=FONT, labelFontSize=12,
                              titleFontWeight="normal", labelLimit=260)
              .configure_legend(labelColor=p["ink2"], titleColor=p["ink2"], labelFont=FONT, titleFont=FONT,
                                orient="top", labelLimit=240)
              .configure_view(strokeWidth=0))


def _limit_state(rows, side, binding):
    """'binding' (sets the price), 'ok' or 'broken', per requirement row, for the minimum or the maximum side."""
    out = []
    for r in rows:
        pct = r["pct_lower"] if side == "lower" else r["pct_upper"]
        broken = (pct < 99.9) if side == "lower" else (pct > 100.1)
        if broken:
            out.append("broken")
        elif binding is not None:
            out.append("binding" if (r["name"], "lo" if side == "lower" else "hi") in binding else "ok")
        else:                               # no LP behind it (the realistic week): on the line counts as binding
            out.append("binding" if 99.5 <= pct <= 100.5 else "ok")
    return out


def coverage(reqs, t, binding=None, clip=400):
    """Minimums: % of each minimum met. Blue: the limit sets the price (binding), red ✗: missed.
    binding: {(name, 'lo'|'hi')} from the LP; None for the realistic week (then 'on the 100% line')."""
    p = PALETTE[t]
    rows = [r for r in reqs if r["lower"]]
    df = pd.DataFrame(rows)
    df["pct"] = df["pct_lower"]
    df["shown"] = df["pct"].clip(upper=clip)
    df["state"] = _limit_state(rows, "lower", binding)
    df["label"] = [f"{'✗ ' if s == 'broken' else ''}{n}" for n, s in zip(df["nutrient"], df["state"])]
    df["intake_s"] = [f"{v:,.4g} {u}" for v, u in zip(df["intake"], df["unit"])]
    df["need_s"] = [f"≥ {lo:,.4g}" + (f", ≤ {hi:,.4g}" if hi else "") + f" {u}"
                    for lo, hi, u in zip(df["lower"], df["upper"], df["unit"])]
    df = df.sort_values("pct")
    dom = {"binding": "sets the price", "ok": "above the minimum", "broken": "missed"}
    df["state_s"] = df["state"].map(dom)
    base = alt.Chart(df).encode(
        y=alt.Y("label:N", sort=None, title=None),
        tooltip=[alt.Tooltip("nutrient:N"), alt.Tooltip("intake_s:N", title="intake"),
                 alt.Tooltip("need_s:N", title="requirement"), alt.Tooltip("pct:Q", title="% of minimum", format=".0f"),
                 alt.Tooltip("state_s:N", title="")])
    bars = base.mark_bar(cornerRadiusEnd=4, height=ROW - 6).encode(
        x=alt.X("shown:Q", title=f"% of the minimum (cut off at {clip}%)", scale=alt.Scale(domain=[0, clip])),
        color=alt.Color("state_s:N", scale=alt.Scale(domain=list(dom.values()),
                                                     range=[p["series"][0], p["rest"], p["critical"]]),
                        legend=alt.Legend(title=None, orient="top")))
    rule = alt.Chart(pd.DataFrame({"x": [100]})).mark_rule(color=p["ink2"], strokeWidth=1).encode(x="x:Q")
    return _cfg((bars + rule).properties(height=ROW * len(df)), t)


def maximums(reqs, t, binding=None):
    """Maximums: how much of each upper limit the diet uses. Blue: the limit sets the price, red ✗: over it."""
    p = PALETTE[t]
    rows = [r for r in reqs if r["upper"]]
    df = pd.DataFrame(rows)
    df["pct"] = df["pct_upper"]
    df["shown"] = df["pct"].clip(upper=150)
    df["state"] = _limit_state(rows, "upper", binding)
    df["label"] = [f"{'✗ ' if s == 'broken' else ''}{n}" for n, s in zip(df["nutrient"], df["state"])]
    df["intake_s"] = [f"{v:,.4g} {u}" for v, u in zip(df["intake"], df["unit"])]
    df["need_s"] = [f"≤ {hi:,.4g} {u}" for hi, u in zip(df["upper"], df["unit"])]
    df = df.sort_values("pct", ascending=False)
    dom = {"binding": "sets the price", "ok": "below the maximum", "broken": "over"}
    df["state_s"] = df["state"].map(dom)
    base = alt.Chart(df).encode(
        y=alt.Y("label:N", sort=None, title=None),
        tooltip=[alt.Tooltip("nutrient:N"), alt.Tooltip("intake_s:N", title="intake"),
                 alt.Tooltip("need_s:N", title="maximum"), alt.Tooltip("pct:Q", title="% of maximum", format=".0f"),
                 alt.Tooltip("state_s:N", title="")])
    bars = base.mark_bar(cornerRadiusEnd=4, height=ROW - 6).encode(
        x=alt.X("shown:Q", title="% of the maximum used", scale=alt.Scale(domain=[0, max(100, float(df.shown.max()))])),
        color=alt.Color("state_s:N", scale=alt.Scale(domain=list(dom.values()),
                                                     range=[p["series"][0], p["rest"], p["critical"]]),
                        legend=alt.Legend(title=None, orient="top")))
    text = base.mark_text(align="left", dx=4, fontSize=11, color=p["ink2"]).encode(
        x="shown:Q", text=alt.Text("pct:Q", format=".0f"))
    rule = alt.Chart(pd.DataFrame({"x": [100]})).mark_rule(color=p["ink2"], strokeWidth=1).encode(x="x:Q")
    return _cfg((bars + text + rule).properties(height=ROW * len(df), padding={"right": 30}), t)


def _grid(df, columns, foods, t, full, legend, tooltip, label_from):
    """A food x nutrient heat grid on the sequential blue: every column in `columns` is drawn, also an empty one."""
    shown = df[df.pct >= 0.5].copy()
    shown["shown"] = shown["pct"].clip(upper=full)
    shown["pct_label"] = shown["pct"].round().astype(int).astype(str)
    pos = dict(x=alt.X("column:N", sort=columns, title=None, scale=alt.Scale(domain=columns, paddingInner=0.06),
                       axis=alt.Axis(orient="top", labelAngle=-45, ticks=False, domain=False)),
               y=alt.Y("food:N", sort=foods, title=None, scale=alt.Scale(domain=foods, paddingInner=0.06),
                       axis=alt.Axis(ticks=False, domain=False)))
    cells = alt.Chart(shown).mark_rect(cornerRadius=2).encode(
        **pos,
        color=alt.Color("shown:Q", scale=alt.Scale(domain=[0, full], range=RAMP[t]),
                        legend=alt.Legend(title=legend, orient="top", gradientLength=220, titleLimit=420)),
        tooltip=tooltip)
    # Text on the dark half of the ramp flips to light, and the reverse in dark mode.
    light_text = f"datum.shown >= {0.6 * full}" if t == "light" else f"datum.shown < {0.3 * full}"
    text = alt.Chart(shown[shown.pct >= label_from]).mark_text(fontSize=10).encode(
        **pos, text="pct_label:N", color=alt.condition(light_text, alt.value("#ffffff"), alt.value("#0b0b0b")))
    # An invisible layer over every cell keeps empty columns and rows on the axes.
    frame = alt.Chart(df.drop_duplicates(["column", "food"])).mark_rect(opacity=0).encode(**pos)
    return _cfg((frame + cells + text).properties(height=(ROW + 4) * len(foods), padding={"right": 40}), t)


def food_coverage(rows_, t, full=100):
    """Which food gives which vitamin and mineral: food x nutrient, one blue from pale (little) to full (the whole
    requirement or more). Every nutrient with a limit has a column, also one the diet has none of. Blank = under
    0.5%. Cells from 20% carry their number; the tooltip has the rest."""
    df = pd.DataFrame(rows_)
    df["column"] = [f"{n} (max)" if s == "maximum" else n for n, s in zip(df["nutrient"], df["side"])]
    columns = list(dict.fromkeys(df["column"]))
    foods = list(df.groupby("food", sort=False).pct.sum().sort_values(ascending=False).index)
    df["amount_s"] = [f"{v:.3g} {u}" for v, u in zip(df["amount"], df["unit"])]
    df["pct_s"] = [f"{v:.0f}% of the {s}" for v, s in zip(df["pct"], df["side"])]
    df["total_s"] = [f"{v:.0f}% of the {s}" for v, s in zip(df["total_pct"], df["side"])]
    tip = [alt.Tooltip("food:N"), alt.Tooltip("nutrient:N"), alt.Tooltip("amount_s:N", title="gives"),
           alt.Tooltip("pct_s:N", title="covers"), alt.Tooltip("total_s:N", title="whole diet")]
    return _grid(df, columns, foods, t, full, f"% of the requirement from this food (full colour from {full}%)", tip, 20)


def _total_s(v, unit):
    return f"{v:,.0f} {unit}" if v >= 10 or v == 0 else f"{v:.2g} {unit}"


def macro_split(rows_, t, full=50):
    """Where the energy and macros come from: food x macronutrient, each column the day's total split over the foods
    (a column adds up to 100%). Every macro has a column, also one that is 0 for the whole diet (free sugars, often),
    so you see that it's 0 rather than miss it. Same blue as food_coverage, full colour from `full`%. Blank = under
    0.5%; cells from 5% carry their number. Foods sorted by their share of the energy."""
    df = pd.DataFrame(rows_)
    tot = df.drop_duplicates("nutrient").set_index("nutrient")
    head = {n: f"{n} ({_total_s(r.day_total, r.unit)})" for n, r in tot.iterrows()}
    columns = [head[n] for n in tot.index]
    foods = list(df[df.nutrient == "energy"].sort_values("pct", ascending=False).food)
    foods += [f for f in dict.fromkeys(df.food) if f not in foods]
    df["column"] = df["nutrient"].map(head)
    df["amount_s"] = [f"{v:.3g} {u}" for v, u in zip(df["amount"], df["unit"])]
    df["pct_s"] = [f"{v:.0f}% of the day's {n}" for v, n in zip(df["pct"], df["nutrient"])]
    df["energy_s"] = [f"{v:.1f}% of the day's energy" if pd.notna(v) else "" for v in df["pct_energy"]]
    tip = [alt.Tooltip("food:N"), alt.Tooltip("nutrient:N"), alt.Tooltip("amount_s:N", title="gives"),
           alt.Tooltip("pct_s:N", title="share"), alt.Tooltip("energy_s:N", title="energy")]
    return _grid(df, columns, foods, t, full, f"% of the day's total from this food (full colour from {full}%)", tip, 5)


def money(items, t, top=15):
    """Where the money goes: € per day per item, ranked; the tail folds into 'other'."""
    p = PALETTE[t]
    df = pd.DataFrame(items).sort_values("eur", ascending=False)
    if len(df) > top + 1:
        tail = df.iloc[top:]
        df = pd.concat([df.iloc[:top], pd.DataFrame([{"item": f"other ({len(tail)} items)", "eur": tail.eur.sum()}])])
    df["share"] = df["eur"] / df["eur"].sum()
    base = alt.Chart(df).encode(y=alt.Y("item:N", sort=None, title=None),
                                tooltip=[alt.Tooltip("item:N"), alt.Tooltip("eur:Q", title="€/day", format=".3f"),
                                         alt.Tooltip("share:Q", title="share", format=".0%")])
    bars = base.mark_bar(cornerRadiusEnd=4, height=ROW - 6, color=p["series"][0]).encode(x=alt.X("eur:Q", title="€ per day"))
    text = base.mark_text(align="left", dx=4, fontSize=11, color=p["ink2"]).encode(
        x="eur:Q", text=alt.Text("share:Q", format=".0%"))
    return _cfg((bars + text).properties(height=ROW * len(df), padding={"right": 30}), t)


def price_split(shares, t, top=7):
    """Why each food is in the basket: its price split over the requirements it pays for (LP duality).
    Positive shares only, as a fraction of the food's price; the top `top` requirements get colours."""
    p = PALETTE[t]
    df = pd.DataFrame(shares)
    df = df[df.eur_per_100g > 1e-9].copy()
    tot = df.groupby("food").eur_per_100g.transform("sum")
    df["frac"] = df.eur_per_100g / tot
    weight = df.groupby("nutrient").frac.sum().sort_values(ascending=False)
    keep = list(weight.index[:top])
    df["part"] = [n if n in keep else "other" for n in df.nutrient]
    agg = df.groupby(["food", "part"], as_index=False).agg(frac=("frac", "sum"), eur=("eur_per_100g", "sum"),
                                                          detail=("nutrient", lambda s: ", ".join(sorted(s))))
    order = df.groupby("food").frac.max().index.tolist()
    first = agg.sort_values("frac", ascending=False).drop_duplicates("food").set_index("food")["part"]
    order = sorted(order, key=lambda f: (keep.index(first[f]) if first[f] in keep else 99, f))
    agg["order"] = [keep.index(x) if x in keep else 99 for x in agg.part]
    ch = alt.Chart(agg).mark_bar(height=ROW - 6, stroke=p["surface"], strokeWidth=2).encode(
        y=alt.Y("food:N", sort=order, title=None),
        x=alt.X("frac:Q", stack="normalize", title="share of the food's price", axis=alt.Axis(format="%")),
        color=alt.Color("part:N", scale=alt.Scale(domain=keep + ["other"], range=p["series"][:len(keep)] + [p["other"]]),
                        legend=alt.Legend(title="pays for", orient="top", columns=4)),
        order=alt.Order("order:Q"),
        tooltip=[alt.Tooltip("food:N"), alt.Tooltip("part:N", title="pays for"), alt.Tooltip("detail:N", title="requirements"),
                 alt.Tooltip("frac:Q", title="share", format=".0%"), alt.Tooltip("eur:Q", title="€/100 g", format=".4f")])
    return _cfg(ch.properties(height=ROW * len(order)), t), agg


def worth(rows, t):
    """Every food's price against what it's worth to the diet at the shadow prices (both € per 100 g, log scales).
    The diagonal is price = worth: the foods in the diet sit on it, every other food below it (dual feasibility)."""
    p = PALETTE[t]
    df = pd.DataFrame(rows)
    df = df[(df.worth > 1e-4) & (df.price > 0)].copy()
    df["kind"] = ["in the diet" if d else "not in the diet" for d in df.in_diet]
    df["gap"] = [f"{100 * rc / pr:.0f}% too dear" if rc > 1e-6 else "worth its price" for rc, pr in zip(df.reduced_cost, df.price)]
    lo, hi = float(min(df.price.min(), df.worth.min())) * 0.8, float(max(df.price.max(), df.worth.max())) * 1.25
    xs = alt.Scale(type="log", domain=[lo, hi])
    ys = alt.Scale(type="log", domain=[lo, hi])
    ticks = [v for v in (0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20) if lo <= v <= hi]
    # The diet's foods all sit on the diagonal: label one only if it's far enough (in log price) from the last label.
    keep, last = [], None
    for i, pr in df[df.in_diet].sort_values("price").price.items():
        if last is None or math.log10(pr) - last > 0.07:
            keep.append(i)
            last = math.log10(pr)
    df["label"] = [f if i in keep else "" for i, f in zip(df.index, df.food)]
    tip = [alt.Tooltip("food:N"), alt.Tooltip("group:N"), alt.Tooltip("price:Q", title="price €/100 g", format=".3f"),
           alt.Tooltip("worth:Q", title="worth €/100 g", format=".3f"), alt.Tooltip("gap:N", title=""),
           alt.Tooltip("g_day:Q", title="g/day in the diet", format=".0f")]
    diag = alt.Chart(pd.DataFrame({"x": [lo, hi], "y": [lo, hi]})).mark_line(color=p["ink2"], strokeWidth=1, strokeDash=[4, 4]).encode(
        x=alt.X("x:Q", scale=xs), y=alt.Y("y:Q", scale=ys))
    dom = ["in the diet", "not in the diet"]
    pts = alt.Chart(df.sort_values("in_diet")).mark_circle(stroke=p["surface"], strokeWidth=1).encode(
        x=alt.X("price:Q", scale=xs, title="price, € per 100 g (log)", axis=alt.Axis(values=ticks, format="~g")),
        y=alt.Y("worth:Q", scale=ys, title="worth to this diet, € per 100 g (log)", axis=alt.Axis(values=ticks, format="~g")),
        color=alt.Color("kind:N", scale=alt.Scale(domain=dom, range=[p["series"][0], p["rest"]]),
                        legend=alt.Legend(title=None, orient="top")),
        size=alt.Size("kind:N", scale=alt.Scale(domain=dom, range=[110, 36]), legend=None),
        opacity=alt.Opacity("kind:N", scale=alt.Scale(domain=dom, range=[1.0, 0.75]), legend=None),
        tooltip=tip)
    labels = alt.Chart(df[df.label != ""]).mark_text(align="right", dx=-8, fontSize=11, color=p["ink2"]).encode(
        x=alt.X("price:Q", scale=xs), y=alt.Y("worth:Q", scale=ys), text="label:N")
    return _cfg((diag + pts + labels).properties(height=520), t)


def limit_costs(rows, t):
    """What each price-setting limit costs: the change in € a day with the limit 10% looser (saves, to the left) and
    10% stricter (costs, to the right), from re-solving the LP. Two series: slots 1 and 2, with a legend."""
    p = PALETTE[t]
    recs = []
    for r in rows:
        name = f"{r['nutrient']} ({'min' if r['side'] == 'minimum' else 'max'} {r['level']:,.4g} {r['unit']})"
        for how, v in (("10% looser", r["looser"]), ("10% stricter", r["stricter"])):
            recs.append({"limit": name, "how": how, "eur": v, "missing": v is None, "estimate": r["estimate"]})
    df = pd.DataFrame(recs)
    order = list(dict.fromkeys(df.limit))
    dom = ["10% looser", "10% stricter"]
    bars = alt.Chart(df.dropna(subset=["eur"])).mark_bar(height=ROW - 6, cornerRadius=3).encode(
        y=alt.Y("limit:N", sort=order, title=None),
        x=alt.X("eur:Q", title="change in € per day (left: saves, right: costs)", axis=alt.Axis(format="+.2f")),
        color=alt.Color("how:N", scale=alt.Scale(domain=dom, range=p["series"][:2]), legend=alt.Legend(title=None, orient="top")),
        tooltip=[alt.Tooltip("limit:N"), alt.Tooltip("how:N", title=""), alt.Tooltip("eur:Q", title="€/day", format="+.3f"),
                 alt.Tooltip("estimate:Q", title="shadow-price estimate ±", format=".3f")])
    zero = alt.Chart(pd.DataFrame({"x": [0]})).mark_rule(color=p["ink2"]).encode(x="x:Q")
    return _cfg((bars + zero).properties(height=ROW * len(order)), t)


def cost_curves(points, t, budget=None):
    """Cost curves: € per day as one minimum is pushed up (x: % of the requirement). One axis for all lines."""
    p = PALETTE[t]
    df = pd.DataFrame(points).dropna(subset=["cost"])
    names = list(dict.fromkeys(df.nutrient))
    sc = alt.Scale(domain=names, range=p["series"][:len(names)])
    nearest = alt.selection_point(nearest=True, on="pointerover", fields=["pct"], empty=False)
    base = alt.Chart(df).encode(x=alt.X("pct:Q", title="minimum pushed to … % of the requirement",
                                         scale=alt.Scale(zero=False)),
                                y=alt.Y("cost:Q", title="€ per day"), color=alt.Color("nutrient:N", scale=sc,
                                                                                      legend=alt.Legend(title=None, orient="top")))
    lines = base.mark_line(strokeWidth=2)
    pts = base.mark_point(filled=True, size=70, stroke=p["surface"], strokeWidth=2).encode(
        opacity=alt.condition(nearest, alt.value(1), alt.value(0)),
        tooltip=[alt.Tooltip("nutrient:N"), alt.Tooltip("pct:Q", title="% of requirement"),
                 alt.Tooltip("level:Q", title="minimum", format=".4g"), alt.Tooltip("unit:N"),
                 alt.Tooltip("cost:Q", title="€/day", format=".2f")]).add_params(nearest)
    rule = alt.Chart(df).mark_rule(color=p["grid"], strokeWidth=1).encode(x="pct:Q").transform_filter(nearest)
    end = df.sort_values("pct").groupby("nutrient").tail(1)
    labels = alt.Chart(end).mark_text(align="left", dx=6, color=p["ink2"]).encode(
        x="pct:Q", y="cost:Q", text="nutrient:N")
    layers = [rule, lines, pts, labels]
    if budget:
        layers.append(alt.Chart(pd.DataFrame({"y": [budget], "t": [f"budget €{budget:.2f}"]})).mark_rule(
            color=p["ink2"], strokeDash=[4, 4]).encode(y="y:Q"))
        layers.append(alt.Chart(pd.DataFrame({"y": [budget], "t": [f"budget €{budget:.2f}"]})).mark_text(
            align="left", dx=4, dy=-7, color=p["ink2"], fontSize=11).encode(y="y:Q", x=alt.value(0), text="t:N"))
    return _cfg(alt.layer(*layers).properties(height=340, padding={"right": 90}), t)


def wiggle(rows, t, others=25):
    """Wiggle room: per food the range of grams over all diets within 5% of the cheapest cost, dot = the cheapest diet.
    Shown: every food in the cheapest diet, then the `others` foods outside it that can go furthest."""
    p = PALETTE[t]
    df = pd.DataFrame(rows)
    df = df[df.unit == "g"]
    df = pd.concat([df[df.in_diet].sort_values("opt", ascending=False),
                    df[~df.in_diet].sort_values("max", ascending=False).head(others)])
    df["kind"] = ["in the cheapest diet" if d else "not in it" for d in df.in_diet]
    tip = [alt.Tooltip("food:N"), alt.Tooltip("min:Q", title="min g", format=".0f"),
           alt.Tooltip("opt:Q", title="cheapest diet g", format=".0f"), alt.Tooltip("max:Q", title="max g", format=".0f")]
    y = alt.Y("food:N", sort=list(df.food), title=None)
    bar = alt.Chart(df).mark_bar(height=6, cornerRadius=3, color=p["rest"]).encode(
        y=y, x=alt.X("min:Q", title="grams per day"), x2="max:Q", tooltip=tip)
    dot = alt.Chart(df[df.in_diet]).mark_point(filled=True, size=70, color=p["series"][0], stroke=p["surface"],
                                              strokeWidth=2).encode(y=y, x="opt:Q", tooltip=tip)
    return _cfg((bar + dot).properties(height=ROW * len(df)), t)


def removal(nodes, t):
    """What replaces what: the removal tree, one bar per diet = how much dearer it is than the cheapest diet.
    Rows in tree order, indented by depth; hover for what replaced the removed food."""
    p = PALETTE[t]
    recs = []
    for n_ in nodes:
        if n_["infeasible"] or n_["same_as"] or n_["cost"] is None:
            continue
        recs.append({"id": " / ".join(n_["path"]) or "cheapest diet", "cost": n_["cost"], "depth": n_["depth"],
                     "step": n_["delta"] or 0.0,
                     "replaced": ", ".join(f"+{g:.0f} g {k}" for k, g in n_["replaced_by"]) or "-"})
    df = pd.DataFrame(recs)
    base = df.cost.iloc[0]
    df["extra"] = df.cost - base
    df["row"] = range(len(df))
    df["extra_s"] = ["" if r == 0 else f"+€{e:.3f}" for r, e in zip(df.row, df.extra)]
    labels = ["cheapest diet" if i == "cheapest diet" else "· " * (i.count(" / ")) + "− " + i.split(" / ")[-1] for i in df.id]
    y = alt.Y("row:O", title=None, axis=alt.Axis(labelExpr=f"{json.dumps(labels)}[datum.value]", labelAlign="left",
                                                 labelPadding=290, labelLimit=285, ticks=False))
    tip = [alt.Tooltip("id:N", title="removed"), alt.Tooltip("cost:Q", title="€/day", format=".3f"),
           alt.Tooltip("extra:Q", title="vs the cheapest", format="+.3f"), alt.Tooltip("step:Q", title="vs one level up", format="+.3f"),
           alt.Tooltip("replaced:N", title="replaced by")]
    bars = alt.Chart(df).mark_bar(height=ROW - 8, cornerRadiusEnd=3, color=p["series"][0]).encode(
        y=y, x=alt.X("extra:Q", title="€ per day more than the cheapest diet", axis=alt.Axis(format="+.2f")), tooltip=tip)
    text = alt.Chart(df).mark_text(align="left", dx=4, fontSize=11, color=p["ink2"]).encode(y=y, x="extra:Q", text="extra_s:N")
    return _cfg((bars + text).properties(height=ROW * len(df), padding={"right": 60}), t), df


def chain_costs(rows, chain, t, mixed=None):
    """The same settings at every chain: € per day, the chain in use in blue, the rest grey. mixed: the price with
    every food at its cheapest chain, as a dashed rule (no single shop sells that)."""
    p = PALETTE[t]
    df = pd.DataFrame(rows).dropna(subset=["cost"])
    df["kind"] = ["chain in use" if c == chain else "other chains" for c in df.chain]
    df["cost_s"] = [f"€{v:.2f}" for v in df.cost]
    tip = [alt.Tooltip("name:N", title="chain"), alt.Tooltip("cost:Q", title="€/day", format=".2f")]
    if "bent" in df:
        tip.append(alt.Tooltip("bent:Q", title="meal rules bent"))
    y = alt.Y("name:N", sort=list(df.sort_values("cost").name), title=None)
    bars = alt.Chart(df).mark_bar(height=ROW - 6, cornerRadiusEnd=4).encode(
        y=y, x=alt.X("cost:Q", title="€ per day"),
        color=alt.Color("kind:N", scale=alt.Scale(domain=["chain in use", "other chains"], range=[p["series"][0], p["rest"]]),
                        legend=alt.Legend(title=None, orient="top")), tooltip=tip)
    text = alt.Chart(df).mark_text(align="left", dx=4, fontSize=11, color=p["ink2"]).encode(
        y=y, x="cost:Q", text="cost_s:N")
    layers = [bars, text]
    if mixed:
        m = pd.DataFrame({"x": [mixed], "t": [f"every food at its cheapest chain: €{mixed:.2f}"]})
        layers += [alt.Chart(m).mark_rule(color=p["ink2"], strokeDash=[4, 4]).encode(x="x:Q"),
                   alt.Chart(m).mark_text(align="left", dx=4, dy=-6, fontSize=11, color=p["ink2"]).encode(
                       x="x:Q", y=alt.value(0), text="t:N")]
    return _cfg(alt.layer(*layers).properties(height=ROW * len(df) + 10, padding={"right": 40, "top": 10}), t)
