"""Dishes: NEVO's mixed dishes and soups that can be priced at the chain from their recipe's ingredients."""
import pandas as pd
import streamlit as st

import appcore as A
import ui

c = ui.ctx()
ss, chain = c.ss, c.chain

st.title("Dishes")
if chain == A.ALL_CHAINS:
    st.info("Pick a chain in the sidebar: a dish is priced from the ingredients sold at one chain.")
else:
    Dt = A.dishes_table(chain=chain)
    dd = pd.DataFrame(Dt["rows"]).sort_values("€/100 g").reset_index(drop=True)
    st.caption(f"{len(dd)} of NEVO's {Dt['n_total']} dishes and soups can be priced at {ui.chain_name(chain)} from their "
               "recipe's ingredients. The ones with a name under *dinner* are the realistic week's dinners "
               "(`data/dinners.tsv`). Nutrients are NEVO's own values for the dish, per 100 g. **Click a row** for its "
               "ingredients and stand-ins.")
    st.multiselect("Nutrient columns (per 100 g)", list(A.FOOD_COLS), key="dish_columns")
    dcols = ["dish", "dinner", "€/100 g", "€ per 400 g", "group"] + [c_ for c_ in ss.dish_columns if c_ in dd]
    sel = st.dataframe(dd[dcols], hide_index=True, width="stretch", height=520, on_select="rerun",
                       selection_mode="single-row", key="dish_table",
                       column_config={"€/100 g": st.column_config.NumberColumn(format="€%.3f"),
                                      "€ per 400 g": st.column_config.NumberColumn(format="€%.2f",
                                                                                    help="A dinner portion of 400 g."),
                                      "dinner": st.column_config.TextColumn("dinner", help="As in the dinner list")})
    ui.download_csv(dd.drop(columns=["code"]), f"dishes_{chain}", "This table with ingredients (CSV)")
    rows_sel = sel.selection.rows
    if rows_sel:
        r = dd.iloc[rows_sel[0]]
        with st.container(border=True):
            st.markdown(f"**{r.dish}** ({r.dutch}, NEVO {r.code}), €{r['€/100 g']:.3f} per 100 g")
            st.markdown(f"Bought per 100 g of dish: {r.ingredients}")
            if r.substitutes:
                st.markdown(f"Priced via a stand-in: {r.substitutes}")
            if r["left out"]:
                st.markdown(f"Left out (under 1.5% of the dish, not sold): {r['left out']}")
    ui.sources("recipes", "nevo", "prices")
