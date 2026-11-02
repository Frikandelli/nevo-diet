"""The eight app charts (Altair / Vega-Lite).  Used by app.py.

Colours: the validated reference palette of the dataviz guidance (categorical slots in fixed order, light and dark
steps chosen separately, status red only for a missed requirement). One emphasis colour plus grey wherever the
story is "this one versus the rest". Every chart has a hover tooltip; app.py puts a table under each one.
"""
import json

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


def coverage(reqs, t, clip=400):
    """1. % of each minimum met. Binding requirements sit on the 100% line (emphasis colour), missed ones red."""
    p = PALETTE[t]
    df = pd.DataFrame([r for r in reqs if r["lower"]])
    df["pct"] = df["pct_lower"]
    df["shown"] = df["pct"].clip(upper=clip)
    df["state"] = ["missed" if not r.ok and r.pct < 99.9 else "binding" if r.pct < 100.5 else "above"
                   for r in df.itertuples()]
    df["label"] = [f"{'✗ ' if s == 'missed' else ''}{n}" for n, s in zip(df["nutrient"], df["state"])]
    df["intake_s"] = [f"{v:.4g} {u}" for v, u in zip(df["intake"], df["unit"])]
    df["need_s"] = [f"≥ {lo:.4g}" + (f", ≤ {hi:.4g}" if hi else "") + f" {u}"
                    for lo, hi, u in zip(df["lower"], df["upper"], df["unit"])]
    df = df.sort_values("pct")
    base = alt.Chart(df).encode(
        y=alt.Y("label:N", sort=None, title=None),
        tooltip=[alt.Tooltip("nutrient:N"), alt.Tooltip("intake_s:N", title="intake"),
                 alt.Tooltip("need_s:N", title="requirement"), alt.Tooltip("pct:Q", title="% of minimum", format=".0f")])
    bars = base.mark_bar(cornerRadiusEnd=4, height=ROW - 6).encode(
        x=alt.X("shown:Q", title=f"% of the minimum (cut off at {clip}%)", scale=alt.Scale(domain=[0, clip])),
        color=alt.Color("state:N", scale=alt.Scale(domain=["binding", "above", "missed"],
                                                   range=[p["series"][0], p["rest"], p["critical"]]),
                        legend=alt.Legend(title=None, orient="top")))
    rule = alt.Chart(pd.DataFrame({"x": [100]})).mark_rule(color=p["ink2"], strokeWidth=1).encode(x="x:Q")
    return _cfg((bars + rule).properties(height=ROW * len(df)), t)


def food_coverage(rows_, t, full=100):
    """1b. Which food covers which micronutrient: a food x nutrient grid, one blue from pale (little) to full (the whole
    requirement or more). Blank = under 0.5%. Cells from 20% carry their number; the tooltip has the rest."""
    p = PALETTE[t]
    df = pd.DataFrame(rows_)
    df = df[df.pct >= 0.5].copy()
    df["column"] = [f"{n} (max)" if s == "maximum" else n for n, s in zip(df["nutrient"], df["side"])]
    order = list(dict.fromkeys(df["column"]))
    foods = list(df.groupby("food").pct.sum().sort_values(ascending=False).index)
    df["shown"] = df["pct"].clip(upper=full)
    df["amount_s"] = [f"{v:.3g} {u}" for v, u in zip(df["amount"], df["unit"])]
    df["pct_s"] = [f"{v:.0f}% of the {s}" for v, s in zip(df["pct"], df["side"])]
    df["total_s"] = [f"{v:.0f}% of the {s}" for v, s in zip(df["total_pct"], df["side"])]
    df["pct_label"] = df["pct"].round().astype(int).astype(str)
    ramp = ["#cde2fb", "#104281"] if t == "light" else ["#184f95", "#cde2fb"]
    pos = dict(x=alt.X("column:N", sort=order, title=None, scale=alt.Scale(paddingInner=0.06),
                       axis=alt.Axis(orient="top", labelAngle=-45, ticks=False, domain=False)),
               y=alt.Y("food:N", sort=foods, title=None, scale=alt.Scale(paddingInner=0.06),
                       axis=alt.Axis(ticks=False, domain=False)))
    cells = alt.Chart(df).mark_rect(cornerRadius=2).encode(
        **pos,
        color=alt.Color("shown:Q", scale=alt.Scale(domain=[0, full], range=ramp),
                        legend=alt.Legend(title=f"% of the requirement from this food (full colour from {full}%)",
                                          orient="top", gradientLength=220, titleLimit=420)),
        tooltip=[alt.Tooltip("food:N"), alt.Tooltip("nutrient:N"), alt.Tooltip("amount_s:N", title="gives"),
                 alt.Tooltip("pct_s:N", title="covers"), alt.Tooltip("total_s:N", title="whole diet")])
    # Text on the dark half of the ramp flips to light, and the reverse in dark mode.
    light_text = "datum.shown >= 60" if t == "light" else "datum.shown < 30"
    text = alt.Chart(df[df.pct >= 20]).mark_text(fontSize=10).encode(
        **pos, text="pct_label:N",
        color=alt.condition(light_text, alt.value("#ffffff"), alt.value("#0b0b0b")))
    return _cfg((cells + text).properties(height=(ROW + 4) * len(foods), padding={"right": 40}), t)


