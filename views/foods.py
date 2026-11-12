"""Foods: every food in the catalog, with a ✗ to leave it out and a cook tick, and the allergy and category ticks.
Ticks sit in one form: clicking only changes the browser's copy, nothing reruns until Apply."""
import pandas as pd
import streamlit as st

import appcore as A
import ui

c = ui.ctx()
ss, chain, pure = c.ss, c.chain, c.pure

st.title("Foods")
st.caption(f"Every food with NEVO values and a price at {ui.chain_name(chain)}: leave foods out, count them cooked or raw, "
           "and tick off whole categories. Your ticks apply to every page.")

F = A.foods_table(profile=c.person, chain=chain, cooked=True, min3=ss.min3, keep=sorted(c.own_keys), flip=c.flip)
df = pd.DataFrame(F["rows"])
df.insert(0, "✗", df.key.isin(c.ex))
cat_out = A.removed_by(ss.no_categories)
kind_out = A.K.removed_by(ss.no_kinds)
df["why ✗"] = ["your food, stays in" if k in c.own_keys else f"no {cat_out[k]}" if k in cat_out else
               f"kind: {kind_out[k]}" if k in kind_out else "" for k in df.key]
df["kind"] = [A.K.KIND.get(k, "") for k in df.key]
plan_g = pure["grams"] if pure["ok"] else {}
df["g/day in plan"] = [plan_g.get(k, 0.0) for k in df.key]
df["reduced cost"] = [pure["rc"].get(k) if pure["ok"] else None for k in df.key]
df["sold at"] = ["" if n is None or pd.isna(n) else f"{int(n)}{' ⚠' if n < 3 else ''}" for n in df.chains]
df["cook note"] = ["⚠ meant to be cooked" if w else "" for w in df.raw_warn]


def shown_foods(df, q):
    if not q:
        return df
    has = lambda col: df[col].str.contains(q, case=False, regex=False)
    return df[has("food") | has("group") | has("kind")]


def category_boxes():
    """The allergy and category ticks, inside the Foods form, each set in an expander. {category key: ticked}"""
    out = {}

    def boxes(cats):
        tick_cols = st.columns(5)
        for i, cat in enumerate(cats):
            out[cat["key"]] = tick_cols[i % 5].checkbox(f"No {cat['label']}", value=cat["key"] in ss.no_categories,
                                                        key=f"nocat_{cat['key']}",
                                                        help=f"{cat['covers']} ({cat['n']} foods)")

    allergies, cats = A.categories(allergies=True), A.categories()
    n_a = sum(a["key"] in ss.no_categories for a in allergies)
    n_c = sum(x["key"] in ss.no_categories for x in cats)
    with st.expander(f"Allergies and intolerances ({n_a} ticked)", expanded=bool(n_a)):
        st.warning("**No guarantee, and not medical advice.** NEVO has no allergen data, so this is worked out from names, "
                   "food groups and typical recipes, and when in doubt a food goes out. Real products differ and can carry "
                   "traces, so read the label of everything you buy. With a serious allergy or coeliac disease, follow your "
                   "doctor or dietitian.")
        boxes(allergies)
    with st.expander(f"Leave out whole categories ({n_c} ticked)", expanded=bool(n_c)):
        st.caption("A tick removes every food with that in it (NEVO's recipes say what's in what), and in the realistic plan "
                   "every dinner with it as an ingredient. Oil, salt, sugar, yeast and the like only stop being eaten as "
                   "such: dinners keep their spoonful, or there would be almost nothing left to cook. A food in My foods "
                   "stays in whatever you tick. These are preferences: for an allergy, use the ticks above.")
        boxes(cats)
    return out


st.multiselect("Nutrient columns (per 100 g, as counted: cooked or raw)", list(F["units"]), key="food_columns")
q = st.text_input("Search", placeholder="filter by name, group or kind, e.g. milk, legume, pasta", key="food_q")
cols = ["✗", "cook", "food", "kind"] + (["why ✗"] if c.own_keys or cat_out or kind_out else []) + (["cook note"] if df.raw_warn.any() else []) + \
       ["group", "sold at", "€/100 g", "g/day in plan", "reduced cost", "product", "pack"] + list(ss.food_columns)
