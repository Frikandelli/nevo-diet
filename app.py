"""nevo-diet app.  ./app.sh  (or: streamlit run app.py)

The entry point: settings in the sidebar, pages in views/ (one file per page, navigation at the top). The sidebar is
drawn on every page, so every page sees the same profile, chain and mode; ui.Ctx carries them to the page.
On the first run it asks for the NEVO dataset (setup_data.py), which doesn't come with the app.

Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources.
"""
import zipfile

import streamlit as st

import setup_data

NEVO_LINE = "Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources."
st.set_page_config(page_title="nevo-diet", page_icon="🥦", layout="wide", initial_sidebar_state="expanded")

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
import ui  # noqa: E402

# ---------------- settings (saved per computer in ~/.config/nevo-diet/settings.json) ----------------
ss = st.session_state
if ss.get("reset_all"):             # "Reset everything" in Settings: back to the defaults. Own profiles and limits stay.
    # new table widgets, or the browser keeps the old ticks
    _v, _o, _l = ss.get("editor_v", 0) + 1, ss.get("own_v", 0) + 1, ss.get("food_limits_v", 0) + 1
    ss.clear()
    A.save_settings(dict(A.DEFAULTS))
    ss.editor_v, ss.own_v, ss.food_limits_v = _v, _o, _l
# Streamlit drops a widget's state when its widget isn't drawn (another page, or a run that ends in st.rerun() first),
# so any missing key is refilled from the settings file, which is saved on every change.
_saved = A.load_settings()
for k, v in _saved.items():
    if k not in ss:
        ss[k] = v
ss.setdefault("editor_v", 0)
ss.setdefault("limits_v", 0)
ss.setdefault("own_v", 0)
ss.setdefault("food_limits_v", 0)
if "switch_profile" in ss:          # a saved or deleted profile: only now, before the widgets exist, can they be changed
    ss.profile = ss.pop("switch_profile")
    ss.weight = ss.height = ss.kcal = ss.protein = None
A.set_limit(ss.cache_mb)
theme = "dark" if (getattr(st.context, "theme", None) and st.context.theme.type == "dark") else "light"
profiles, chains = A.profiles(), A.chains()
if ss.profile not in profiles:
    ss.profile = A.DEFAULTS["profile"]
real = ss.mode == "realistic"

# ---------------- pages (defined first, so the sidebar can link to them) ----------------
pages = [
    st.Page("views/plan.py", title="Plan", icon=":material/restaurant:", default=True),
    st.Page("views/nutrients.py", title="Nutrients", icon=":material/nutrition:"),
    st.Page("views/why.py", title="Why this diet", icon=":material/insights:"),
    st.Page("views/foods.py", title="Foods", icon=":material/shopping_basket:"),
    st.Page("views/supplements.py", title="Supplements", icon=":material/medication:"),
    st.Page("views/dishes.py", title="Dishes", icon=":material/ramen_dining:"),
    st.Page("views/profile.py", title="Profile & limits", icon=":material/person:"),
    st.Page("views/data.py", title="Data & sources", icon=":material/database:"),
    st.Page("views/howto.py", title="How to use", icon=":material/help:"),
    st.Page("views/about.py", title="About", icon=":material/info:"),
    st.Page("views/settings.py", title="Settings", icon=":material/settings:"),
]
page = st.navigation(pages, position="top")

# ---------------- the sidebar: what to solve, top to bottom in order of importance ----------------
# Pure mode recomputes on every change; realistic mode on the Solve button. Every number has a tooltip, and the How to
# use page explains them all.
side = st.sidebar
side.markdown("### 🥦 nevo-diet")
side.caption("The cheapest diet that meets every Dutch nutrient norm, from real supermarket prices. Work down the "
             "sidebar; the result is on the **Plan** page.")
side.page_link("views/howto.py", label="How to use this app", icon=":material/help:")

side.markdown("**1 · Who eats**")
side.selectbox("Profile", list(profiles), format_func=profiles.get, key="profile", label_visibility="collapsed",
               help="Sex, age, body and activity of the person eating. They set every nutrient limit and the calorie and "
                    "protein estimates. Make your own on the Profile & limits page.")

_body = A.person_info(A.person(ss.profile, ss.weight, ss.height))
side.markdown("**2 · Calories and protein** · *the two numbers that matter most*")
c = side.columns(2)
c[0].number_input("Calories (kcal/day)", min_value=800.0, max_value=8000.0, step=50.0, value=None, key="kcal",
                  format="%.0f", placeholder=f"auto: {_body['kcal']:.0f}",
                  help="How much energy a day. The diet lands between this number and 4% above it. Blank: estimated from "
                       "the profile and the body below (resting energy x activity level). Type your own to eat more or "
                       "less, e.g. 2,200 to lose weight.")
