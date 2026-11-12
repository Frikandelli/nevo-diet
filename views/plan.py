"""Plan: the result. The price, your own foods, the basket (pure) or the week of meals (realistic), what your foods and
ticks changed, and the nutrient check. Downloads: every table as CSV, the whole plan as a ZIP."""
import pandas as pd
import streamlit as st

import appcore as A
import ui

c = ui.ctx()
ss, chain, real, own = c.ss, c.chain, c.real, c.own
pure = c.pure

st.title("Plan")
st.caption(c.describe())


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
        away = [A.label(k) for k in c.own_keys if not any(r["chain"] == chain for r in A.prices_of(k))]
        if away and chain != A.ALL_CHAINS:
            st.caption(f"⚠ Not sold at {ui.chain_name(chain)}, so priced at the cheapest other chain: " + ", ".join(sorted(away)) + ".")


def limits_box():
    """At most so much of a food, or of a whole kind of food, a day or a week. There are none until you add one."""
    with st.container(border=True):
        st.markdown("**Limits** · at most so much of a food, or of a whole kind (all pasta, all cheese ...). There are "
                    "none until you add one. Double-click a cell to change it.")
        choices = A.limit_choices()
        pick = st.selectbox("Add a limit", list(choices), format_func=choices.get, index=None,
                            key=f"limit_pick_{ss.food_limits_v}", label_visibility="collapsed",
                            placeholder="Add a limit: type to search a food or a kind, e.g. pasta")
        if pick:
            if pick not in [f["key"] for f in ss.food_limits]:
                ss.food_limits = [*ss.food_limits, {"key": pick, "grams": 100.0, "per": "day"}]
            ss.food_limits_v += 1
            st.rerun()
        if not ss.food_limits:
            return
        shown = pd.DataFrame([{"✗": False, "food or kind": A.limit_target(f["key"]), "at most": f["grams"], "per": f["per"],
                               "key": f["key"]} for f in ss.food_limits])
        edited = st.data_editor(
            shown, hide_index=True, width="stretch", key=f"limits_{ss.food_limits_v}", disabled=["food or kind"],
            column_config={
                "✗": st.column_config.CheckboxColumn("✗", help="remove this limit", width="small"),
                "at most": st.column_config.NumberColumn(
                    "at most (g)", min_value=0, max_value=50000, step=10, format="%.0f",
                    help="Grams as bought (dry pasta, raw meat), of everything in the limit together. 0 = none at all."),
                "per": st.column_config.SelectboxColumn("per", options=["day", "week"], required=True),
                "key": None})
        new = [{"key": r["key"], "grams": old["grams"] if pd.isna(r["at most"]) else float(r["at most"]), "per": r["per"]}
               for r, old in zip(edited.to_dict("records"), ss.food_limits) if not r["✗"]]
        if new != ss.food_limits:
            ss.food_limits = new
            ss.food_limits_v += 1
            st.rerun()
        st.caption("A limit counts all of that food or kind you eat: on its own and, in the realistic week, in dinners. "
                   "A food at its limit says so in the plan, and your limits are in the nutrient check; *Why this diet* "
                   "shows what each one costs. Too tight a limit gives no plan, with a message saying which one.")


def impossible(why, intro):
    """No plan: say what's in the way, and how much of each of your own foods would still work."""
    if why.get("empty"):
        st.info("**Every food is excluded.** Put back the foods you want on the Foods page, and the plan is made from those.")
        return
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
    if not c.compare_with or before is None or not before["ok"]:
        return {}
    d = now["cost"] - before["cost"]
    return {"delta": f"{'+' if d >= 0 else '-'}€{abs(d):.2f}", "help": f"Compared with the plan {c.compare_with}."}


def compare_block(now, before, dinners=False):
    """The before-and-after, folded away under the plan: the tile on top already has the price change. The label stays
    the same whatever is compared, because an expander closes itself when its label changes."""
    if not c.compare_with:
        return
    with st.expander("What changed in the rest of the plan"):
        if own and ss.no_categories:
            st.toggle("Also compare without the category ticks", key="compare_ticks",
                      help="Off: what your own foods change. On: what your own foods and the ticks change together.")
        if before is None:
            st.info(f"Press **Solve** in the sidebar to compare with the plan {c.compare_with}.")
        elif not before["ok"]:
            st.info(f"There is no adequate plan {c.compare_with}, so there is nothing to compare with.")
        else:
            d = now["cost"] - before["cost"]
            st.markdown(f"Compared with the plan {c.compare_with}: €{before['cost']:.2f} → €{now['cost']:.2f} a day "
                        f"({'+' if d >= 0 else '−'}€{abs(d):.2f}). ★ = your food.")
            rows_ = A.compare(now, before, own)
            ui.table(rows_, "plan_changes", fmt={"before": "{:,.0f}", "now": "{:,.0f}", "change": "{:+,.0f}",
                                                 "€/day change": "{:+.3f}"},
                     column_config={"before": "before (g/day)", "now": "now (g/day)", "change": "change (g/day)"})
            if dinners:
                changed = A.compare_dinners(now, before)
                if changed:
                    ui.table(changed, "plan_dinner_changes")


