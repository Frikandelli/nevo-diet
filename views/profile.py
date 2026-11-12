"""Profile & limits: create or edit profiles, and set the minimum and maximum per nutrient, with each limit's source."""
import pandas as pd
import streamlit as st

import appcore as A
import ui

c = ui.ctx()
ss = c.ss
profiles = A.profiles()
name = ss.profile
F_ = A.profile_fields(name)

st.title("Profile & limits")
st.subheader(f"Profile: {profiles[name]}", anchor="profile")
st.caption("Saved on this computer in `~/.config/nevo-diet/profiles.json`, outside git. "
           + ("This is one of your own profiles." if A.is_own(name) and not A.is_standard(name) else
              "You changed this standard profile." if A.is_own(name) else "A standard profile: saving keeps your "
              "changes next to the original, which you can always restore."))
with st.form(f"profile_form_{name}"):
    cc = st.columns([2.2, 1, 1, 1])
    label = cc[0].text_input("Name", value=F_["label"])
    sex = cc[1].radio("Sex", ["m", "f"], index=0 if F_["sex"] == "m" else 1, horizontal=True,
                      format_func=lambda s: "man" if s == "m" else "woman", help="Picks the men's or women's norms.")
    age = cc[2].number_input("Age", min_value=18, max_value=100, value=int(F_["age"]),
                             help="Sets the energy estimate. The nutrient norms stay the 18-69 values, see the note below.")
    pal = cc[3].number_input("Activity level (PAL)", min_value=1.2, max_value=2.5, step=0.05, value=round(F_["pal"], 2),
                             help="Gezondheidsraad 2022/19: 1.4 light, 1.6 moderate, 1.8 active, 2.0 very active.")
    cc = st.columns(4)
    weight = cc[0].number_input("Weight (kg)", min_value=30.0, max_value=250.0, value=round(F_["weight"], 1), format="%.1f")
    height = cc[1].number_input("Height (cm)", min_value=120.0, max_value=230.0, step=1.0, value=F_["height"], format="%.1f",
                                placeholder="not set")
    kcal = cc[2].number_input("Fixed calories (kcal/day)", min_value=800.0, max_value=8000.0, step=50.0, value=F_["kcal"],
                              format="%.0f", placeholder="estimate", help="Blank: estimated from body and activity.")
    per_kg = cc[3].number_input("Protein (g per kg)", min_value=0.5, max_value=4.0, step=0.05, value=F_["protein_per_kg"],
                                help="0.83 is the Dutch norm for adults. 1.4-2.0 is the ISSN's range for people who train.")
    source = st.text_input("Note or source", value=F_["source"])
    cc = st.columns([1, 1, 3])
    save = cc[0].form_submit_button("Save changes", type="primary")
    save_new = cc[1].form_submit_button("Save as new profile")
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
        ss.switch_profile = name if A.is_standard(name) else A.DEFAULTS["profile"]
        st.rerun()

st.subheader("Minimum and maximum per nutrient", anchor="limits")
st.caption("Change a number, or clear it for no limit (an empty cell shows as *None*). The diet is solved again with your "
           "limits, and they are saved with this profile. The calories and protein boxes in the sidebar change the "
           "standard values shown here. Every limit has its source and link; the **Data & sources** page explains which "
           "ones newer advice has changed.")
rows_ = A.limit_rows(c.person)
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
ui.download_csv(df.drop(columns=["key"]), f"limits_{name}", "These limits (CSV)")
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
