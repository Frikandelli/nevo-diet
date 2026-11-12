"""What every page of the app shares: the settings context, tables and charts with their downloads, the sources line.

Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources.

app.py builds a `Ctx` from the sidebar on every run and keeps it in st.session_state["_ctx"]; a page (views/*.py) gets
it with `ui.ctx()`. The solutions themselves are computed only when a page asks for them (Ctx.pure, Ctx.R ...), so the
About or Data page never waits for a solver.
"""
import io
import json
import zipfile
from datetime import date
from functools import cached_property

import pandas as pd
import streamlit as st

import appcore as A
import charts as C

NEVO_LINE = "Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources."

# Where each requirement belongs, for the nutrient tables (data/requirements.tsv `name`; anything else: "other").
NUTRIENT_GROUPS = [
    ("energy and macronutrients", ["energy", "protein", "carbs", "fat", "satfat", "trans", "free_sugars", "fibre"]),
    ("fatty acids", ["linoleic", "ala", "epa_dha"]),
    ("minerals", ["sodium", "potassium", "calcium", "phosphorus", "magnesium", "magnesium_pills", "iron_abs", "iron", "zinc",
                  "copper", "iodine", "selenium"]),
    ("vitamins", ["vitA", "retinol", "thiamin", "riboflavin", "niacin", "vitB6", "folate", "folic_acid", "vitB12", "vitC",
                  "vitD", "vitE", "vitK1"]),
    ("essential amino acids", ["histidine", "isoleucine", "leucine", "lysine", "met_cys", "phe_tyr", "threonine",
                               "tryptophan", "valine"]),
    ("food groups", ["fruit"]),
    ("your limits on foods", []),        # the Limits box on the Plan page: rows of kind "food" (lp.load limits)
]
GROUP_OF = {n: g for g, names in NUTRIENT_GROUPS for n in names}
GROUP_ORDER = {g: i for i, (g, _) in enumerate(NUTRIENT_GROUPS)}


def ctx():
    return st.session_state["_ctx"]


def chain_name(c):
    return {A.ALL_CHAINS: "every chain (cheapest per food)", A.CHEAPEST: "cheapest chain (automatic)"}.get(c) or A.CHAIN_NAMES.get(c, c)


def snapshot_date():
    """The date of the Checkjebon snapshot the catalog was built from (data/catalog_snapshot.txt, written by catalog.py)."""
    f = A.ROOT / "data/catalog_snapshot.txt"
    name = f.read_text().strip() if f.exists() else ""
    return name.removeprefix("checkjebon_").removesuffix(".json") or "unknown"


SOURCES = {
    "nevo": "NEVO 2025/9.0 food composition (RIVM)",
    "recipes": "NEVO 2025/9.0 recipes",
    "prices": "Checkjebon supermarket prices",
    "limits": "limits from Voedingscentrum 2025, Gezondheidsraad, EFSA and WHO",
    "amino": "amino acids from USDA SR Legacy",
    "cooking": "cooking losses from NEVO's cooked entries and USDA retention factors",
    "model": "the linear program in lp.py",
    "supplements": "supplement labels and prices from supermarket and drugstore websites and Checkjebon (data/supplements.tsv)",
}


def sources(*keys):
    """One grey line under a table or chart: where its numbers come from. The Data & sources page has the details."""
    parts = [SOURCES[k] + (f" ({snapshot_date()})" if k == "prices" else "") for k in keys]
    st.caption("Sources: " + " · ".join(parts) + ". Details on the **Data & sources** page.")


def tile(col, label, value, sub="", delta=None, help=None):
    col.metric(label, value, delta=delta, delta_color="inverse", help=help)     # inverse: dearer is red, cheaper is green
    if sub:
        col.caption(sub)


# ---------------- tables and downloads ----------------
def csv_bytes(df):
    """A CSV for download. The last line carries the NEVO reference, as every output must (a '#' comment line:
    pandas reads it with comment='#', a spreadsheet shows it as the last row)."""
    return (pd.DataFrame(df).to_csv(index=False) + f"# {NEVO_LINE}\n").encode()