def ranking_block():
    """With "cheapest": what the other chains would have cost. The label stays the same, see compare_block."""
    if not c.ranking:
        return
    with st.expander("Every chain compared"):
        rows_ = [{"chain": ui.chain_name(r["chain"]), **{k: v for k, v in r.items() if k != "chain"}} for r in c.ranking["rows"]]
        ui.table(pd.DataFrame(rows_).rename(columns={"cost": "€/day", "bent": "rules bent"}), "chains_ranked",
                 fmt={"€/day": "€{:.2f}"})
        st.caption("Empty: no plan at that chain with these settings. The chain is picked on price alone"
                   + (", so a cheaper week may bend more meal rules." if real else "."))


def price_tiles(result, base, fourth):
    t = st.columns(4)
    ui.tile(t[0], "€ per day", f"€{result['cost']:.2f}",
            f"your foods €{result['own_eur']:.2f}, the rest €{result['cost'] - result['own_eur']:.2f}" if own else "",
            **change_note(result, base))
    ui.tile(t[1], "€ per week", f"€{7 * result['cost']:.2f}", f"€{30 * result['cost']:.0f} a month")
    over = result["cost"] - ss.budget
    ui.tile(t[2], "Budget", "within budget" if over <= 0 else f"€{over:.2f} over", f"budget €{ss.budget:.2f}/day")
    ui.tile(t[3], *fourth)
    if result.get("free_pills"):
        n = len(result["free_pills"])
        st.warning(f"⚠ **This price assumes {n} free supplement{'s' if n > 1 else ''}**: "
                   f"{', '.join(result['free_pills'])} {'have' if n > 1 else 'has'} no price here, so "
                   f"{'they count' if n > 1 else 'it counts'} as €0. Type a price on the **Supplements** page.")


def downloads(rows_, name):
    b = st.columns([1, 1, 4])
    with b[0]:
        ui.download_csv(rows_, name, "This table (CSV)")
    b[1].download_button("The whole plan (ZIP)", data=ui.plan_zip(c), file_name="nevo-diet-plan.zip",
                         mime="application/zip", key="dl_plan_zip", on_click="ignore", icon=":material/folder_zip:",
                         type="tertiary", help="Every table of the Plan and Nutrients pages as CSV, the settings, and a "
                                               "README with the sources.")


def nutrient_check(result, binding=()):
    st.subheader("Nutrients", anchor="nutrients")
    ui.nutrient_summary(result["reqs"], binding)
    with st.expander(f"Every nutrient ({len(result['reqs'])} limits)"):
        ui.nutrient_table(result["reqs"], "nutrients", binding)
    st.page_link("views/nutrients.py", label="Charts: coverage, maximums, which food gives what", icon=":material/nutrition:")


# ---------------- warnings first: they apply to whatever is shown ----------------
allergy_ticks = [A.CAT.LABEL[k] for k in ss.no_categories if k in A.CAT.ALLERGY_KEYS]
if allergy_ticks:
    st.warning(f"**Leaving out: {', '.join(allergy_ticks)}.** This is worked out from names and typical recipes, and isn't a "
               "guarantee: read the label of everything you buy, because real products differ and can carry traces.")
conflicts = A.own_conflicts(own, ss.no_categories)
if conflicts:
    st.error("**In My foods, and may go against your allergy ticks:** " +
             "; ".join(f"{A.label(k)} ({why})" for k, why in conflicts.items()) + ". They stay in because you asked for them.")
raw_must = A.raw_but_must(c.flip)
if raw_must:
    st.error("**Counted raw, but meant to be cooked:** " + ", ".join(A.label(k) for k in raw_must) + ". Raw meat, fish, "
             "eggs, frozen vegetables, dried pulses and flour can make you ill, and some are inedible raw. The plan "
             "uses their raw nutrients because you unticked *cook*; tick it again on the Foods page or in the plan table.")

my_foods_box()
limits_box()
ui.left_out_box("plan")

