"""How to use: the sidebar step by step, what every setting does, leaving foods out and putting them back, common tasks
(docs/how-to-use.md, which reads the same on GitHub)."""
import streamlit as st

import appcore as A

st.markdown((A.ROOT / "docs/how-to-use.md").read_text())
st.markdown("#### Go to")
cols = st.columns(4)
for col, (path, title, icon) in zip(cols, [("views/plan.py", "Plan", ":material/restaurant:"),
                                           ("views/foods.py", "Foods: leave out foods and kinds", ":material/shopping_basket:"),
                                           ("views/profile.py", "Profile & limits", ":material/person:"),
                                           ("views/about.py", "About: what this is", ":material/info:")]):
    col.page_link(path, label=title, icon=icon)
