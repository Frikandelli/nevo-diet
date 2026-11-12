"""Data & sources: every dataset and what is done to it (docs/data.md), every derived table and report to download,
and where each limit comes from (data/requirements.tsv, SOURCES.md)."""
import csv
import io
import zipfile

import pandas as pd
import streamlit as st

import appcore as A
import ui

c = ui.ctx()
ROOT = A.ROOT

# The derived and hand-made tables in data/: what each holds, and what makes it. NEVO's own files aren't offered:
# they are RIVM's, and the terms don't allow passing them on.
FILES = [
    ("catalog_foods.tsv", "The 608 foods in the model: NEVO code and name, food group, cooked NEVO partner and yield, "
                          "how many chains sell it.", "catalog.py"),
    ("catalog_prices.tsv", "Per food and chain, the cheapest product: price per 100 g edible, product name, pack size and price.",
     "catalog.py"),
    ("catalog_snapshot.txt", "Which Checkjebon snapshot the catalog was built from.", "catalog.py"),
    ("auto_matches.tsv", "Every supermarket product matched to a NEVO food by name, with its price per 100 g edible.",
     "expand.py"),
    ("auto_prices.tsv", "The cheapest automatically matched product per NEVO food and chain.", "expand.py"),
    ("foods.tsv", "The 53 hand-mapped staples: search pattern, NEVO raw and cooked code, edible fraction, yield.", "by hand"),
    ("review.tsv", "Hand decisions on products: exclude, remap to another NEVO code, or keep, with the reason.", "by hand"),
    ("requirements.tsv", "Every nutrient limit: men's values, women's overrides, how it scales, source, link, evidence.",
     "by hand, from the sources"),
    ("profiles.tsv", "The four standard profiles: sex, age, height, activity, protein per kg, with sources.", "by hand"),
    ("amino_foods.tsv", "Essential amino acids per gram of protein for every food, and its digestibility.",
     "amino.py (USDA SR Legacy)"),
    ("amino_families.tsv", "The median USDA amino acid profile per food family (oats, wheat, legumes, dairy ...).", "amino.py"),
    ("cooking.tsv", "Which foods are cooked by default (must / usual / raw / as sold) and their USDA retention class.",
     "by hand"),
    ("retention.tsv", "USDA retention factors for the classes used: the share of each vitamin and mineral left after boiling.",
     "cooking.py (USDA Release 6)"),
    ("kinds.tsv", "Kinds of food for leaving out a whole kind at once (wheat flour, pasta and noodles, rice ...): rules on the "
                  "food group and NEVO name, first match wins.", "by hand"),
    ("dinners.tsv", "Which NEVO dishes are dinners: quick or batch, hands-on minutes, whether a starch side comes with it.",
     "by hand"),
    ("prices.tsv", "Old: prices of the 50 hand-mapped foods only. Not used by the app.", "price.py"),
]
REPORTS = [
    ("avg_man.md", "Average man: the full analysis (run.py): the cheapest diet, reduced costs, variants, protein sweep, "
                   "wiggle room, nutrient totals, availability, price split, removal tree, what each limit costs."),
    ("avg_woman.md", "Average woman: the same analysis."),
    ("active_man.md", "Active man: the same analysis."),
    ("active_woman.md", "Active woman: the same analysis."),
    ("profiles.md", "The four standard profiles at every chain (compare.py)."),
    ("plans.md", "Shopping lists in whole packs at one chain: a weekly list and a 4-week rotation (plan.py)."),
    ("meals.md", "A week of meals for the average man at AH (meals.py)."),
    ("cooking-notes.md", "Cooking notes for that week, written by hand."),
    ("dishes.md", "NEVO's dishes priced at every chain, with every stand-in (dishes.py)."),
    ("sensitivity.md", "How much cooking losses and the absorption assumptions change the price (sensitivity.py)."),
]


def n_rows(path):
    if path.suffix != ".tsv":
        return None
    with open(path, encoding="utf-8") as fh:
        return sum(1 for _ in fh) - 1


def zip_of(paths, readme):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.txt", readme + "\n\n" + ui.NEVO_LINE + "\n")
        for p in paths:
            z.write(p, p.name)
    return buf.getvalue()


st.title("Data & sources")
st.caption("Where every number comes from, what was done to it, and every table to download.")
tabs = st.tabs(["Datasets and processing", "Tables to download", "Limits and their sources", "Reports"])