def _fmt(s):
    """A display format for a column without one: numbers to 4 significant digits, blanks for missing values."""
    if pd.api.types.is_bool_dtype(s):
        return None
    if pd.api.types.is_integer_dtype(s):
        return "{:,d}"
    if pd.api.types.is_numeric_dtype(s):
        return lambda v: f"{v:,.4g}"
    return None


def table(df, name, fmt=None, height=None, column_config=None, download=True, label="Download CSV"):
    """A read-only table with blank cells for missing values (not "None"), and a CSV download under it.
    fmt: {column: format string or function} for the cells; other numbers get 4 significant digits."""
    df = pd.DataFrame(df)
    if df.empty:
        st.caption("Nothing to show.")
        return
    fmt = fmt or {}
    styled = df.style.format({c: fmt.get(c, _fmt(df[c])) for c in df.columns if fmt.get(c, _fmt(df[c]))}, na_rep="")
    if height is None:
        height = "auto" if len(df) <= 12 else min(35 * len(df) + 38, 640)
    st.dataframe(styled, hide_index=True, width="stretch", height=height, column_config=column_config)
    if download:
        download_csv(df, name, label)


def download_csv(df, name, label="Download CSV"):
    st.download_button(label, data=csv_bytes(df), file_name=f"{name}.csv", mime="text/csv", key=f"dl_{name}",
                       on_click="ignore", icon=":material/download:", type="tertiary")


def chart_block(chart, data, name, note=None, source=None):
    """A chart, its caption and sources, and under it (folded) its numbers as a table, with the data as CSV and the chart
    as HTML (which can save itself as PNG or SVG)."""
    h = chart.to_dict().get("height")
    st.altair_chart(chart, width="stretch", theme=None, height=int(h) + 130 if isinstance(h, (int, float)) else "content")
    if note:
        st.caption(note)
    if source:
        sources(*source)
    with st.expander("The numbers behind this chart"):
        table(pd.DataFrame(data), name, download=False)
        b = st.columns([1, 1, 3])
        with b[0]:
            download_csv(pd.DataFrame(data), name, "Data (CSV)")
        b[1].download_button("Chart (HTML, saves as PNG/SVG)", data=chart.to_html().encode(), file_name=f"{name}.html",
                             mime="text/html", key=f"dl_{name}_html", on_click="ignore", icon=":material/download:",
                             type="tertiary")


def heading(text, anchor):
    st.subheader(text, anchor=anchor, divider="gray")


def contents(items):
    """A line of links to the headings on a long page: [(title, anchor)]."""
    st.markdown(" · ".join(f"[{t}](#{a})" for t, a in items))


# ---------------- nutrients ----------------
def nutrient_rows(reqs, binding=()):
    """The nutrient table as rows: grouped (energy and macros, fatty acids, minerals, vitamins, amino acids)."""
    out = []
    for r in reqs:
        group = "your limits on foods" if r.get("kind") == "food" else GROUP_OF.get(r["name"], "other")
        out.append({"": "✓" if r["ok"] else "✗", "group": group, "nutrient": r["nutrient"],
                    "intake": r["intake"], "unit": r["unit"], "minimum": r["lower"], "maximum": r["upper"],
                    "% of minimum": r["pct_lower"], "% of maximum": r["pct_upper"],
                    "sets the price": "yes" if r["name"] in binding else ""})
    out.sort(key=lambda r: GROUP_ORDER.get(r["group"], 99))
    return out


def nutrient_table(reqs, name, binding=()):
    rows_ = nutrient_rows(reqs, binding)
    pct = lambda v: f"{v:,.0f}%"
    table(rows_, name, fmt={"intake": lambda v: f"{v:,.4g}", "minimum": lambda v: f"{v:,.4g}",
                            "maximum": lambda v: f"{v:,.4g}", "% of minimum": pct, "% of maximum": pct},
          height=35 * len(rows_) + 38)


