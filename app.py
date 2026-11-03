"""nevo-diet app.  ./app.sh  (or: streamlit run app.py)

Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources.
"""
import zipfile

import pandas as pd
import streamlit as st

import setup_data

NEVO_LINE = "Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources."
st.set_page_config(page_title="nevo-diet", page_icon="🥦", layout="wide")

# ---------------- first run: the NEVO dataset (the model can't even be imported without it) ----------------
if setup_data.missing():
    st.markdown("### nevo-diet · the cheapest adequate Dutch diet")
    st.markdown("This app needs the **NEVO food composition dataset**. It's free, but only RIVM may hand it out, so it "
                "doesn't come with the app. You only do this once per computer.")
    st.markdown("**1. Request the dataset.** Fill in your email and accept the conditions, and RIVM emails you a download link.")
    st.link_button("Request the NEVO dataset from RIVM", setup_data.REQUEST_URL, type="primary")
    st.markdown("**2. Add the zip here.**")
    upload = st.file_uploader("NEVO zip file", type="zip", label_visibility="collapsed")
    if upload is not None:
        try:
            ok = setup_data.extract(upload)
        except zipfile.BadZipFile:
            ok = False
        if ok:
            st.rerun()
        st.error("That zip doesn't hold the NEVO 2025/9.0 files: " + " and ".join(setup_data.REQUIRED) + ".")
    st.caption(NEVO_LINE)
    st.stop()

import appcore as A  # noqa: E402
import charts as C  # noqa: E402

# ---------------- settings (saved per computer in ~/.config/nevo-diet/settings.json) ----------------
ss = st.session_state
# Widget state can be dropped by Streamlit (e.g. a run that ends in st.rerun() before a widget is drawn), so any
# missing key is refilled from the settings file, which is saved on every change.
_saved = A.load_settings()
for k, v in _saved.items():
    if k not in ss:
        ss[k] = v
ss.setdefault("editor_v", 0)
ss.setdefault("limits_v", 0)
ss.setdefault("own_v", 0)
if "switch_profile" in ss:          # a saved or deleted profile: only now, before the widgets exist, can they be changed
    ss.profile = ss.pop("switch_profile")
    ss.weight = ss.height = ss.kcal = ss.protein = None
A.set_limit(ss.cache_mb)
theme = "dark" if (getattr(st.context, "theme", None) and st.context.theme.type == "dark") else "light"
profiles, chains = A.profiles(), A.chains()
if ss.profile not in profiles:
    ss.profile = "avg_man"

st.markdown("### nevo-diet · the cheapest adequate Dutch diet")
c = st.columns([2.2, 1.6, 1.1, 1.3, 1.0])
c[0].selectbox("Profile", list(profiles), format_func=profiles.get, key="profile")
chain_col = c[1]
chain_opts = [A.CHEAPEST] + (chains if ss.mode == "realistic" else [A.ALL_CHAINS] + chains)
# Set it even when it's unchanged: without this the selectbox falls back to its first option when the list changes.
ss.chain = ss.chain if ss.chain in chain_opts else "ah"
c[1].selectbox("Chain", chain_opts, key="chain",
               format_func=lambda x: {A.ALL_CHAINS: "all chains (cheapest per food)",
                                      A.CHEAPEST: "cheapest chain (automatic)"}.get(x, x))
c[2].radio("Composition", [True, False], key="cooked", horizontal=True, format_func=lambda b: "cooked" if b else "raw")
c[3].radio("Mode", ["pure", "realistic"], key="mode", horizontal=True,
                       help="Pure: the bare LP (grams per day, any food). Realistic: a week of meals with whole "
                            "packs and the soft rules, solved on the Solve button.")
c[4].number_input("Budget €/day", min_value=0.5, max_value=20.0, step=0.25, key="budget")
# Blank = the profile's value, shown greyed out. Calories and protein follow weight and height until you type a target.
_body = A.person_info(A.person(ss.profile, ss.weight, ss.height))
c = st.columns(4)
c[0].number_input("Weight (kg)", min_value=30.0, max_value=250.0, step=1.0, value=None, key="weight", format="%.1f",
                  placeholder=f"{_body['weight']:.1f}")
c[1].number_input("Height (cm)", min_value=120.0, max_value=230.0, step=1.0, value=None, key="height", format="%.0f",
                  placeholder=f"{_body['height']:.0f}" if _body["height"] else "not set",
                  help="With a height, calories are estimated from weight, height, age and activity (Henry 2005, as in the Dutch norms).")
c[2].number_input("Calories target (kcal/day)", min_value=800.0, max_value=8000.0, step=50.0, value=None, key="kcal",
                  format="%.0f", placeholder=f"auto: {_body['kcal']:.0f}",
                  help="The diet stays between this and 4% above it. Blank: estimated from your body and activity.")
c[3].number_input("Protein target (g/day)", min_value=10.0, max_value=500.0, step=5.0, value=None, key="protein",
                  format="%.0f", placeholder=f"auto: {_body['protein']:.0f}",
                  help="A minimum: the diet has at least this much. Blank: the profile's g/kg x your weight.")
