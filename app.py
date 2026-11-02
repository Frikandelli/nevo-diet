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
chain_opts = chains if ss.mode == "realistic" else [A.ALL_CHAINS] + chains
if ss.chain not in chain_opts:
    ss.chain = "ah"
c[1].selectbox("Chain", chain_opts, key="chain",
               format_func=lambda x: "all chains (cheapest per food)" if x == A.ALL_CHAINS else x)
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

ex = tuple(sorted(ss.excluded))
pure_kw = dict(profile=person, chain=ss.chain, cooked=ss.cooked, excluded=list(ex), min3=ss.min3)
real_kw = dict(profile=person, chain=ss.chain, cooked=ss.cooked, excluded=list(ex), strictness=ss.strictness,
               pattern=ss.pattern, batch=ss.batch)

with c[4]:
    if real:
        known = A.realistic.is_cached(**real_kw)
        if st.button("Solve" if not known else "Solved ✓ (cached)", type="primary", disabled=known,
                     width="stretch"):
            with st.spinner("Solving a week of meals (about 10 s) ..."):
                A.realistic(**real_kw)
            st.rerun()
    if ex:
        st.caption(f"{len(ex)} food(s) excluded: " + ", ".join(A.label(k) for k in ex[:6]) + (" …" if len(ex) > 6 else ""))

pure = A.pure(**pure_kw)
R = A.realistic(**real_kw) if real and A.realistic.is_cached(**real_kw) else None


def tile(col, label, value, sub=""):
    col.metric(label, value)
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


tabs = st.tabs(["Plan", "Foods", "Dishes", "Charts", "Profile & limits", "Settings"])

# ---------------- Plan ----------------
with tabs[0]:
    if not real:
        if not pure["ok"]:
            st.error(f"No adequate diet with these settings: {pure['message']}. Put back excluded foods, or change the calories or protein target.")
        else:
            t = st.columns(4)
            tile(t[0], "€ per day", f"€{pure['cost']:.2f}")
            tile(t[1], "€ per week", f"€{7 * pure['cost']:.2f}")
            over = pure["cost"] - ss.budget
            tile(t[2], "Budget", "within budget" if over <= 0 else f"€{over:.2f} over",
                 f"budget €{ss.budget:.2f}/day")
            tile(t[3], "Foods in the basket", str(len(pure["basket"])), f"of {pure['n_foods']} available")
            st.caption("**Pure** is the bare linear program: the cheapest grams per day that meet every requirement. "
                       "It may use raw flour, odd amounts and foods from different chains. Switch to *realistic* "
                       "for meals, whole packs and a shopping list.")
            df = pd.DataFrame(pure["basket"])
            df["chains"] = [f"{n}{' ⚠' if n < 3 else ''}" for n in df.n_chains]
            df["cap"] = ["at cap" if c_ else "" for c_ in df.at_cap]
            show_table(df[["food", "amount", "eur_day", "product", "chain", "chains", "cap"]].rename(
                columns={"eur_day": "€/day"}), height=35 * len(df) + 38, column_config={"€/day": st.column_config.NumberColumn(format="%.3f")})
            st.markdown("**Nutrients** (✓ met, binding = the requirement that sets the price)")
            nutrient_table(pure["reqs"], pure["binding"])
    elif R is None:
        st.info("Realistic mode solves a week of meals (about 10 s per setting). Press **Solve** above. "
                "Results are cached, so settings you solved before show at once.")
    elif not R["ok"]:
        st.error(R["message"])
    else:
        t = st.columns(4)
        tile(t[0], "€ per day", f"€{R['cost']:.2f}")
        tile(t[1], "€ per week", f"€{7 * R['cost']:.2f}")
        over = R["cost"] - ss.budget
        tile(t[2], "Budget", "within budget" if over <= 0 else f"€{over:.2f} over", f"budget €{ss.budget:.2f}/day")
        tile(t[3], "vs pure LP", f"+€{R['cost'] - pure['cost']:.2f}" if pure["ok"] else "-",
             "price of meals, packs and rules")
        if R["bent"]:
            st.warning("Rules bent: " + "; ".join(
                f"**{b['rule']}** (keeping it costs €{b['saving_day']:.2f}/day more)" if b["saving_day"] is not None
                else f"**{b['rule']}** (keeping it is infeasible)" for b in R["bent"]))
        else:
            st.success("All meal rules kept.")
        st.markdown(f"**Dinners** ({R['n_dishes']} NEVO dishes priceable at {ss.chain})")
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
        st.markdown("**Nutrients per day**")
        nutrient_table(R["reqs"])

