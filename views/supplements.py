"""Supplements: every vitamin and mineral pill (and fish oil, algae oil, psyllium) the plan can use, with its price, what
the model counts of its label, and what it would save. Which ones the plan may use is set here: only the vitamin D tablet
by default. The choices sit in one form, so nothing reruns until Apply."""
import pandas as pd
import streamlit as st

import appcore as A
import ui

S = A.S
c = ui.ctx()
ss, chain, src = c.ss, c.chain, c.src
spec = c.pills
v = ss.editor_v

st.title("Supplements")
st.caption(c.describe())
st.markdown(
    "Pills the plan can use next to food: single vitamins and minerals, multivitamins, fish and algae oil, psyllium. "
    "Each is counted the way the nutrient norms count it, not just as the label says: folic acid counts 1.7 times as "
    "folate, synthetic vitamin E two thirds, and a big B12 tablet only for the little the gut takes up (a 1000 µg tablet "
    "counts as 22 µg). The details are under **How a label is counted** below.")

MODES = {"ticked": "only the ticked ones", "priced": "every supplement with a price",
         "all": "every supplement (no price counts as free ⚠)"}

# ---------------- what the plan may use, and the prices ----------------
savings = None
if src.get("ok", True):
    with st.spinner("Working out what each supplement would save (a few seconds the first time) ..."):
        savings = A.pill_savings(**c.lp_kw)["saves"]
rows_ = A.supplement_rows(spec, chain, src.get("units") if src.get("ok", True) else None, savings)
df = pd.DataFrame(rows_)
exact = {e["key"]: e for e in ss.pill_exact}
df["use"] = df.key.isin(ss.pills_on)
df["exactly"] = [exact[k]["n"] if k in exact else None for k in df.key]
df["per"] = [exact[k].get("per", "day") if k in exact else "day" for k in df.key]
df["€ per unit"] = [0.0 if p is None else p for p in df["€/unit"]]
df["price from"] = ["your price" if y else "⚠ no price: free" if f else f"{s}: {p}" for y, f, s, p in
                    zip(df.yours, df.free, df["shop"], df["product"])]
df["in plan"] = ["" if not a else "yes" if w > 1e-6 else "may use" for a, w in zip(df.allowed, df.per_week)]
df["per week"] = df.per_week.where(df.per_week > 1e-6)

with st.form("pills_form", border=False):
    mode = st.radio("The plan may use", list(MODES), index=list(MODES).index(spec["mode"]), format_func=MODES.get,
                    horizontal=True, key=f"pill_mode_w_{v}",
                    help="Only the ticked ones: the 'use' column (the vitamin D tablet by default). Every supplement with "
                         "a price: all of them except those without a price. Every supplement: those without a price "
                         "too, as if they were free; the price then says so with a ⚠. A supplement with an exact amount "
                         "is always in.")
    anywhere = st.toggle("Buy supplements at any shop", value=spec["anywhere"], key=f"pill_anywhere_w_{v}",
                         help="On: each supplement at the cheapest shop that sells it, drugstores too (you buy pills a few "
                              "times a year, and they keep). Off: only what your chain sells "
                              f"({ui.chain_name(chain)}); the rest has no price there.")
    st.caption("Tick **use** for the supplements the plan may take, or give one an **exact** amount (e.g. 1 a week). "
               "**€ per unit** is the cheapest price found; type your own to replace it, or a price where it says 0. "
               "Then press **Apply**.")
    cols = ["use", "exactly", "per", "€ per unit", "price from", "supplement", "contents", "unit", "in plan", "per week",
            "saves", "pack", "type", "note"]
    cfg = {
        "use": st.column_config.CheckboxColumn("use", width="small",
                                               help="The plan may use this one (with 'only the ticked ones')."),
        "exactly": st.column_config.NumberColumn("exactly", min_value=0.0, max_value=20.0, step=0.5, format="%g",
                                                 help="Take exactly this many, whatever the plan would choose. Empty: the "
                                                      "plan decides."),
        "per": st.column_config.SelectboxColumn("per", options=["day", "week"], width="small"),
        "€ per unit": st.column_config.NumberColumn("€ per unit", min_value=0.0, max_value=50.0, step=0.001,
                                                    format="€%.4f",
                                                    help="Price of one tablet, capsule or spoon: pack price ÷ units. Type "
                                                         "your own to use it instead; 0 with ⚠ means no price was found."),
        "price from": st.column_config.TextColumn("price from", width="medium"),
        "contents": st.column_config.TextColumn("on the label (per unit)", width="large"),
        "per week": st.column_config.NumberColumn("per week", format="%.1f",
                                                  help=f"Units a week in the plan ({c.src_tag})."),
        "saves": st.column_config.NumberColumn(
            "saves €/day", format="€%.3f",
            help="What this supplement is worth to the plan (the pure LP, no cost per food): for one the plan may not "
                 "use yet, what ticking it alone would save; for one it may use, what it saves now. At its price "
                 "(no price: as if free). Empty: an exact amount, which you set."),
        "pack": st.column_config.TextColumn("pack", help="The cheapest product: units per pack and its price."),
    }
    edited = st.data_editor(df[cols + ["key"]], hide_index=True, width="stretch", height=35 * len(df) + 38,
                            column_config={**cfg, "key": None},
                            disabled=[x for x in cols if x not in ("use", "exactly", "per", "€ per unit")],
                            key=f"pills_editor_{v}")
    applied = ui.apply_button(key="pills_apply")