person = A.person(ss.profile, ss.weight, ss.height, ss.kcal, ss.protein)
c = st.columns([1.6, 1.2, 1.1, 1.6, 2.3])
real = ss.mode == "realistic"
c[0].radio("Strictness", ["strict", "medium", "loose"], key="strictness", horizontal=True, disabled=not real,
                       help="Strict: no rule bent. Medium: a rule may be bent if that saves ≥ €0.25/day. "
                            "Loose: ≥ €0.10/day.")
c[1].radio("Meals", ["brunch", "classic"], key="pattern", horizontal=True, disabled=not real,
                       help="Brunch: brunch + warm dinner (+ leftovers) + snacks. Classic: breakfast, lunch, dinner.")
c[2].toggle("Batch cooking", key="batch", disabled=not real, help="One weekend session for pulses and soup.")
c[3].toggle("Only foods sold at ≥ 3 chains", key="min3", disabled=real,
            help="Realistic mode always uses only those for foods eaten as such.")
settings = {k: ss[k] for k in A.DEFAULTS}
settings["excluded"] = sorted(ss.excluded)
if settings != _saved:
    A.save_settings(settings)

own = A.own_spec(ss.my_foods)
own_keys = {o[0] for o in own}
ex = tuple(A.effective_excluded(ss.excluded, ss.no_categories, own))
pure_rank_kw = dict(profile=person, cooked=ss.cooked, excluded=list(ex), min3=ss.min3, own=own)
week_kw = dict(profile=person, cooked=ss.cooked, excluded=sorted(ss.excluded), strictness=ss.strictness,
               pattern=ss.pattern, batch=ss.batch, no_cats=sorted(ss.no_categories), own=own)
# "cheapest" resolves to a real chain here, from the current settings: everything below uses `chain`, never ss.chain.
# In realistic mode that takes a week at every chain, so until Solve the pure LP's pick stands in and no week is shown.
auto = ss.chain == A.CHEAPEST
week_ranked = not (auto and real) or A.week_prices.is_cached(**week_kw)
ranking, chain = None, ss.chain
if auto:
    ranking = A.week_prices(**week_kw) if real and week_ranked else A.chain_prices(**pure_rank_kw)
    chain = ranking["best"] or A.DEFAULTS["chain"]
    if not ranking["best"]:
        chain_col.caption("No chain has a plan with these settings.")
    elif not week_ranked:
        chain_col.caption(f"Press **Solve** to compare a week at every chain. Cheapest in the pure LP: **{chain}**.")
    else:
        chain_col.caption(f"→ **{chain}**, €{ranking['rows'][0]['cost']:.2f} a day")
pure_kw = dict(chain=chain, **pure_rank_kw)
real_kw = dict(chain=chain, **week_kw)
# The plan the before-and-after compares with: the same one without your own foods. The category ticks stay on in both,
# unless the switch says otherwise or they're all there is to take away.
drop_ticks = bool(ss.no_categories) and (ss.compare_ticks or not own)
compare_with = ("without your foods and category ticks" if own and drop_ticks else "without your foods" if own else
                "without your category ticks" if drop_ticks else None)
base_cats = [] if drop_ticks else sorted(ss.no_categories)
base_pure_kw = {**pure_kw, "excluded": A.effective_excluded(ss.excluded, base_cats), "own": []}
base_real_kw = {**real_kw, "no_cats": base_cats, "own": []}

with c[4]:
    if real:
        known = week_ranked and A.realistic.is_cached(**real_kw) and (not compare_with or A.realistic.is_cached(**base_real_kw))
        if st.button("Solve" if not known else "Solved ✓ (cached)", type="primary", disabled=known,
                     width="stretch"):
            if not week_ranked:         # each week is cached on its own, so an interrupted run picks up where it stopped
                bar = st.progress(0.0)
                for i, ch in enumerate(chains):
                    bar.progress(i / len(chains), f"Solving a week at {ch} ({i + 1} of {len(chains)}) ...")
                    A.realistic(chain=ch, **week_kw)
                chain = A.week_prices(**week_kw)["best"] or A.DEFAULTS["chain"]
                bar.empty()
            with st.spinner("Solving a week of meals (about 10 s, twice with a before-and-after) ..."):
                A.realistic(**{**real_kw, "chain": chain})
                if compare_with:
                    A.realistic(**{**base_real_kw, "chain": chain})
            st.rerun()
    if ex:
        st.caption(f"{len(ex)} food(s) excluded: " + ", ".join(A.label(k) for k in ex[:6]) + (" …" if len(ex) > 6 else ""))

pure = A.pure(**pure_kw)
R = A.realistic(**real_kw) if real and week_ranked and A.realistic.is_cached(**real_kw) else None
R_base = A.realistic(**base_real_kw) if real and week_ranked and compare_with and A.realistic.is_cached(**base_real_kw) else None


def tile(col, label, value, sub="", delta=None, help=None):
    col.metric(label, value, delta=delta, delta_color="inverse", help=help)     # inverse: dearer is red, cheaper is green
    if sub:
        col.caption(sub)


def show_table(df, **kw):
    st.dataframe(df, hide_index=True, width="stretch", **kw)