if not real:
    if not pure["ok"]:
        impossible(pure["why"], "**No adequate diet with these settings.** Change your own foods or limits, put back "
                                "excluded foods or categories, or change the calories or protein target.")
    else:
        price_tiles(pure, c.pure_base, ("Foods in the basket", str(len(pure["basket"])), f"of {pure['n_foods']} available"))
        st.caption("**Pure** is the bare linear program: the cheapest grams per day that meet every limit, from any food "
                   "and in any amount (until you set limits), so flour may be eaten as such (counted as baked). Switch "
                   "*Mode* to *realistic* in "
                   "the sidebar for meals, whole packs and a shopping list."
                   + (f" The cost of €{ss.food_cost:.2f} per food isn't in the price: it takes the basket from "
                      f"{pure['bare']['n']} foods to {len(pure['basket'])}, and adds "
                      f"€{pure['cost'] - pure['bare']['cost']:.3f} a day to what the food costs." if ss.food_cost else ""))
        ranking_block()
        st.subheader("Basket", anchor="basket")
        rows_ = []
        for b in pure["basket"]:
            notes = [n for n, on in [("your food", b["mine"]), (f"not sold at {ui.chain_name(chain)}", b["away"]),
                                     ("⚠ meant to be cooked", b["raw_warn"]), ("sold at < 3 chains", (b["n_chains"] or 3) < 3),
                                     ("at your limit", b["at_limit"])] if on]
            rows_.append({"key": b["key"], "cook": b["cook"], "food": b["food"] + (" ★" if b["mine"] else ""),
                          "kind": A.K.KIND.get(b["key"], ""),
                          "g/day": b["g_day"] if b["g_day"] else None, "amount": b["amount"], "€/day": b["eur_day"],
                          "€/week": 7 * b["eur_day"], "product": b["product"],
                          "chain": ui.chain_name(b["chain"]) + (" ⚠" if b["away"] else ""),
                          "sold at": f"{b['n_chains']} chains" if b["n_chains"] else "", "note": ", ".join(notes)})
        cols = ["food", "kind", "amount", "€/day", "€/week", "product", "chain", "sold at"] + (["note"] if any(r["note"] for r in rows_) else [])
        st.caption("Tick **✗** to leave a food out, **✗ kind** to leave out its whole kind (all pasta, all rice ...), "
                   "*cook* to count it cooked or raw; then press **Apply**. Put things back with *Leave out or put back* above.")
        ui.tick_table(rows_, cols, {"€/day": st.column_config.NumberColumn(format="€%.3f"),
                                    "€/week": st.column_config.NumberColumn(format="€%.2f"),
                                    "sold at": st.column_config.TextColumn(help="How many of the 10 chains sell this food.")},
                      "pure")
        downloads([{k: v for k, v in r.items() if k not in ("key",)} for r in rows_], "basket")
        compare_block(pure, c.pure_base)
        nutrient_check(pure, pure["binding"])
elif c.R is None:
    st.info(("Realistic mode solves a week of meals (10 to 20 s per setting). " if c.week_ranked else
             f"The cheapest chain takes a week of meals at all {len(A.chains())} chains (about 2 minutes). ") +
            "Press **Solve** in the sidebar. Results are cached, so settings you solved before show at once.")
elif not c.R["ok"]:
    impossible(c.R["why"], "**No feasible week with these settings.** Change your own foods or limits, take off a "
                           "category tick, or try a looser strictness.")
else:
    R = c.R
    price_tiles(R, c.R_base, ("vs pure LP", f"+€{R['cost'] - pure['cost']:.2f}" if pure["ok"] else "-",
                              "the price of meals, packs and rules"))
    ranking_block()
    if R["bent"]:
        st.warning("Rules bent: " + "; ".join(
            f"**{b['rule']}** (keeping it costs €{b['saving_day']:.2f}/day more)" if b["saving_day"] is not None
            else f"**{b['rule']}** (keeping it is infeasible)" for b in R["bent"]))
    else:
        st.success("All meal rules kept.")
    st.subheader("Dinners", anchor="dinners")
    st.caption(f"{R['n_dishes']} NEVO dishes are priceable at {ui.chain_name(chain)}; these are the week's.")
    ui.table(pd.DataFrame(R["dinners"]).rename(columns={"g_per_evening": "g per evening", "hands_on_min": "hands-on min",
                                                        "eur_portion": "€/portion", "nevo_dish": "NEVO dish"}),
             "dinners", fmt={"g per evening": "{:,.0f}", "€/portion": "€{:.2f}"})
    a, b = st.columns([1.2, 1.5])
    with a:
        st.subheader("Eaten as such", anchor="eaten-as-such")
        st.caption("Brunch, sides and snacks. ✗, ✗ kind and cook work as in the pure plan; after Apply, press **Solve** again.")
        direct = [{**d, "kind": A.K.KIND.get(d["key"], ""),
                   "note": ", ".join(n for n, on in [("⚠ meant to be cooked", d["raw_warn"]),
                                                     ("at your limit", d.get("at_limit"))] if on)}
                  for d in R["direct"]]
        ui.tick_table(direct, ["food", "kind", "amount"] + (["note"] if any(d["note"] for d in direct) else []), {}, "week")
    with b:
        st.subheader("Shopping list", anchor="shopping-list")
        st.caption(f"At {ui.chain_name(chain)}, every week; pantry items last several weeks.")
        shop = pd.DataFrame(R["shop"]).rename(columns={"eur_week": "€/week"})
        ui.table(shop, "shopping_list", fmt={"€/week": "€{:.2f}"}, download=False)
    downloads(R["shop"], "shopping_list")
    compare_block(R, c.R_base, dinners=True)
    nutrient_check(R)
ui.sources("nevo", "prices", "limits", "cooking")