cfg = {"✗": st.column_config.CheckboxColumn("✗", help="leave this food out", width="small"),
       "why ✗": st.column_config.TextColumn(width="medium"),
       "kind": st.column_config.TextColumn(help="A group of similar foods. Leave out a whole kind with the list above the table."),
       "sold at": st.column_config.TextColumn(help="How many of the 10 chains sell this food. ⚠ = fewer than 3."),
       "€/100 g": st.column_config.NumberColumn(format="€%.3f", help="Per 100 g as bought, of the edible part."),
       "g/day in plan": st.column_config.NumberColumn(format="%.0f", help="In the pure LP's plan (0 = not in it)."),
       "reduced cost": st.column_config.NumberColumn(
           format="€%.3f", help="How much the price per 100 g must drop before the LP would use the food: 0 = in the "
                                "basket; below 0 = it would save a little, but less than the cost per food.")}
for n in ss.food_columns:
    cfg[n] = st.column_config.NumberColumn(n if n == F["units"][n] else f"{n} ({F['units'][n]})", format="%.4g")

b = st.columns([1.3, 1.3, 1.3, 2.7])
# Without a search "all" means every food, also those this chain doesn't sell, so another chain doesn't bring them back.
shown = set(shown_foods(df, q).key) if q else set(A.P.FOODS) | set(df.key)
bulk = None
if b[0].button("Exclude all foods shown" if q else "Exclude all foods", width="stretch"):
    bulk = set(ss.excluded) | shown
if b[1].button("Put back all foods shown" if q else "Put back all foods", width="stretch"):
    bulk = set(ss.excluded) - shown
if bulk is not None:
    ss.excluded, ss.editor_v = sorted(bulk), ss.editor_v + 1
    st.rerun()
with b[2]:
    ui.download_csv(df[[x for x in cols if x not in ("✗",)] + ["key"]].assign(excluded=df["✗"]), "foods", "This table (CSV)")
st.caption("Tick ✗ to leave a food out, and *cook* to count it cooked (unticked: raw; empty: eaten as sold); pick whole "
           "**kinds** (all pasta, all rice ...) or **categories** to leave out. As many as you like, then press **Apply**: "
           "nothing changes before that. Apply before you search, or unapplied ticks are lost. A food a kind or category "
           "removes stays ✗ until that is undone.")

view = shown_foods(df, q)
locked = set(cat_out) | set(kind_out) | c.own_keys
with st.form("foods_form", border=False):
    top = ui.apply_button(key="foods_apply_top")
    kinds_pick = st.multiselect(
        "Leave out whole kinds", A.K.KINDS, default=[k for k in ss.no_kinds if k in A.K.KINDS],
        format_func=lambda k: f"{k} ({A.K.COUNT[k]})", key=f"foods_kinds_{ss.editor_v}",
        placeholder="e.g. pasta and noodles, rice, wheat flour",
        help="A kind is a group of similar foods (the kind column). Leaving one out is a ✗ on each of its foods, also the "
             "ones this chain doesn't sell. In the realistic week the dinners made with them go too.")
    cats = category_boxes()
    st.markdown(f"**{len(view)} foods**" + (f" matching '{q}'" if q else ""))
    edited = st.data_editor(view[cols + ["key"]], hide_index=True, width="stretch", height=620,
                            column_config={**cfg, "cook": ui.cook_col(), "key": None},
                            disabled=[c_ for c_ in cols if c_ not in ("✗", "cook")],
                            key=f"foods_{ss.editor_v}_{q}_{len(cols)}")
    bottom = ui.apply_button(key="foods_apply_bottom")
if top or bottom:
    ticked = set(edited.loc[edited["✗"].eq(True), "key"])       # eq: selecting cells and pressing Delete leaves None
    single = set(ss.excluded)
    ss.excluded = sorted((single - set(view.key)) | (single & locked) | (ticked - locked))
    ss.no_categories = sorted(k for k, v in cats.items() if v)
    ss.no_kinds = sorted(kinds_pick)
    ss.cook_flip = ui.cook_flips(edited)
    ss.editor_v += 1
    st.rerun()
ui.sources("nevo", "prices", "cooking")
