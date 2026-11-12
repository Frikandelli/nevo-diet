"""Why this diet: the linear program behind the plan, through its dual. What each food is worth, what each food pays for,
what each limit costs, how the cost grows, how much room there is, what replaces what, and every chain."""
import pandas as pd
import streamlit as st

import appcore as A
import ui

c = ui.ctx()
C, ss, theme, pure = ui.C, c.ss, c.theme, c.pure

st.title("Why this diet")
st.caption(c.describe() + " · every chart here explains the pure linear program")
st.markdown(
    "The plan is the optimum of a linear program: choose grams $x \\ge 0$ of each food to minimise the cost $c \\cdot x$ "
    "subject to every limit, $G x \\le h$ (a minimum is a row with a minus sign). Its **dual** gives every limit a "
    "**shadow price** $y_j \\ge 0$: what the cheapest diet would save per unit if that limit were relaxed. "
    "At the optimum each food in the diet is worth exactly its price at those shadow prices, and no food is worth more "
    "than its price. The charts below read the diet off that duality.")
if c.real:
    st.info("The realistic week adds meals, whole packs and rules on top (a mixed-integer program, which has no shadow "
            "prices), so these charts explain the pure LP of the same settings.")
if ss.food_cost:
    st.caption(f"The cost per food (€{ss.food_cost:.2f}) only picks which foods are in. 'Why each food is in the basket' "
               "uses the plan's basket; the other charts use the plain LP without that cost, so they can show a few more foods.")
if c.own:
    st.caption("Your own foods are fixed amounts, not choices of the LP: the price split leaves them out, and the "
               "removal tree never removes them.")

if not pure["ok"]:
    st.error("No adequate diet with these settings, so there is nothing to explain. The Plan page says what's in the way.")