def chart_block(chart, data, name, note=None):
    h = chart.to_dict().get("height")
    st.altair_chart(chart, width="stretch", theme=None,
                    height=int(h) + 130 if isinstance(h, (int, float)) else "content")
    if note:
        st.caption(note)
    with st.expander("Table and export"):
        show_table(pd.DataFrame(data))
        b = st.columns(4)
        b[0].download_button("Data (CSV)", pd.DataFrame(data).to_csv(index=False).encode(), f"{name}.csv",
                             "text/csv", key=f"dl_{name}_csv")
        b[1].download_button("Chart (HTML, exports PNG/SVG)", chart.to_html().encode(), f"{name}.html",
                             "text/html", key=f"dl_{name}_html")


def nutrient_table(reqs, binding=()):
    rows_ = []
    for r in reqs:
        need = " – ".join(x for x in [f"≥ {r['lower']:.4g}" if r["lower"] else "",
                                       f"≤ {r['upper']:.4g}" if r["upper"] else ""] if x)
        rows_.append({"": "✓" if r["ok"] else "✗", "nutrient": r["nutrient"], "intake": float(f"{r['intake']:.4g}"),
                      "unit": r["unit"], "requirement": need,
                      "% of minimum": round(r["pct_lower"]) if r["pct_lower"] is not None else None,
                      "% of maximum": round(r["pct_upper"]) if r["pct_upper"] is not None else None,
                      "binding": "binding" if r["name"] in binding else ""})
    df = pd.DataFrame(rows_)
    show_table(df, height=35 * len(df) + 38)


def split_note(result):
    """Under the price: what your own foods cost and what the rest costs."""
    return f"your foods €{result['own_eur']:.2f}, the rest €{result['cost'] - result['own_eur']:.2f}" if own else ""


def per_of(key):
    return next((f.get("per", "day") for f in ss.my_foods if f["key"] == key), "day")


def my_foods_box():
    """Pick foods you'll eat anyway, with an amount; the plan fills in the rest around them."""
    with st.container(border=True):
        st.markdown("**My foods** · what you want to eat anyway. The plan fills in the rest around it. "
                    "Double-click a cell to change it.")
        choices = A.food_choices(chain)
        pick = st.selectbox("Add a food", list(choices), format_func=choices.get, index=None, key=f"own_pick_{ss.own_v}",
                            placeholder="Add a food: type to search, e.g. milk", label_visibility="collapsed")
        if pick:
            if pick not in [f["key"] for f in ss.my_foods]:
                ss.my_foods = [*ss.my_foods, {"key": pick, "grams": 100.0, "how": "exactly", "per": "day"}]
            ss.own_v += 1
            st.rerun()
        if not ss.my_foods:
            return
        shown = pd.DataFrame([{"✗": False, "food": A.label(f["key"]), "grams": f["grams"], "how": f["how"], "per": f["per"],
                               "key": f["key"]} for f in ss.my_foods])
        edited = st.data_editor(
            shown, hide_index=True, width="stretch", key=f"own_{ss.own_v}", disabled=["food"],
            column_config={
                "✗": st.column_config.CheckboxColumn("✗", help="remove from My foods", width="small"),
                "grams": st.column_config.NumberColumn("grams", min_value=1, max_value=50000, step=10, format="%.0f",
                                                       help="As bought, like the rest of the app: dry pasta, raw meat."),
                "how": st.column_config.SelectboxColumn("how much", options=["exactly", "at least"], required=True,
                                                        help="At least: the plan may add more if that's cheaper."),
                "per": st.column_config.SelectboxColumn("per", options=["day", "week"], required=True),
                "key": None})
        new = [{"key": r["key"], "grams": old["grams"] if pd.isna(r["grams"]) else float(r["grams"]), "how": r["how"], "per": r["per"]}
               for r, old in zip(edited.to_dict("records"), ss.my_foods) if not r["✗"]]
        if new != ss.my_foods:
            ss.my_foods = new
            ss.own_v += 1
            st.rerun()
        away = [A.label(k) for k in own_keys if not any(r["chain"] == chain for r in A.prices_of(k))]
        if away and chain != A.ALL_CHAINS:
            st.caption(f"⚠ Not sold at {chain}, so priced at the cheapest other chain: " + ", ".join(sorted(away)) + ".")


def impossible(why, intro):
    """No plan: say what's in the way, and how much of each of your own foods would still work."""
    lines = [f"- **{m['nutrient']}** would be {m['intake']:,.4g} {m['unit']}; the {m['side']} is {m['limit']:,.4g}."
             for m in why["misses"]]
    if why.get("rules"):
        lines.append(f"- The meal rules leave no room: {why['n_dinners']} dinner(s) are left with these settings. "
                     "Try a looser strictness, or take off a category tick.")
    for a in why["amounts"]:
        per = per_of(a["key"])
        f = 7 if per == "week" else 1
        if a["most"] is None:
            lines.append(f"- **{a['food']}**: no amount works with your other foods and ticks.")
        elif a["wanted"] > a["most"]:
            lines.append(f"- **{a['food']}**: the most that still works is {f * a['most']:,.0f} g a {per} "
                         f"(you asked for {f * a['wanted']:,.0f} g).")
        elif a["least"] and a["wanted"] < a["least"]:
            lines.append(f"- **{a['food']}**: it needs at least {f * a['least']:,.0f} g a {per} "
                         f"(you asked for {f * a['wanted']:,.0f} g).")
    st.error(intro + "\n\n" + "\n".join(lines))