def money(items, t, top=15):
    """2. Where the money goes: € per day per item, ranked; the tail folds into 'other'."""
    p = PALETTE[t]
    df = pd.DataFrame(items).sort_values("eur", ascending=False)
    if len(df) > top + 1:
        tail = df.iloc[top:]
        df = pd.concat([df.iloc[:top], pd.DataFrame([{"item": f"other ({len(tail)} items)", "eur": tail.eur.sum()}])])
    df["share"] = df["eur"] / df["eur"].sum()
    ch = alt.Chart(df).mark_bar(cornerRadiusEnd=4, height=ROW - 6, color=p["series"][0]).encode(
        y=alt.Y("item:N", sort=None, title=None),
        x=alt.X("eur:Q", title="€ per day"),
        tooltip=[alt.Tooltip("item:N"), alt.Tooltip("eur:Q", title="€/day", format=".3f"),
                 alt.Tooltip("share:Q", title="share", format=".0%")])
    return _cfg(ch.properties(height=ROW * len(df)), t)


def price_split(shares, t, top=7):
    """3. Why each food is in the basket: its price split over the requirements it pays for (LP duality).
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


def chains(rows, chain, t, skip=("poiesz", "vomar")):
    """4. Chain comparison per profile: every chain as a dot, the selected chain highlighted and labelled, the
    cheapest-per-food optimum (all chains mixed) as a diamond. `skip`: chains with tiny online ranges (their
    €5-9 days would squash the axis); they stay in the table."""
    p = PALETTE[t]
    df = pd.DataFrame(rows).dropna(subset=["cost"])
    df = df[~df.chain.isin(skip)]
    df["kind"] = ["all chains mixed" if c == "all" else ("selected chain" if c == chain else "other chains")
                  for c in df.chain]
    dom = ["selected chain", "other chains", "all chains mixed"]
    enc = dict(y=alt.Y("profile:N", sort=None, title=None),
               x=alt.X("cost:Q", title="cheapest adequate day, € (pure LP)", scale=alt.Scale(zero=False)),
               color=alt.Color("kind:N", scale=alt.Scale(domain=dom, range=[p["series"][0], p["rest"], p["ink"]]),
                               legend=alt.Legend(title=None, orient="top")),
               shape=alt.Shape("kind:N", scale=alt.Scale(domain=dom, range=["circle", "circle", "diamond"]), legend=None),
               tooltip=[alt.Tooltip("profile:N"), alt.Tooltip("chain:N"), alt.Tooltip("cost:Q", title="€/day", format=".2f")])
    base = alt.Chart(df).encode(**enc)
    rest = base.mark_point(filled=True, size=90).transform_filter("datum.kind == 'other chains'")
    top = base.mark_point(filled=True, size=120, stroke=p["surface"], strokeWidth=2).transform_filter(
        "datum.kind != 'other chains'")
    lab = alt.Chart(df[df.kind == "selected chain"]).mark_text(dy=-13, color=p["ink2"], fontSize=11).encode(
        x="cost:Q", y=alt.Y("profile:N", sort=None), text="chain:N")
    return _cfg((rest + top + lab).properties(height=56 * df.profile.nunique()), t)


def removal(nodes, t):
    """5. What replaces what: the removal tree as a dot per diet, indented by depth."""
    p = PALETTE[t]
    recs = []
    for n_ in nodes:
        if n_["infeasible"] or n_["same_as"] or n_["cost"] is None:
            continue
        name = "base optimum" if not n_["path"] else ("    " * (n_["depth"] - 1)) + "− " + n_["path"][-1]
        recs.append({"node": name, "id": " / ".join(n_["path"]) or "base", "cost": n_["cost"],
                     "delta": n_["delta"] or 0.0, "depth": n_["depth"],
                     "replaced": ", ".join(f"+{g:.0f} g {k}" for k, g in n_["replaced_by"]) or "-"})
    df = pd.DataFrame(recs)
    df["row"] = range(len(df))
    labels = ["base optimum" if not r else "· " * (r.count(" / ")) + "− " + r.split(" / ")[-1] for r in
              [n_ if n_ != "base" else "" for n_ in df.id]]
    base = df.cost.iloc[0]
    ch = alt.Chart(df).mark_point(filled=True, size=90, color=p["series"][0], stroke=p["surface"], strokeWidth=2).encode(
        y=alt.Y("row:O", title=None, axis=alt.Axis(labelExpr=f"{json.dumps(labels)}[datum.value]", labelAlign="left",
                                                   labelPadding=250, ticks=False)),
        x=alt.X("cost:Q", title="€ per day after removing the food(s)", scale=alt.Scale(zero=False),
                axis=alt.Axis(format=".2f", tickCount=8)),
        tooltip=[alt.Tooltip("id:N", title="removed"), alt.Tooltip("cost:Q", title="€/day", format=".3f"),
                 alt.Tooltip("delta:Q", title="+€ vs parent", format="+.3f"), alt.Tooltip("replaced:N", title="replaced by")])
    rule = alt.Chart(pd.DataFrame({"x": [base]})).mark_rule(color=p["ink2"]).encode(x="x:Q")
    return _cfg((rule + ch).properties(height=ROW * len(df)), t), df


def cost_curves(points, t, budget=None):
    """6. Cost curves: € per day as one minimum is pushed up (x: % of the requirement). One axis for all lines."""
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
            color=p["ink2"], strokeDash=[]).encode(y="y:Q"))
    return _cfg(alt.layer(*layers).properties(height=340), t)


def wiggle(rows, t):
    """7. Wiggle room: per food the range of grams over all diets within 5% of the cheapest cost, dot = optimum."""
    p = PALETTE[t]
    df = pd.DataFrame(rows)
    df = df[df.unit == "g"].sort_values(["opt", "max"], ascending=False)
    tip = [alt.Tooltip("food:N"), alt.Tooltip("min:Q", title="min g", format=".0f"),
           alt.Tooltip("opt:Q", title="optimum g", format=".0f"), alt.Tooltip("max:Q", title="max g", format=".0f")]
    y = alt.Y("food:N", sort=list(df.food), title=None)
    bar = alt.Chart(df).mark_bar(height=6, cornerRadius=3, color=p["rest"]).encode(
        y=y, x=alt.X("min:Q", title="grams per day"), x2="max:Q", tooltip=tip)
    dot = alt.Chart(df).mark_point(filled=True, size=70, color=p["series"][0], stroke=p["surface"], strokeWidth=2).encode(
        y=y, x="opt:Q", tooltip=tip)
    return _cfg((bar + dot).properties(height=ROW * len(df)), t)