if applied:
    shown = dict(zip(df.key, df["€ per unit"]))
    prices = dict(ss.pill_prices)
    for k, p in zip(edited.key, edited["€ per unit"]):
        if p is None or pd.isna(p):
            prices.pop(k, None)
        elif abs(float(p) - shown[k]) > 1e-9:            # changed: your price from now on
            prices[k] = float(p)
    ss.pill_mode, ss.pill_anywhere = mode, bool(anywhere)
    ss.pills_on = sorted(edited.loc[edited["use"].eq(True), "key"])
    ss.pill_prices = prices
    ss.pill_exact = [{"key": k, "n": float(n), "per": p or "day"} for k, n, p in
                     zip(edited.key, edited.exactly, edited.per) if n is not None and not pd.isna(n) and n > 0]
    ss.editor_v += 1
    st.rerun()

b = st.columns([1.3, 1.3, 1.3, 2.1])
if b[0].button("Back to vitamin D only", width="stretch",
               help="The default: only the vitamin D tablet, at any shop. Your typed prices stay."):
    ss.pill_mode, ss.pills_on, ss.pill_anywhere, ss.pill_exact = "ticked", list(S.DEFAULT_ON), True, []
    ss.editor_v += 1
    st.rerun()
if b[1].button("Forget my prices", width="stretch", disabled=not ss.pill_prices,
               help=f"Remove the {len(ss.pill_prices)} price(s) you typed."):
    ss.pill_prices = {}
    ss.editor_v += 1
    st.rerun()
with b[2]:
    ui.download_csv(df.drop(columns=["key", "€/unit", "yours", "free", "allowed", "ticked", "per_week", "eur_day",
                                     "product", "shop"]), "supplements", "This table (CSV)")

used = [r for r in rows_ if r["allowed"] and r["free"]]
if used:
    st.warning(f"⚠ **{len(used)} supplement(s) the plan may use have no price** and count as free: "
               + ", ".join(r["supplement"] for r in used) + ". Type a price in **€ per unit**, or the plan's price is "
               "too low by whatever it takes of them.")
if src.get("ok", True) and src.get("units"):
    st.markdown("**In the plan now** (" + c.src_tag + "): " + "; ".join(
        f"{S.name(k)}: {7 * n:.1f} a week" for k, n in sorted(src["units"].items(), key=lambda t: -t[1])) + ".")
elif src.get("ok", True):
    st.markdown("**In the plan now:** no supplements.")

# ---------------- how a label is counted ----------------
ui.heading("How a label is counted", "how-counted")
st.markdown(
    "The nutrient norms assume the nutrient comes from ordinary food. A pill's form or dose can make it count for more or "
    "less, so each label amount is converted first (model rules; sources on the **Data & sources** page):\n\n"
    "- **Folic acid** (and methylfolate) is absorbed better than folate in food: **×1.7** as folate (dietary folate "
    "equivalents, EFSA). It also counts against the folic acid maximum of 1000 µg.\n"
    "- **Vitamin E**: natural (d-alpha) ×1; synthetic (dl-alpha) **×0.67**, because the label counts it at 74% of "
    "natural and the norms at 50% (IOM 2000, EFSA 2015).\n"
    "- **Vitamin B12**: the gut takes up at most about 1.2 µg per dose through intrinsic factor, plus about 1% of the "
    "rest by diffusion. A dose counts as the food B12 that would be absorbed as much (food B12 is about 50% absorbed): "
    f"25 µg counts as {S.b12_counted(25):.1f} µg, 100 µg as {S.b12_counted(100):.1f}, 1000 µg as "
    f"{S.b12_counted(1000):.1f}.\n"
    "- **Iron** counts as non-haem iron, 10% absorbed, like iron from plants.\n"
    "- **Magnesium** from pills has its own maximum of 250 mg a day (EFSA's upper limit is for supplements only).\n"
    "- **Everything else** counts as on the label: no Dutch or EFSA norm gives a factor for pills. Magnesium oxide is "
    "said to be absorbed worse than citrate, but there is no agreed number.\n\n"
    "Supplements have no cap of their own: the nutrient maximums (vitamin D 100 µg, zinc 25 mg, retinol 3000 µg ...) "
    "bound them, as for food. The realistic week takes them in whole units a week.")
counted = [{"supplement": S.name(k), **r} for k in S.SUPP for r in S.counted(k)[1]]
ui.table(pd.DataFrame(counted), "supplements_counted",
         fmt={"label": "{:g}", "factor": "{:.3g}", "counted": "{:.4g}"},
         column_config={"why": st.column_config.TextColumn(width="large")})

# ---------------- every product ----------------
ui.heading("Every product and price", "products")
P = pd.DataFrame(S.products())
P.insert(0, "supplement", [S.name(k) for k in P.key])
P["shop"] = [S.shop_name(s) for s in P["shop"]]
P = P.rename(columns={"units": "units per pack", "price": "pack €", "per_unit": "€ per unit"})
ui.table(P[["supplement", "shop", "product", "units per pack", "pack €", "€ per unit", "source", "date", "link"]],
         "supplement_products", fmt={"pack €": "€{:.2f}", "€ per unit": "€{:.4f}"},
         column_config={"link": st.column_config.TextColumn(width="small")})
st.caption("Supermarket prices come from the Checkjebon snapshot and are refreshed with the food prices (Settings). "
           "Drugstore prices (De Online Drogist, Vitaminstore) were copied from the shop's website on the date shown and "
           "don't refresh. Albert Heijn's own labels (Care multivitamins) couldn't be read, so those aren't in the list; "
           "Lidl's pills have no pack size in the price data.")
ui.sources("supplements", "limits", "model")