c[1].number_input("Protein (g/day)", min_value=10.0, max_value=500.0, step=5.0, value=None, key="protein",
                  format="%.0f", placeholder=f"auto: {_body['protein']:.0f}",
                  help="The least protein a day; the diet may have more. Blank: the profile's grams per kg x your weight "
                       "(0.83 g/kg is the Dutch norm, the active profiles use 1.2). People who train often aim for "
                       "1.4-2.0 g/kg. More protein costs the most of any limit.")
side.caption("Blank = the estimate shown in grey. Type a number to aim for exactly that.")
with side.expander("Your body (for the estimates)"):
    c = st.columns(2)
    c[0].number_input("Weight (kg)", min_value=30.0, max_value=250.0, step=1.0, value=None, key="weight", format="%.1f",
                      placeholder=f"{_body['weight']:.1f}",
                      help="Only used for estimates: calories and protein when those boxes are blank, and the amino acid "
                           "needs (mg per kg). Blank: the profile's weight.")
    c[1].number_input("Height (cm)", min_value=120.0, max_value=230.0, step=1.0, value=None, key="height", format="%.1f",
                      placeholder=f"{_body['height']:.1f}" if _body["height"] else "not set",
                      help="Only used for the calorie estimate (Henry 2005, the equation behind the Dutch norms). "
                           "Blank: the profile's height.")
    st.caption("Change these to get the estimates for your own body. They don't matter once you type calories and "
               "protein above (weight still sets the amino acid needs).")

side.markdown("**3 · Where you shop**")
chain_opts = [A.CHEAPEST] + (chains if real else [A.ALL_CHAINS] + chains)
# Set it even when it's unchanged: without this the selectbox falls back to its first option when the list changes.
ss.chain = ss.chain if ss.chain in chain_opts else "ah"
side.selectbox("Chain", chain_opts, key="chain", format_func=ui.chain_name, label_visibility="collapsed",
               help="The supermarket whose prices are used. 'Cheapest chain' picks the one where your plan costs least. "
                    "'Every chain' (pure only) takes each food from the chain that sells it cheapest: no single shop.")
chain_note = side.empty()

side.markdown("**4 · Kind of plan**")
side.radio("Mode", ["pure", "realistic"], key="mode", horizontal=True, label_visibility="collapsed",
           help="Pure: the mathematical minimum, in grams a day of any food; it updates as you change things. Realistic: "
                "a week of real dinners with whole packs and a shopping list; press Solve after a change.")
side.caption("**Pure**: the mathematical minimum, any food in any amount. **Realistic**: a week of meals, whole packs "
             "and a shopping list (press **Solve**).")
solve_slot = side.empty()
if real:
    side.radio("Strictness of the meal rules", ["strict", "medium", "loose"], key="strictness", horizontal=True,
               help="The rules: at least 4 different dinners a week, none more than twice, 2 bread toppings, 250 g "
                    "vegetables and 200 g fruit a day. Strict: never bent. Medium: bent only if that saves at least "
                    "€0.25/day. Loose: at least €0.10/day. How much of a food you eat is up to your own limits (Plan "
                    "page); there are none by default.")
    side.radio("Meals", ["brunch", "classic"], key="pattern", horizontal=True,
               help="Brunch: brunch + warm dinner (cooked with leftovers for the next brunch) + snacks. Classic: "
                    "breakfast, lunch and dinner.")
    side.toggle("Batch cooking", key="batch",
                help="One weekend session (about an hour) for dried pulses and soup, frozen in portions. Off: every "
                     "dinner is cooked on the day.")

side.markdown("**5 · Fewer foods**")
side.number_input("Cost per food (€/day)", min_value=0.0, max_value=1.0, step=0.01, format="%.2f", key="food_cost",
                  help="A small charge for every food in the plan, so a food only comes in if it saves at least this "
                       "much. Without it the cheapest plan uses tiny amounts of many foods (1 g of kale a day), and every "
                       "one is another pack to buy. The charge isn't in the price shown. 0 = the textbook linear program; "
                       "0.10 = even fewer foods.")
side.caption("Recommended: **€0.05**. A few cents more on paper, but fewer products to buy, so usually cheaper in the "
             "shop. 0 gives the textbook answer.")

# Supplements: set on their own page; here only what the plan may use, in one line.
pills = A.pill_spec(ss.pill_mode, ss.pills_on, ss.pill_anywhere, ss.pill_prices, ss.pill_exact)
side.markdown("**6 · Supplements**")
side.page_link("views/supplements.py", label=A.S.describe(pills).capitalize(), icon=":material/medication:",
               help="Which vitamin and mineral pills the plan may use, and at what price. Change it on the Supplements "
                    "page. By default only the vitamin D tablet.")