def nutrient_summary(reqs, binding=()):
    """One line: how many limits are met, which ones are missed, which set the price."""
    missed = [r["nutrient"] for r in reqs if not r["ok"]]
    sets = [r["nutrient"] for r in reqs if r["name"] in binding]
    if missed:
        st.error(f"**{len(missed)} of {len(reqs)} limits missed:** " + ", ".join(missed) + ".")
    else:
        st.success(f"**All {len(reqs)} limits met.**" + (f" {len(sets)} of them set the price: " + ", ".join(sets) + "."
                                                          if sets else ""))


# ---------------- the context: settings -> what to solve ----------------
class Ctx:
    """Everything the pages need from the sidebar settings. Built by app.py; solutions computed on first use."""

    def __init__(self, ss, theme, person, chain, ranking, week_ranked, own, ex, flip, pure_rank_kw, week_kw, single):
        self.ss, self.theme, self.person, self.chain = ss, theme, person, chain
        self.ranking, self.week_ranked = ranking, week_ranked
        self.real = ss.mode == "realistic"
        self.own, self.own_keys, self.ex, self.flip = own, {o[0] for o in own}, ex, flip
        self.pure_rank_kw, self.week_kw = pure_rank_kw, week_kw
        self.pills = pure_rank_kw.get("pills") or A.S.DEFAULT
        self.pure_kw = dict(chain=chain, **pure_rank_kw)
        self.real_kw = dict(chain=chain, **week_kw)
        # The plan the before-and-after compares with: the same one without your own foods. The category ticks stay on
        # in both, unless the switch says otherwise or they're all there is to take away.
        drop = bool(ss.no_categories) and (ss.compare_ticks or not own)
        self.compare_with = ("without your foods and category ticks" if own and drop else "without your foods" if own else
                             "without your category ticks" if drop else None)
        base_cats = [] if drop else sorted(ss.no_categories)
        self.single = single        # the ✗ marks and the foods of the kinds left out
        self.base_pure_kw = {**self.pure_kw, "excluded": A.effective_excluded(single, base_cats), "own": []}
        self.base_real_kw = {**self.real_kw, "no_cats": base_cats, "own": []}
        self.lp_kw = {k: v for k, v in self.pure_kw.items() if k != "food_cost"}      # the "why" charts: the plain LP

    @cached_property
    def pure(self):
        return A.pure(**self.pure_kw)

    @cached_property
    def pure_base(self):
        return A.pure(**self.base_pure_kw) if self.compare_with else None

    @property
    def solved(self):
        """The realistic week is in the cache (and so is the one to compare with): no Solve needed."""
        return (self.week_ranked and A.realistic.is_cached(**self.real_kw)
                and (not self.compare_with or A.realistic.is_cached(**self.base_real_kw)))

    @cached_property
    def R(self):
        ok = self.real and self.week_ranked and A.realistic.is_cached(**self.real_kw)
        return A.realistic(**self.real_kw) if ok else None

    @cached_property
    def R_base(self):
        ok = self.real and self.week_ranked and self.compare_with and A.realistic.is_cached(**self.base_real_kw)
        return A.realistic(**self.base_real_kw) if ok else None

    @property
    def src(self):
        """The diet the nutrient charts describe: the realistic week once it's solved, else the pure LP."""
        return self.R if (self.real and self.R and self.R["ok"]) else self.pure

    @property
    def src_tag(self):
        return "realistic week" if self.src is self.R else "pure LP"

    def describe(self):
        """The settings in words, for page headers and the export's README."""
        ss = self.ss
        bits = [A.profiles().get(ss.profile, ss.profile), chain_name(self.chain),
                "realistic week" if self.real else "pure LP"]
        if self.real:
            bits.append(f"{ss.strictness}, {ss.pattern}" + (", batch cooking" if ss.batch else ""))
        if ss.food_cost:
            bits.append(f"€{ss.food_cost:.2f} per food")
        if ss.food_limits:
            bits.append(f"{len(ss.food_limits)} limit{'s' if len(ss.food_limits) > 1 else ''} on foods")
        if self.pills != A.S.DEFAULT:
            bits.append("supplements: " + A.S.describe(self.pills))
        return " · ".join(bits)