def change_note(now, before):
    """For the price tile: what your foods and ticks do to the price, and compared with what."""
    if not compare_with or before is None or not before["ok"]:
        return {}
    d = now["cost"] - before["cost"]
    return {"delta": f"{'+' if d >= 0 else '-'}€{abs(d):.2f}", "help": f"Compared with the plan {compare_with}."}


def compare_block(now, before, dinners=False):
    """The before-and-after, folded away under the plan: the tile on top already has the price change. The label stays
    the same whatever is compared, because an expander closes itself when its label changes."""
    if not compare_with:
        return
    with st.expander("What changed in the rest of the plan"):
        if own and ss.no_categories:
            st.toggle("Also compare without the category ticks", key="compare_ticks",
                      help="Off: what your own foods change. On: what your own foods and the ticks change together.")
        if before is None:
            st.info(f"Press **Solve** to compare with the plan {compare_with}.")
        elif not before["ok"]:
            st.info(f"There is no adequate plan {compare_with}, so there is nothing to compare with.")
        else:
            d = now["cost"] - before["cost"]
            st.markdown(f"Compared with the plan {compare_with}: €{before['cost']:.2f} → €{now['cost']:.2f} a day "
                        f"({'+' if d >= 0 else '−'}€{abs(d):.2f}). ★ = your food.")
            rows_ = A.compare(now, before, own)
            if rows_:
                show_table(pd.DataFrame(rows_), height=35 * len(rows_) + 38, column_config={
                    "before": st.column_config.NumberColumn("before (g/day)", format="%.0f"),
                    "now": st.column_config.NumberColumn("now (g/day)", format="%.0f"),
                    "change": st.column_config.NumberColumn("change (g/day)", format="%+.0f"),
                    "€/day change": st.column_config.NumberColumn(format="%+.3f")})
            if dinners:
                changed = A.compare_dinners(now, before)
                if changed:
                    show_table(pd.DataFrame(changed))


def ranking_block():
    """With "cheapest": what the other chains would have cost. The label stays the same, see compare_block."""
    if not ranking:
        return
    with st.expander("Every chain compared"):
        show_table(pd.DataFrame(ranking["rows"]).rename(columns={"cost": "€/day", "bent": "rules bent"}),
                   column_config={"€/day": st.column_config.NumberColumn(format="%.2f")})
        st.caption("Empty: no plan at that chain with these settings. The chain is picked on price alone"
                   + (", so a cheaper week may bend more meal rules." if real else "."))


def _tick(key):
    on = ss[f"nocat_{key}"]
    ss.no_categories = sorted((set(ss.no_categories) | {key}) if on else (set(ss.no_categories) - {key}))


tabs = st.tabs(["Plan", "Foods", "Dishes", "Charts", "Profile & limits", "Settings"])