else:
    ui.contents([("What each food is worth", "worth"), ("What each food pays for", "price-split"),
                 ("What each limit costs", "limit-costs"), ("Cost curves", "cost-curves"), ("Wiggle room", "wiggle"),
                 ("What replaces what", "removal"), ("Every chain", "chains")])

    ui.heading("What each food is worth to this diet", "worth")
    V = A.worth(**c.lp_kw)
    shown = [r for r in V["rows"] if r["worth"] > 1e-4]
    ui.chart_block(C.worth(V["rows"], theme), V["rows"], "food_worth",
                   "Every food at this chain: its price (across) against its worth (up), both per 100 g. Worth = Σ shadow "
                   "price × the food's content of that nutrient, so it is what the food's nutrients would cost bought "
                   "elsewhere in the diet. The foods in the diet sit on the dashed line (worth = price); every other food "
                   "sits below it, by its reduced cost: the price drop it needs before it would enter. That no point is above "
                   "the line is exactly what makes this diet the cheapest (dual feasibility)."
                   + (f" {len(V['rows']) - len(shown)} foods are worth nothing to this diet and aren't drawn." if len(shown) < len(V["rows"]) else ""),
                   ("nevo", "prices", "limits", "model"))

    ui.heading("What each food pays for", "price-split")
    if pure["shares"]:
        ch3, agg = C.price_split(pure["shares"], theme)
        ui.chart_block(ch3, agg.drop(columns=["order"]), "price_split",
                       "At the optimum a food's price splits exactly over the limits it helps meet: price = Σ shadow price × "
                       "content. So each bar is the food's price, divided by what it pays for: its first colour is the "
                       "main reason it's in the diet. The seven limits that pay for the most get a colour, the rest is "
                       "'other' (the tooltip names them). These are the plan's basket foods.",
                       ("nevo", "prices", "limits", "model"))
    else:
        st.caption("Your own foods are the whole basket, so there's nothing for the LP to explain.")

    ui.heading("What each limit costs", "limit-costs")
    L = A.limit_costs(**c.lp_kw)
    if L["rows"]:
        ui.chart_block(C.limit_costs(L["rows"], theme), L["rows"], "limit_costs",
                       "Only the limits that set the price (the binding ones) are here: every other limit could move 10% "
                       "without changing anything. Each one is solved again 10% looser (blue, what it saves) and 10% stricter "
                       "(orange, what it costs). The two differ when the basket changes on the way; the tooltip has the "
                       "shadow-price estimate, which assumes it doesn't.", ("limits", "model"))

    ui.heading("Cost curves: what pushing one minimum up costs", "cost-curves")
    lows = [r for r in pure["reqs"] if r["lower"] and r["kind"] == "abs"]
    names = {r["name"]: r["nutrient"] for r in lows}
    pick = st.multiselect("Minimums to push up (at most 4)", list(names), format_func=names.get,
                          default=[n for n in ("protein", "calcium", "vitC", "fibre") if n in names],
                          max_selections=4, key="curve_pick")
    pts = []
    for n in pick:
        pts += A.cost_curve(**c.lp_kw, req=n)["points"]
    if pts:
        ui.chart_block(C.cost_curves(pts, theme, ss.budget), pts, "cost_curves",
                       "The cheapest diet's price as one minimum is raised to 125%, 150% ... 400% of the norm. The slope at "
                       "100% is that minimum's shadow price; flat means it doesn't bind yet. Each curve is piecewise linear "
                       "and convex: every kink is a new basket. The dashed line is your budget.", ("limits", "model"))

    ui.heading("Wiggle room: how much each food can vary for at most 5% more", "wiggle")
    W = A.wiggle(**c.lp_kw)
    n_in = sum(r["in_diet"] for r in W["rows"])
    ui.chart_block(C.wiggle(W["rows"], theme), W["rows"], "wiggle_room",
                   f"Grey bar: the grams a food can take in some adequate diet costing at most 5% more than the cheapest (the "
                   f"near-optimal part of the polytope, one or two LPs per food). Dot: the cheapest diet. {len(W['rows'])} "
                   f"foods can be part of such a diet; shown are the {n_in} in the cheapest diet and the 25 others that can "
                   "go furthest. The table has all of them.", ("model",))

    ui.heading("What replaces what", "removal")
    RM = A.removal(**c.lp_kw)
    ch5, df5 = C.removal(RM["nodes"], theme)
    bad = [" / ".join(n_["path"]) for n_ in RM["nodes"] if n_["infeasible"]]
    ui.chart_block(ch5, df5.drop(columns=["row"]), "removal_tree",
                   "Take the biggest food out of the cheapest diet and solve again; then do the same in the new diet: three "
                   "levels, three branches each. Each bar is how much dearer that diet is than the cheapest. Hover for what "
                   "replaced the removed food." + (f" No adequate diet is left after removing: {'; '.join(bad)}." if bad else ""),
                   ("model",))

    ui.heading("The same diet at every chain", "chains")
    if c.real and A.week_prices.is_cached(**c.week_kw):
        rows_ = A.week_prices(**c.week_kw)["rows"]
        what = "the realistic week"
    else:
        rows_ = (c.ranking if c.ranking and not c.real else A.chain_prices(**c.pure_rank_kw))["rows"]
        what = "the pure LP" + (f" with the cost per food" if ss.food_cost else "")
    rows_ = [{**r, "name": ui.chain_name(r["chain"])} for r in rows_]
    mixed = A.pure(**{**c.pure_kw, "chain": A.ALL_CHAINS}) if not c.real else None
    big = [r for r in rows_ if r["chain"] not in ("poiesz", "vomar")]
    ui.chart_block(C.chain_costs(big, c.chain, theme, mixed["cost"] if mixed and mixed["ok"] else None), rows_, "chains",
                   f"Your settings at each chain, as {what}. Poiesz and Vomar sell few products online, so their days cost "
                   "€5-9 and they're only in the table. A missing chain has no adequate diet with these settings. The "
                   "dashed line takes every food from the chain that sells it cheapest: no single shop gets there.",
                   ("prices",))
    ui.sources("nevo", "prices", "limits", "model")