# ---------------- cook ticks (Plan and Foods pages) ----------------
def cook_col():
    return st.column_config.CheckboxColumn(
        "cook", width="small", help="Ticked: counted as cooked (boiled), with the nutrients cooking leaves. Unticked: raw. "
                                    "Empty: no choice, the food is eaten as sold. Press Apply after ticking.")


def apply_button(label="Apply", key=None):
    return st.form_submit_button(label, type="primary", key=key,
                                 help="Ticks only take effect when you press this, so you can click as many as you like first.")


def cook_flips(edited):
    """The cook ticks of a table, back into cook_flip: a tick that differs from the food's default is a flip.
    Rows without a choice (None) and rows not in the table keep what they had."""
    how = A.cook_info()
    flips = set(st.session_state.cook_flip)
    for k, v in zip(edited["key"], edited["cook"]):
        h = how.get(k)
        if h is None or not h.cookable or v is None or pd.isna(v):
            continue
        (flips.add if bool(v) != h.ticked else flips.discard)(k)
    return sorted(flips)


def tick_table(rows_, cols, cfg, name):
    """A plan table you can change: ✗ leaves that food out, ✗ kind every food of its kind (all pasta, all rice ...),
    cook counts it cooked or raw. In a form: ticking is instant, nothing is recalculated before Apply. What's left out is
    put back in the 'Leave out or put back' box on the Plan page, or on the Foods page."""
    ss = st.session_state
    df = pd.DataFrame(rows_)
    if df.empty:
        return
    df["✗"], df["✗ kind"] = False, False
    with st.form(f"ticks_{name}", border=False):
        edited = st.data_editor(
            df[["✗", "✗ kind", "cook"] + cols + ["key"]], hide_index=True, width="stretch", height=35 * len(df) + 38,
            key=f"ticks_{name}_{ss.editor_v}", disabled=list(cols),
            column_config={**cfg, "cook": cook_col(), "key": None,
                           "✗": st.column_config.CheckboxColumn("✗", width="small", help="Leave this food out."),
                           "✗ kind": st.column_config.CheckboxColumn(
                               "✗ kind", width="small", help="Leave out every food of this kind (the 'kind' column): all "
                                                             "pasta, all rice, all wheat flour ...")})
        if apply_button("Apply"):
            out = set(edited.loc[edited["✗"].eq(True), "key"])       # eq: a cell cleared with Delete is None
            kinds_out = {A.K.KIND[k] for k in edited.loc[edited["✗ kind"].eq(True), "key"] if k in A.K.KIND}
            ss.excluded = sorted(set(ss.excluded) | out)
            ss.no_kinds = sorted(set(ss.no_kinds) | kinds_out)
            ss.cook_flip, ss.editor_v = cook_flips(edited), ss.editor_v + 1
            st.rerun()


def left_out_box(where):
    """Leave out, or put back, whole kinds and single foods: two lists in a form, applied with Apply. On the Plan page;
    the Foods page has the same kinds list in its own form."""
    ss = st.session_state
    with st.expander("Leave out or put back foods and kinds"):
        st.caption("A **kind** is a group of similar foods: wheat flour, pasta and noodles, rice, oily fish, cabbages ... "
                   "Pick what you don't want to eat; remove it from the list to put it back. Then press **Apply**. "
                   "Whole categories (no meat, no dairy) and allergies are ticks on the Foods page.")
        with st.form(f"left_out_{where}", border=False):
            kinds_pick = st.multiselect("Kinds left out", A.K.KINDS, default=[k for k in ss.no_kinds if k in A.K.KINDS],
                                        format_func=lambda k: f"{k} ({A.K.COUNT[k]})", key=f"lo_kinds_{where}_{ss.editor_v}",
                                        placeholder="e.g. pasta and noodles, rice, wheat flour")
            options = sorted(set(A.P.FOODS) | set(A.S.SUPP), key=lambda k: A.label(k).lower())
            foods_pick = None
            if len(ss.excluded) <= 100:
                foods_pick = st.multiselect("Foods left out", options, default=[k for k in ss.excluded if k in options],
                                            format_func=A.label, key=f"lo_foods_{where}_{ss.editor_v}",
                                            placeholder="type to search, e.g. peanuts")
            else:
                st.caption(f"{len(ss.excluded)} single foods are left out: too many to list here. Put them back on the "
                           "Foods page (Put back all foods).")
            if st.form_submit_button("Apply", type="primary", key=f"left_out_apply_{where}"):
                ss.no_kinds = sorted(kinds_pick)
                if foods_pick is not None:
                    ss.excluded = sorted(foods_pick)
                ss.editor_v += 1
                st.rerun()