with side.expander("Optional"):
    st.number_input("Whole fruit (g/day)", min_value=0.0, max_value=1000.0, step=50.0, key="fruit", format="%.0f",
                    help="A minimum of whole fruit: fresh, frozen, or tinned in juice or water; not juice, jam, sweetened "
                         "apple sauce, dried fruit, olives, lemon or lime. The cheapest diet has none, because other foods "
                         "give the same vitamins for less. The Dutch guidelines say at least 200 g. 0 = no minimum.")
    st.number_input("Budget (€/day)", min_value=0.5, max_value=20.0, step=0.25, key="budget",
                    help="Only a check: the Plan page says whether the plan fits, and the cost curves draw it as a line. "
                         "It doesn't change the plan.")
    if not real:
        st.toggle("Only foods sold at ≥ 3 chains", key="min3",
                  help="Leaves out foods that few chains sell, which are often matching errors or hard to find. The "
                       "realistic week always does this for foods eaten as such.")
person = A.person(ss.profile, ss.weight, ss.height, ss.kcal, ss.protein, ss.fruit)

settings = {k: ss[k] for k in A.DEFAULTS}
settings["excluded"] = sorted(ss.excluded)
settings["no_kinds"] = sorted(ss.no_kinds)
settings["cook_flip"] = sorted(ss.cook_flip)
if settings != _saved:
    A.save_settings(settings)

# ---------------- settings -> what to solve ----------------
own = A.own_spec(ss.my_foods)
# Your ✗ marks and every food of the kinds you left out ("pasta and noodles", "rice" ...): both are single foods out.
single = sorted(set(ss.excluded) | A.K.members(ss.no_kinds))
ex = tuple(A.effective_excluded(single, ss.no_categories, own))
flip = sorted(ss.cook_flip)    # the foods whose cook tick differs from the default (cooking.py)
limits = A.limit_spec(ss.food_limits)      # your own maximums on foods and kinds; none by default
pure_rank_kw = dict(profile=person, cooked=True, excluded=list(ex), min3=ss.min3, own=own, flip=flip, limits=limits,
                    food_cost=ss.food_cost, pills=pills)
week_kw = dict(profile=person, cooked=True, flip=flip, excluded=single, strictness=ss.strictness,
               pattern=ss.pattern, batch=ss.batch, no_cats=sorted(ss.no_categories), own=own, food_cost=ss.food_cost,
               limits=limits, pills=pills)
# "cheapest" resolves to a real chain here, from the current settings: everything below uses `chain`, never ss.chain.
# In realistic mode that takes a week at every chain, so until Solve the pure LP's pick stands in and no week is shown.
auto = ss.chain == A.CHEAPEST
week_ranked = not (auto and real) or A.week_prices.is_cached(**week_kw)
ranking, chain = None, ss.chain
if auto:
    ranking = A.week_prices(**week_kw) if real and week_ranked else A.chain_prices(**pure_rank_kw)
    chain = ranking["best"] or A.DEFAULTS["chain"]
    if not ranking["best"]:
        chain_note.caption("No chain has a plan with these settings.")
    elif not week_ranked:
        chain_note.caption(f"Press **Solve** to compare a week at every chain. Cheapest in the pure LP: **{ui.chain_name(chain)}**.")
    else:
        chain_note.caption(f"→ **{ui.chain_name(chain)}**, €{ranking['rows'][0]['cost']:.2f} a day")
ctx = ui.Ctx(ss, theme, person, chain, ranking, week_ranked, own, ex, flip, pure_rank_kw, week_kw, single)
ss["_ctx"] = ctx

if real:
    with solve_slot.container():
        known = ctx.solved
        if st.button("Solve" if not known else "Solved ✓ (cached)", type="primary", disabled=known, width="stretch",
                     help="Solves a week of meals (10 to 20 s; with 'cheapest chain' a week at every chain, about 2 min). "
                          "Every week is cached, so settings you solved before show at once."):
            if not week_ranked:         # each week is cached on its own, so an interrupted run picks up where it stopped
                bar = st.progress(0.0)
                for i, ch in enumerate(chains):
                    bar.progress(i / len(chains), f"Solving a week at {ui.chain_name(ch)} ({i + 1} of {len(chains)}) ...")
                    A.realistic(chain=ch, **week_kw)
                chain = A.week_prices(**week_kw)["best"] or A.DEFAULTS["chain"]
                bar.empty()
            with st.spinner("Solving a week of meals (10 to 20 s, twice with a before-and-after) ..."):
                A.realistic(**{**ctx.real_kw, "chain": chain})
                if ctx.compare_with:
                    A.realistic(**{**ctx.base_real_kw, "chain": chain})
            st.rerun()
if ex:
    side.caption(f"{len(ex)} food(s) left out: your ✗ marks, kinds and category ticks (Plan and Foods pages).",
                 help=", ".join(A.label(k) for k in ex))

page.run()

st.divider()
st.caption(f"{ui.NEVO_LINE} Prices: Checkjebon (MIT), snapshot {ui.snapshot_date()}. Amino acids: USDA FoodData Central "
           "SR Legacy. Cooking losses: USDA retention factors. Not medical advice.")