with tabs[0]:
    text = (ROOT / "docs/data.md").read_text().replace("snapshot of 2026-10-30", f"snapshot of {ui.snapshot_date()}")
    st.markdown(text.split("\n", 1)[1])          # without its title: the page has one

with tabs[1]:
    st.markdown("The tables the model reads, as they are in the repository's `data/` folder (tab-separated, UTF-8). "
                "*Made by* says which script writes a table; *by hand* ones are edited directly, each change with a "
                "reason. NEVO's own files aren't here: they are RIVM's, and its terms don't allow passing them on.")
    present = [(f, what, by) for f, what, by in FILES if (ROOT / "data" / f).exists()]
    overview = [{"file": f"data/{f}", "what": what, "made by": by, "rows": n_rows(ROOT / "data" / f),
                 "size": f"{(ROOT / 'data' / f).stat().st_size / 1e3:,.0f} kB"} for f, what, by in present]
    ui.table(overview, "data_files", fmt={"rows": "{:,.0f}"}, download=False,
             column_config={"what": st.column_config.TextColumn(width="large")})
    st.download_button("All these tables (ZIP)", data=zip_of(
                           [ROOT / "data" / f for f, _, _ in present],
                           "nevo-diet data tables: see docs/data.md for what each one is and how it was made."),
                       file_name="nevo-diet-data.zip", mime="application/zip", key="dl_data_zip", on_click="ignore",
                       icon=":material/folder_zip:", type="primary")
    pick = st.selectbox("Look at one table", [f for f, _, _ in present], key="data_pick",
                        format_func=lambda f: f"data/{f}")
    path = ROOT / "data" / pick
    if path.suffix == ".tsv":
        df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False, quoting=csv.QUOTE_NONE)
        st.caption(f"{len(df):,} rows" + (", the first 500 shown" if len(df) > 500 else ""))
        st.dataframe(df.head(500), hide_index=True, width="stretch", height=420)
    else:
        st.code(path.read_text())
    st.download_button(f"data/{pick}", data=path.read_bytes(), file_name=pick, key="dl_data_one", on_click="ignore",
                       icon=":material/download:", type="tertiary")

with tabs[2]:
    st.markdown("Every limit the diet must meet, for the profile and body in the sidebar, with its source. Change them on "
                "the **Profile & limits** page. *Evidence*: confirmed against the source, a project choice, not a firm "
                "target, or newer advice differs.")
    rows_ = A.limit_rows(c.person)
    ui.table([{k: v for k, v in r.items() if k not in ("key", "standard min", "standard max")} for r in rows_],
             "limits_with_sources", fmt={"min": "{:,.4g}", "max": "{:,.4g}"}, height=35 * len(rows_) + 38,
             column_config={"link": st.column_config.LinkColumn(display_text="open"),
                            "source": st.column_config.TextColumn(width="large")})
    with st.expander("How every limit was checked, and where the model deliberately differs (SOURCES.md)", expanded=True):
        st.markdown((ROOT / "SOURCES.md").read_text().split("\n", 1)[1])

with tabs[3]:
    st.markdown("Reports written by the scripts for the **standard profiles** (not your settings), with the snapshot of "
                f"{ui.snapshot_date()}. Rerun a script to bring one up to date; `README.md` lists them.")
    present = [(f, what) for f, what in REPORTS if (ROOT / "reports" / f).exists()]
    if not present:                     # a fresh clone: the reports are written by the scripts, not kept in git
        st.info("No reports yet. Run the scripts (`README.md` → *Rebuild and reports*) to write them to `reports/`.")
    else:
        ui.table([{"report": f"reports/{f}", "what": what} for f, what in present], "reports", download=False,
                 column_config={"what": st.column_config.TextColumn(width="large")})
        st.download_button("All reports (ZIP)", data=zip_of([ROOT / "reports" / f for f, _ in present],
                                                                    "nevo-diet reports (Markdown)."),
                           file_name="nevo-diet-reports.zip", mime="application/zip", key="dl_reports_zip",
                           on_click="ignore", icon=":material/folder_zip:", type="primary")
        pick = st.selectbox("Read one report", [f for f, _ in present], key="report_pick",
                            format_func=lambda f: f"reports/{f}")
        path = ROOT / "reports" / pick
        st.download_button(f"reports/{pick}", data=path.read_bytes(), file_name=pick, key="dl_report_one",
                           on_click="ignore", icon=":material/download:", type="tertiary")
        with st.container(border=True):
            st.markdown(path.read_text())
