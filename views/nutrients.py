"""Nutrients: what is in the diet, and where it comes from. Follows the mode: the realistic week once it's solved, else
the pure LP. Every chart has its numbers and downloads under it; the full table is at the bottom."""
import streamlit as st

import ui

c = ui.ctx()
C, src, theme = ui.C, c.src, c.theme

st.title("Nutrients")
st.caption(f"{c.describe()} · the charts describe the **{c.src_tag}**")
if c.real and src is not c.R:
    st.info("These charts show the pure LP until the realistic week is solved: press **Solve** in the sidebar.")

if not src["ok"]:
    st.error("No adequate diet with these settings, so there is nothing to chart. The Plan page says what's in the way.")
else:
    binding = ui.limit_state_binding(src)
    ui.contents([("Minimums", "minimums"), ("Maximums", "maximums"), ("Vitamins and minerals per food", "per-food"),
                 ("Energy and macros per food", "macros"), ("Where the money goes", "money"), ("Every nutrient", "table")])

    ui.heading("Minimums: how much of each is met", "minimums")
    ui.chart_block(C.coverage(src["reqs"], theme, binding),
                   [{k: r[k] for k in ("nutrient", "intake", "unit", "lower", "upper", "pct_lower", "ok")} for r in src["reqs"] if r["lower"]],
                   "minimums", "Blue bars sit on the 100% line: those minimums set the price (they bind). Grey: met with room to "
                               "spare. Red ✗: missed. Bars stop at 400%.", ("nevo", "limits"))

    ui.heading("Maximums: how close the diet comes to each upper limit", "maximums")
    ui.chart_block(C.maximums(src["reqs"], theme, binding),
                   [{k: r[k] for k in ("nutrient", "intake", "unit", "upper", "pct_upper", "ok")} for r in src["reqs"] if r["upper"]],
                   "maximums", "Upper limits: salt, saturated fat, free sugars, trans fat, the safe upper levels of vitamins "
                               "and minerals, and your own limits on foods ('limit: ...', if you set any). Blue: the maximum "
                               "sets the price. Red ✗: over it. A full bar here is not a goal.",
                   ("nevo", "limits"))

    ui.heading("Which food gives which vitamin and mineral", "per-food")
    ui.chart_block(C.food_coverage(src["by_food"], theme), src["by_food"], "food_x_vitamins_minerals",
                   "Each cell: how much of that vitamin or mineral this food gives, as % of the daily minimum. Hover for the "
                   "amounts. Columns marked (max) only have an upper limit, so there a full cell is not a good thing. "
                   "Every limited nutrient has a column, also one the diet has (almost) none of.", ("nevo", "limits"))

    ui.heading("Where the energy and macros come from", "macros")
    ui.chart_block(C.macro_split(src["macros"], theme), src["macros"], "food_x_macros",
                   "Each column is the day's total (in its header) split over the foods, so a column adds up to 100%. Every "
                   "macro keeps its column, also at 0 g (free sugars are often 0: the cheapest diet has no sugar, honey or "
                   "juice). Foods are sorted by how much energy they give. Hover for the grams and, for protein, "
                   "carbohydrate and fat, the % of the day's energy (4 kcal/g, fat 9).", ("nevo",))

    ui.heading("Where the money goes", "money")
    if src is c.R:
        items = [{"item": r["food"], "eur": r["eur_week"] / 7} for r in c.R["shop"]]
        note = "The shopping list per day: whole packs, pantry items spread over the weeks they last."
    else:
        items = [{"item": b["food"], "eur": b["eur_day"]} for b in c.pure["basket"]]
        note = "The basket per day. Labels: each food's share of the total."
    ui.chart_block(C.money(items, theme), items, "money", note, ("prices",))

    ui.heading("Every nutrient", "table")
    ui.nutrient_summary(src["reqs"], src.get("binding", ()))
    ui.nutrient_table(src["reqs"], "nutrients", src.get("binding", ()))
    ui.sources("nevo", "limits", "amino", "cooking")