# ---------------- Plan ----------------
with tabs[0]:
    my_foods_box()
    if not real:
        if not pure["ok"]:
            impossible(pure["why"], "**No adequate diet with these settings.** Change your own foods, put back excluded "
                                    "foods or categories, or change the calories or protein target.")
        else:
            t = st.columns(4)
            pure_base = A.pure(**base_pure_kw) if compare_with else None
            tile(t[0], "€ per day", f"€{pure['cost']:.2f}", split_note(pure), **change_note(pure, pure_base))
            tile(t[1], "€ per week", f"€{7 * pure['cost']:.2f}")
            over = pure["cost"] - ss.budget
            tile(t[2], "Budget", "within budget" if over <= 0 else f"€{over:.2f} over",
                 f"budget €{ss.budget:.2f}/day")
            tile(t[3], "Foods in the basket", str(len(pure["basket"])), f"of {pure['n_foods']} available")
            st.caption("**Pure** is the bare linear program: the cheapest grams per day that meet every requirement. "
                       "It may use raw flour, odd amounts and foods from different chains. Switch to *realistic* "
                       "for meals, whole packs and a shopping list.")
            ranking_block()
            df = pd.DataFrame(pure["basket"])
            df["chains"] = [f"{n}{' ⚠' if n < 3 else ''}" for n in df.n_chains]
            df["cap"] = ["your food" if m_ else "at cap" if c_ else "" for m_, c_ in zip(df.mine, df.at_cap)]
            df["food"] = [f"{f_} ★" if m_ else f_ for f_, m_ in zip(df.food, df.mine)]
            df["chain"] = [f"{c_} ⚠" if a_ else c_ for c_, a_ in zip(df.chain, df.away)]
            show_table(df[["food", "amount", "eur_day", "product", "chain", "chains", "cap"]].rename(
                columns={"eur_day": "€/day"}), height=35 * len(df) + 38, column_config={"€/day": st.column_config.NumberColumn(format="%.3f")})
            compare_block(pure, pure_base)
            st.markdown("**Nutrients** (✓ met, binding = the requirement that sets the price)")
            nutrient_table(pure["reqs"], pure["binding"])
    elif R is None:
        st.info(("Realistic mode solves a week of meals (about 10 s per setting). " if week_ranked else
                 f"The cheapest chain takes a week of meals at all {len(chains)} chains (about a minute). ") +
                "Press **Solve** above. Results are cached, so settings you solved before show at once.")
    elif not R["ok"]:
        impossible(R["why"], "**No feasible week with these settings.** Change your own foods, take off a category tick, "
                             "or try a looser strictness.")
    else:
        t = st.columns(4)
        tile(t[0], "€ per day", f"€{R['cost']:.2f}", split_note(R), **change_note(R, R_base))
        tile(t[1], "€ per week", f"€{7 * R['cost']:.2f}")
        over = R["cost"] - ss.budget
        tile(t[2], "Budget", "within budget" if over <= 0 else f"€{over:.2f} over", f"budget €{ss.budget:.2f}/day")
        tile(t[3], "vs pure LP", f"+€{R['cost'] - pure['cost']:.2f}" if pure["ok"] else "-",
             "price of meals, packs and rules")
        ranking_block()
        if R["bent"]:
            st.warning("Rules bent: " + "; ".join(
                f"**{b['rule']}** (keeping it costs €{b['saving_day']:.2f}/day more)" if b["saving_day"] is not None
                else f"**{b['rule']}** (keeping it is infeasible)" for b in R["bent"]))
        else:
            st.success("All meal rules kept.")
        st.markdown(f"**Dinners** ({R['n_dishes']} NEVO dishes priceable at {chain})")
        show_table(pd.DataFrame(R["dinners"]).rename(columns={"g_per_evening": "g per evening",
                                                              "hands_on_min": "hands-on min", "eur_portion": "€/portion"}),
                   column_config={"g per evening": st.column_config.NumberColumn(format="%.0f"),
                                  "€/portion": st.column_config.NumberColumn(format="%.2f")})
        a, b = st.columns([1, 1.6])
        with a:
            st.markdown("**Eaten as such** (brunch, sides, snacks)")
            show_table(pd.DataFrame(R["direct"])[["food", "amount", "group"]])
        with b:
            st.markdown("**Shopping list**")
            show_table(pd.DataFrame(R["shop"]).rename(columns={"eur_week": "€/week"}),
                       column_config={"€/week": st.column_config.NumberColumn(format="%.2f")})
        compare_block(R, R_base, dinners=True)
        st.markdown("**Nutrients per day**")
        nutrient_table(R["reqs"])

# ---------------- Foods ----------------
with tabs[1]:
    st.markdown("**Leave out whole categories**")
    st.caption("A tick removes every food with that in it (NEVO's recipes say what's in what), and in the realistic plan every "
               "dinner with it as an ingredient. Oil, salt, sugar, yeast and the like only stop being eaten as such: "
               "dinners keep their spoonful, or there would be almost nothing left to cook. A food in My foods stays in "
               "whatever you tick. These are preferences, **not allergy protection**: recipes are typical ones, and real "
               "products can differ or carry traces.")
    tick_cols = st.columns(5)
    for i, cat in enumerate(A.categories()):
        tick_key = f"nocat_{cat['key']}"
        ss[tick_key] = cat["key"] in ss.no_categories
        tick_cols[i % 5].checkbox(f"No {cat['label']}", key=tick_key, on_change=_tick, args=(cat["key"],),
                                  help=f"{cat['covers']} ({cat['n']} foods)")
    F = A.foods_table(profile=person, chain=chain, cooked=ss.cooked, min3=ss.min3, keep=sorted(own_keys))
    df = pd.DataFrame(F["rows"])
    df.insert(0, "✗", df.key.isin(ex))
    cat_out = A.removed_by(ss.no_categories)
    df["why ✗"] = ["your food, stays in" if k in own_keys else f"no {cat_out[k]}" if k in cat_out else "" for k in df.key]
    plan_g = pure["grams"] if pure["ok"] else {}
    if real and R and R["ok"]:
        st.caption("Grams below are from the pure LP; the realistic plan is on the Plan tab.")
    df["g/day in plan"] = [plan_g.get(k) for k in df.key]
    df["reduced cost"] = [pure["rc"].get(k) if pure["ok"] else None for k in df.key]
    df["chains"] = [f"{n}{' ⚠' if n < 3 else ''}" for n in df.chains]
    nut = list(F["units"])
    st.multiselect("Nutrient columns (per 100 g)", nut, key="food_columns")
    q = st.text_input("Search", placeholder="filter by name or group", key="food_q")
    view = df if not q else df[df.food.str.contains(q, case=False) | df.group.str.contains(q, case=False)]
    cols = ["✗", "food"] + (["why ✗"] if own_keys or cat_out else []) + \
           ["group", "chains", "€/100 g", "g/day in plan", "reduced cost", "product", "pack"] + list(ss.food_columns)
    st.caption("Tick ✗ to exclude a food; the plan re-solves at once. A food a category removes stays ✗ until that tick is "
               "off. Reduced cost: how much the price per 100 g must drop before the LP would use the food (0 = in the "
               "basket). ⚠ = sold at fewer than 3 chains.")
    cfg = {"✗": st.column_config.CheckboxColumn("✗", help="exclude this food", width="small"),
           "why ✗": st.column_config.TextColumn(width="medium"),
           "€/100 g": st.column_config.NumberColumn(format="%.3f"),
           "g/day in plan": st.column_config.NumberColumn(format="%.0f"),
           "reduced cost": st.column_config.NumberColumn(format="%.3f")}
    for n in ss.food_columns:
        cfg[n] = st.column_config.NumberColumn(f"{n} ({F['units'][n]})", format="%.4g")
    edited = st.data_editor(view[cols + ["key"]], hide_index=True, width="stretch", height=620,
                            column_config={**cfg, "key": None},
                            disabled=[c_ for c_ in cols if c_ != "✗"], key=f"foods_{ss.editor_v}")
    ticked = set(edited.loc[edited["✗"], "key"])
    if ticked != set(view.key) & set(ex):       # a change, or a click on a row that a tick or My foods decides: back it goes
        single, locked = set(ss.excluded), set(cat_out) | own_keys
        ss.excluded = sorted((single - set(view.key)) | (single & locked) | (ticked - locked))
        ss.editor_v += 1
        st.rerun()
    if ss.excluded and st.button("Put back all excluded foods"):
        ss.excluded = []
        ss.editor_v += 1
        st.rerun()

