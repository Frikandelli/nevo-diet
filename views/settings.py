"""Settings: start over, the cook ticks, the solution cache, and fresh prices."""
import streamlit as st

import appcore as A
import ui

c = ui.ctx()
ss = c.ss

st.title("Settings")
st.subheader("Start over", anchor="reset")
st.caption("Back to the defaults: the sidebar, My foods, your limits on foods (none), every tick and every ✗. Your own "
           "profiles, their nutrient limits and the cache stay.")
if not ss.get("reset_ask"):
    if st.button("Reset everything"):
        ss.reset_ask = True
        st.rerun()
else:
    st.warning("This also empties My foods and your limits on foods, and takes off all your ticks, allergy ticks too. Sure?")
    a, b, _ = st.columns([1, 1, 4])
    if a.button("Yes, reset everything", type="primary"):
        ss.reset_all = True
        st.rerun()
    if b.button("Cancel"):
        ss.reset_ask = False
        st.rerun()

st.subheader("Cooking", anchor="cooking")
st.caption("Each food starts cooked or raw as it's usually eaten: cooked for raw meat, fish, eggs, frozen vegetables, dried "
           "pulses, flour, pasta, rice, potatoes, and vegetables usually cooked in a Dutch kitchen; raw for tomatoes, "
           "peppers and oat flakes. Cooked means boiled: NEVO's own cooked entry where there is one, else the raw values "
           "with USDA's retention factors (the share of each vitamin and mineral boiling leaves). Change a food's tick on "
           "the Foods page or in the plan table.")
if st.button(f"Reset the cook ticks to the defaults ({len(ss.cook_flip)} changed)", disabled=not ss.cook_flip):
    ss.cook_flip, ss.editor_v = [], ss.editor_v + 1
    st.rerun()

st.subheader("Solution cache", anchor="cache")
st.caption(f"Every computed solution is kept in `{A.CACHE_DIR}` (outside git) and reused; the least recently used "
           "entries go first when the cache is full. A change to the data or the model code makes old entries unreachable.")
a, b, c_ = st.columns(3)
a.number_input("Cache limit (MB)", min_value=10, max_value=10000, step=50, key="cache_mb")
ui.tile(b, "In use", f"{A.cache_size_mb():.1f} MB", f"{len(A.cache_files())} entries")
if c_.button("Empty the cache"):
    A.clear_all()
    st.rerun()

st.subheader("Prices", anchor="prices")
snap = sorted((A.ROOT / "data").glob("checkjebon_*.json"))
st.caption(f"The catalog is built from the Checkjebon snapshot of **{ui.snapshot_date()}**"
           + (f" (on this computer: `{snap[-1].name}`)" if snap else " (the snapshot file itself isn't on this computer, "
              "and isn't needed to run the app)")
           + ". Fetching new prices downloads the latest snapshot and rebuilds the catalog (`fetch_prices.py`, "
           "`expand.py`, `catalog.py`, about 2 minutes). New products can bring new matcher errors; odd foods in a basket "
           "are worth a check.")
if st.button("Fetch new prices"):
    with st.status("Updating prices ...", expanded=True) as stt:
        try:
            n = A.refresh_prices(st.write)
            stt.update(label=f"Prices updated; {n} outdated cache entries removed.", state="complete")
        except Exception as e:
            stt.update(label="Price update failed", state="error")
            st.code(str(e))
