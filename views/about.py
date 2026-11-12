"""About: what nevo-diet is and how to read it (docs/about.md), and where to find what in the app."""
import streamlit as st

import appcore as A

PAGES = [
    ("views/plan.py", "Plan", ":material/restaurant:",
     "The answer: price, basket or week of meals, shopping list, your own foods, the nutrient check. Leave out foods or "
     "whole kinds (all pasta, all rice) and put them back. Download it as a ZIP."),
    ("views/nutrients.py", "Nutrients", ":material/nutrition:",
     "Charts of what's in the diet: minimums met, maximums used, which food gives which vitamin, where the macros and "
     "the money go, and the full nutrient table."),
    ("views/why.py", "Why this diet", ":material/insights:",
     "The linear program explained through its dual: what each food is worth and pays for, what each limit costs, cost "
     "curves, wiggle room, what replaces what, every chain."),
    ("views/foods.py", "Foods", ":material/shopping_basket:",
     "Every food the chain sells (608 in all) with prices and nutrients: leave out foods, kinds, categories and allergies, "
     "and count foods cooked or raw."),
    ("views/dishes.py", "Dishes", ":material/ramen_dining:",
     "NEVO's dishes and soups priced from their recipes at the chain, with their ingredients and stand-ins."),
    ("views/profile.py", "Profile & limits", ":material/person:",
     "Make your own profile, and change the minimum and maximum of any nutrient; every limit with its source."),
    ("views/howto.py", "How to use", ":material/help:",
     "Step by step: what every setting in the sidebar does, leaving out foods and kinds and putting them back, common tasks."),
    ("views/data.py", "Data & sources", ":material/database:",
     "Every dataset, what was done to it, every derived table and report to download, and where each limit comes from."),
    ("views/settings.py", "Settings", ":material/settings:", "Start over, reset the cook ticks, the solution cache, fetch new prices."),
]

text = (A.ROOT / "docs/about.md").read_text()
head, _, rest = text.partition("\n## Getting started")
st.markdown(head)

st.markdown("## Where to find what")
cols = st.columns(2)
for i, (path, title, icon, what) in enumerate(PAGES):
    with cols[i % 2].container(border=True):
        st.page_link(path, label=f"**{title}**", icon=icon)
        st.caption(what)
st.caption("The **sidebar** on every page holds what to solve, in five steps: who eats, calories and protein, where you "
           "shop, kind of plan (with Solve), cost per food; the optional settings are folded at the bottom.")

st.markdown("## Getting started" + rest)