# ---------------- Dishes ----------------
with tabs[2]:
    if chain == A.ALL_CHAINS:
        st.info("Pick a chain: a dish is priced from the ingredients sold at one chain.")
    else:
        Dt = A.dishes_table(chain=chain)
        dd = pd.DataFrame(Dt["rows"])
        st.caption(f"{len(dd)} of NEVO's {Dt['n_total']} dishes and soups can be priced at {chain} from their "
                   "ingredients. Nutrients are NEVO's own values for the dish, per 100 g. Click a row for its "
                   "ingredients and substitutions.")
        st.multiselect("Nutrient columns (per 100 g)", list(A.FOOD_COLS), key="dish_columns")
        dcols = ["dish", "dinner", "€/100 g", "€ per 400 g", "group"] + [c_ for c_ in ss.dish_columns if c_ in dd]
        sel = st.dataframe(dd[dcols].sort_values("€/100 g"), hide_index=True, width="stretch", height=520,
                           on_select="rerun", selection_mode="single-row",
                           column_config={"€/100 g": st.column_config.NumberColumn(format="%.3f"),
                                          "€ per 400 g": st.column_config.NumberColumn(format="%.2f"),
                                          "dinner": st.column_config.TextColumn("in the dinner list as")})
        rows_sel = sel.selection.rows
        if rows_sel:
            r = dd.sort_values("€/100 g").iloc[rows_sel[0]]
            st.markdown(f"**{r.dish}** ({r.dutch}, NEVO {r.code}), €{r['€/100 g']:.3f} per 100 g")
            st.markdown(f"Bought per 100 g of dish: {r.ingredients}")
            if r.substitutes:
                st.markdown(f"Priced via a stand-in: {r.substitutes}")
            if r["left out"]:
                st.markdown(f"Left out (under 1.5% of the dish, not sold): {r['left out']}")

# ---------------- Charts ----------------
with tabs[3]:
    if not pure["ok"]:
        st.error("No adequate diet with these settings.")
    else:
        src = R if (real and R and R["ok"]) else pure
        tag = "realistic week" if src is R else "pure LP"
        st.markdown(f"#### 1. Nutrient coverage ({tag})")
        chart_block(C.coverage(src["reqs"], theme), [{k: r[k] for k in ("nutrient", "intake", "unit", "lower", "upper",
                                                                        "pct_lower")} for r in src["reqs"]],
                    "coverage", "Blue bars sit on the 100% line: those requirements set the price. "
                                "Red ✗ = a minimum missed.")
        st.markdown(f"#### 1b. Which food covers which micronutrient ({tag})")
        chart_block(C.food_coverage(src["by_food"], theme), src["by_food"], "food_coverage",
                    "Each cell: how much of that vitamin or mineral this food gives, as % of the daily minimum. Hover for "
                    "the amounts. Columns marked (max) only have an upper limit, so there a full cell is not a good thing.")
        st.markdown(f"#### 2. Where the money goes ({tag})")
        if src is R:
            items = [{"item": r["food"], "eur": r["eur_week"] / 7} for r in R["shop"]]
        else:
            items = [{"item": b["food"], "eur": b["eur_day"]} for b in pure["basket"]]
        chart_block(C.money(items, theme), items, "money")

        st.markdown("#### 3. Why each food is in the basket (pure LP)")
        if pure["shares"]:
            ch3, agg = C.price_split(pure["shares"], theme)
            chart_block(ch3, agg.drop(columns=["order"]), "price_split",
                        "LP duality: at the optimum a basket food's price equals Σ shadow price × nutrient content over "
                        "the binding requirements, so each bar is the food's price split by what it pays for."
                        + (" Your own foods aren't here: they're in the basket because you put them there, so this sum "
                           "doesn't hold for them." if own else ""))
        else:
            st.caption("Your own foods are the whole basket, so there's nothing for the LP to explain.")

        st.markdown("#### 4. Chains per profile (pure LP)")
        if person != ss.profile:
            st.caption("The standard profiles, without your weight, height and targets.")
        CT = A.chain_table(cooked=ss.cooked, excluded=list(ex), min3=ss.min3, own=own)
        chart_block(C.chains(CT["rows"], chain, theme), CT["rows"], "chains")

        st.markdown("#### 5. What replaces what (pure LP)")
        RM = A.removal(**pure_kw)
        ch5, df5 = C.removal(RM["nodes"], theme)
        bad = [" / ".join(n_["path"]) for n_ in RM["nodes"] if n_["infeasible"]]
        chart_block(ch5, df5.drop(columns=["node"]), "removal",
                    "Remove the biggest food, re-solve, then do the same in the new diet: three levels, three "
                    "branches each. Hover a dot to see what replaced the removed food."
                    + (" Your own foods are never removed." if own else "")
                    + (f" Infeasible (no adequate diet left): {'; '.join(bad)}." if bad else ""))

        st.markdown("#### 6. Cost curves (pure LP)")
        lows = [r for r in pure["reqs"] if r["lower"] and r["kind"] == "abs"]
        names = {r["name"]: r["nutrient"] for r in lows}
        pick = st.multiselect("Requirements to push up (at most 4)", list(names), format_func=names.get,
                              default=[n for n in ("protein", "calcium", "vitC", "fibre") if n in names],
                              max_selections=4, key="curve_pick")
        pts = []
        for n in pick:
            pts += A.cost_curve(**pure_kw, req=n)["points"]
        if pts:
            chart_block(C.cost_curves(pts, theme, ss.budget), pts, "cost_curves",
                        "The slope at 100% is the requirement's shadow price; flat means it doesn't bind. "
                        "The horizontal rule is your budget.")

        st.markdown("#### 7. Wiggle room (pure LP)")
        W = A.wiggle(**pure_kw)
        chart_block(C.wiggle(W["rows"], theme), W["rows"], "wiggle",
                    "Grey bar: the grams a food can take in any diet costing at most 5% more than the cheapest "
                    "(the near-optimal polytope, two LPs per food). Dot: the cheapest diet.")