# ---------------- Foods ----------------
with tabs[1]:
    F = A.foods_table(profile=person, chain=ss.chain, cooked=ss.cooked, min3=ss.min3)
    df = pd.DataFrame(F["rows"])
    df.insert(0, "✗", df.key.isin(ex))
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
    cols = ["✗", "food", "group", "chains", "€/100 g", "g/day in plan", "reduced cost", "product", "pack"] + \
           list(ss.food_columns)
    st.caption("Tick ✗ to exclude a food; the plan re-solves at once. Reduced cost: how much the price per 100 g "
               "must drop before the LP would use the food (0 = in the basket). ⚠ = sold at fewer than 3 chains.")
    cfg = {"✗": st.column_config.CheckboxColumn("✗", help="exclude this food", width="small"),
           "€/100 g": st.column_config.NumberColumn(format="%.3f"),
           "g/day in plan": st.column_config.NumberColumn(format="%.0f"),
           "reduced cost": st.column_config.NumberColumn(format="%.3f")}
    for n in ss.food_columns:
        cfg[n] = st.column_config.NumberColumn(f"{n} ({F['units'][n]})", format="%.4g")
    edited = st.data_editor(view[cols + ["key"]], hide_index=True, width="stretch", height=620,
                            column_config={**cfg, "key": None},
                            disabled=[c_ for c_ in cols if c_ != "✗"], key=f"foods_{ss.editor_v}")
    now = (set(ex) - set(view.key)) | set(edited.loc[edited["✗"], "key"])
    if now != set(ex):
        ss.excluded = sorted(now)
        ss.editor_v += 1
        st.rerun()
    if ex and st.button("Put back all excluded foods"):
        ss.excluded = []
        ss.editor_v += 1
        st.rerun()

# ---------------- Dishes ----------------
with tabs[2]:
    if ss.chain == A.ALL_CHAINS:
        st.info("Pick a chain: a dish is priced from the ingredients sold at one chain.")
    else:
        Dt = A.dishes_table(chain=ss.chain)
        dd = pd.DataFrame(Dt["rows"])
        st.caption(f"{len(dd)} of NEVO's {Dt['n_total']} dishes and soups can be priced at {ss.chain} from their "
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
        ch3, agg = C.price_split(pure["shares"], theme)
        chart_block(ch3, agg.drop(columns=["order"]), "price_split",
                    "LP duality: at the optimum a basket food's price equals Σ shadow price × nutrient content over "
                    "the binding requirements, so each bar is the food's price split by what it pays for.")

        st.markdown("#### 4. Chains per profile (pure LP)")
        if person != ss.profile:
            st.caption("The standard profiles, without your weight, height and targets.")
        CT = A.chain_table(cooked=ss.cooked, excluded=list(ex), min3=ss.min3)
        chart_block(C.chains(CT["rows"], ss.chain, theme), CT["rows"], "chains")

        st.markdown("#### 5. What replaces what (pure LP)")
        RM = A.removal(**pure_kw)
        ch5, df5 = C.removal(RM["nodes"], theme)
        bad = [" / ".join(n_["path"]) for n_ in RM["nodes"] if n_["infeasible"]]
        chart_block(ch5, df5.drop(columns=["node"]), "removal",
                    "Remove the biggest food, re-solve, then do the same in the new diet: three levels, three "
                    "branches each. Hover a dot to see what replaced the removed food."
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