# ---------------- the plan as one download ----------------
def plan_zip(c):
    """Everything on the Plan and Nutrients pages as CSV files, the settings, and a README with the sources."""
    ss, src = c.ss, c.src
    buf = io.BytesIO()
    files = {}
    if src is c.R:
        files["dinners.csv"] = pd.DataFrame(c.R["dinners"])
        files["eaten_as_such.csv"] = pd.DataFrame(c.R["direct"]).drop(columns=["key", "raw_warn", "at_limit"], errors="ignore")
        files["shopping_list.csv"] = pd.DataFrame(c.R["shop"])
        files["rules_bent.csv"] = pd.DataFrame(c.R["bent"], columns=["rule", "saving_day"])
    else:
        files["basket.csv"] = pd.DataFrame(c.pure["basket"]).drop(columns=["key", "raw_warn", "at_limit"], errors="ignore")
    files["nutrients.csv"] = pd.DataFrame(nutrient_rows(src["reqs"], src.get("binding", ())))
    files["food_x_vitamins_minerals.csv"] = pd.DataFrame(src["by_food"])
    files["food_x_macros.csv"] = pd.DataFrame(src["macros"])
    settings = {k: ss[k] for k in A.DEFAULTS if k not in ("cache_mb",)}
    settings["chain_used"] = c.chain
    readme = "\n".join([
        f"nevo-diet plan, exported {date.today().isoformat()}",
        "",
        f"Settings: {c.describe()}",
        f"Cost: €{src['cost']:.2f} a day, €{7 * src['cost']:.2f} a week (the cost per food, if any, is not included).",
        "",
        "Files: one CSV per table (comma-separated, UTF-8; the last line of each is a '#' comment with the NEVO",
        "reference). settings.json has every setting, so the plan can be made again in the app.",
        "",
        f"Prices: Checkjebon snapshot {snapshot_date()} (MIT licence), cheapest product per food at the chain.",
        "Nutrient limits: data/requirements.tsv (Voedingscentrum 2025, Gezondheidsraad, EFSA, WHO); see SOURCES.md.",
        "Amino acids: USDA FoodData Central SR Legacy. Cooking losses: USDA Table of Nutrient Retention Factors, Release 6.",
        "",
        "Not medical advice. Allergy ticks are worked out from names and typical recipes: read every label.",
        "",
        NEVO_LINE,
    ])
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.txt", readme + "\n")
        z.writestr("settings.json", json.dumps(settings, indent=1, ensure_ascii=False) + "\n")
        for fname, df in files.items():
            z.writestr(fname, csv_bytes(df))
    return buf.getvalue()


def limit_state_binding(result):
    """{(requirement, side)} for the charts, from a pure LP result (None for the realistic week)."""
    return {tuple(b) for b in result.get("binding_sides", ())} if "binding_sides" in result else None


__all__ = ["A", "C", "NEVO_LINE", "ctx", "chain_name", "snapshot_date", "sources", "tile", "table", "chart_block",
           "download_csv", "csv_bytes", "heading", "contents", "nutrient_table", "nutrient_summary", "Ctx", "plan_zip"]