# ---------------- Profile & limits ----------------
with tabs[4]:
    name = ss.profile
    F_ = A.profile_fields(name)
    st.markdown(f"#### Profile: {profiles[name]}")
    st.caption("Saved on this computer in `~/.config/nevo-diet/profiles.json`, outside git. "
               + ("This is one of your own profiles." if A.is_own(name) and not A.is_standard(name) else
                  "You changed this standard profile." if A.is_own(name) else "A standard profile: saving keeps your "
                  "changes next to the original, which you can always restore."))
    with st.form(f"profile_form_{name}"):
        c = st.columns([2.2, 1, 1, 1])
        label = c[0].text_input("Name", value=F_["label"])
        sex = c[1].radio("Sex", ["m", "f"], index=0 if F_["sex"] == "m" else 1, horizontal=True,
                         format_func=lambda s: "man" if s == "m" else "woman", help="Picks the men's or women's norms.")
        age = c[2].number_input("Age", min_value=18, max_value=100, value=int(F_["age"]),
                                help="Sets the energy estimate. The nutrient norms stay the 18-69 values, see the note below.")
        pal = c[3].number_input("Activity level (PAL)", min_value=1.2, max_value=2.5, step=0.05, value=round(F_["pal"], 2),
                                help="Gezondheidsraad 2022/19: 1.4 light, 1.6 moderate, 1.8 active, 2.0 very active.")
        c = st.columns(4)
        weight = c[0].number_input("Weight (kg)", min_value=30.0, max_value=250.0, value=round(F_["weight"], 1), format="%.1f")
        height = c[1].number_input("Height (cm)", min_value=120.0, max_value=230.0, step=1.0, value=F_["height"], format="%.1f",
                                   placeholder="not set")
        kcal = c[2].number_input("Fixed calories (kcal/day)", min_value=800.0, max_value=8000.0, step=50.0, value=F_["kcal"],
                                 format="%.0f", placeholder="estimate", help="Blank: estimated from body and activity.")
        per_kg = c[3].number_input("Protein (g per kg)", min_value=0.5, max_value=4.0, step=0.05, value=F_["protein_per_kg"],
                                   help="0.83 is the Dutch norm for adults. 1.4-2.0 is the ISSN's range for people who train.")
        source = st.text_input("Note or source", value=F_["source"])
        c = st.columns([1, 1, 3])
        save = c[0].form_submit_button("Save changes", type="primary")
        save_new = c[1].form_submit_button("Save as new profile")
    if save or save_new:
        same = lambda a, b: (a is None and b is None) or (a is not None and b is not None and abs(a - b) < 1e-6)
        changed = {}
        for k, new, old in [("age", age, F_["age"]), ("weight", weight, round(F_["weight"], 1)), ("height", height, F_["height"]),
                            ("pal", pal, round(F_["pal"], 2)), ("kcal", kcal, F_["kcal"]),
                            ("protein_per_kg", per_kg, F_["protein_per_kg"])]:
            if not same(new, old):
                changed[k] = new
        if kcal is None and "pal" not in changed:
            changed["pal"] = pal                      # a profile with fixed calories may have no level of its own
        if weight != round(F_["weight"], 1) or height != F_["height"] or (kcal is None and F_["kcal"] is not None):
            changed.setdefault("weight", weight)      # with weight and height both set, energy uses Henry
        for k, new, old in [("label", label, F_["label"]), ("sex", sex, F_["sex"]), ("source", source, F_["source"])]:
            if new != old:
                changed[k] = new
        if save_new and source == F_["source"]:
            changed["source"] = ""                  # the note was about the profile this one was copied from
        if kcal is None and height is None and not 18 <= age < 60:
            st.error("Fill in a height or fixed calories: there is no estimate from weight alone at this age.")
        elif save_new and label == F_["label"]:
            st.error("Give the new profile its own name.")
        else:
            ss.switch_profile = A.save_profile(name, new_name=label if save_new else None, **changed)
            st.rerun()
    if A.is_own(name):
        if st.button("Restore the original profile" if A.is_standard(name) else "Delete this profile"):
            A.delete_profile(name)
            ss.switch_profile = name if A.is_standard(name) else "avg_man"
            st.rerun()

    st.markdown("#### Minimum and maximum per nutrient")
    st.caption("Change a number, or clear it for no limit. The diet is solved again with your limits, and they are saved "
               "with this profile. Calories and protein targets in the boxes at the top change the standard values shown here. "
               "`SOURCES.md` explains where every standard value comes from and which ones newer advice has changed.")
    rows_ = A.limit_rows(person)
    df = pd.DataFrame(rows_)
    edited = st.data_editor(df, hide_index=True, width="stretch", height=560, key=f"limits_{name}_{ss.limits_v}",
                            disabled=[c_ for c_ in df.columns if c_ not in ("min", "max")],
                            column_order=["nutrient", "unit", "min", "max", "standard min", "standard max", "evidence",
                                          "source", "link"],
                            column_config={"min": st.column_config.NumberColumn(format="%.4g"),
                                           "max": st.column_config.NumberColumn(format="%.4g"),
                                           "standard min": st.column_config.NumberColumn(format="%.4g"),
                                           "standard max": st.column_config.NumberColumn(format="%.4g"),
                                           "link": st.column_config.LinkColumn(display_text="open")})
    new_rows = [{**r, "min": None if pd.isna(e["min"]) else float(e["min"]), "max": None if pd.isna(e["max"]) else float(e["max"])}
                for r, e in zip(rows_, edited.to_dict("records"))]
    if any(n["min"] != r["min"] or n["max"] != r["max"] for n, r in zip(new_rows, rows_)):
        errors = A.limit_errors(new_rows)
        if errors:
            st.error("Not saved. " + "; ".join(errors) + ".")
        else:
            A.set_limits(name, new_rows)
            ss.limits_v += 1
            st.rerun()
    own_limits = [r for r in rows_ if r["min"] != r["standard min"] or r["max"] != r["standard max"]]
    if own_limits:
        st.caption(f"{len(own_limits)} limit(s) changed: " + ", ".join(r["nutrient"] for r in own_limits))
        if st.button("Put all limits back to the standard values"):
            A.set_limits(name, [{**r, "min": r["standard min"], "max": r["standard max"]} for r in rows_])
            ss.limits_v += 1
            st.rerun()
    if F_["age"] >= 50:
        st.warning("The standard limits are for adults up to about 50-69. Some differ at older ages (Voedingscentrum 2025): "
                   "vitamin D 20 µg from 70, calcium 1200 mg from 70, vitamin B6 1.8 mg for men from 51, and for women iron "
                   "11 mg and calcium 1100 mg from 50. Set those here if they apply.")

# ---------------- Settings ----------------
with tabs[5]:
    st.markdown("#### Solution cache")
    st.caption(f"Every computed solution is kept in `{A.CACHE_DIR}` (outside git) and reused; the oldest-used "
               "entries go first when the cache is full.")
    a, b, c_ = st.columns(3)
    a.number_input("Cache limit (MB)", min_value=10, max_value=10000, step=50, key="cache_mb")
    tile(b, "In use", f"{A.cache_size_mb():.1f} MB", f"{len(A.cache_files())} entries")
    if c_.button("Empty the cache"):
        A.clear_all()
        st.rerun()
    st.markdown("#### Prices")
    snap = sorted((A.ROOT / "data").glob("checkjebon_*.json"))
    st.caption(f"Current snapshot: `{snap[-1].name if snap else 'none'}`. Fetching new prices downloads the latest "
               "Checkjebon snapshot and rebuilds the catalog (`fetch_prices.py`, `expand.py`, `catalog.py`, about "
               "2 minutes). New products can bring new matcher errors; odd foods in a basket are worth a check.")
    if st.button("Fetch new prices"):
        with st.status("Updating prices ...", expanded=True) as stt:
            try:
                n = A.refresh_prices(st.write)
                stt.update(label=f"Prices updated; {n} outdated cache entries removed.", state="complete")
            except Exception as e:
                stt.update(label="Price update failed", state="error")
                st.code(str(e))

st.divider()
st.caption(f"{NEVO_LINE} Prices: Checkjebon (MIT). Amino acids: USDA FoodData Central SR Legacy.")
