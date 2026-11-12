"""Smoke test of the app: every page (charts included) renders without errors in several settings.
nix-shell --run 'python3 test_app.py'   (uses a temporary settings file; the cache is the normal one)

The app has one page per file in views/; the sidebar (app.py) is drawn on every page. `at` stays on the page it was
last switched to, so a check of the Foods or Settings page switches there first and back to the Plan page after."""
import json
import os
import re
import tempfile
import time

from streamlit.testing.v1 import AppTest

_tmp = tempfile.mkdtemp()
os.environ["NEVO_DIET_SETTINGS"] = os.path.join(_tmp, "settings.json")
os.environ["NEVO_DIET_PROFILES"] = os.path.join(_tmp, "profiles.json")
# Most of these tests compare with the plain LP. The cost per food has its own section at the end.
open(os.environ["NEVO_DIET_SETTINGS"], "w").write(json.dumps({"food_cost": 0.0}))
PAGES = ["plan", "nutrients", "why", "foods", "supplements", "dishes", "profile", "data", "howto", "about", "settings"]


def check(at, what):
    assert not at.exception, (what, at.exception)
    print(f"{what:38} " + " | ".join(str(m.value) for m in at.metric[:4]))


def page(name):
    """Switch to a page (views/<name>.py) and draw it."""
    at.switch_page(f"views/{name}.py").run()
    assert not at.exception, (name, at.exception)


def every_page(what):
    """Every page renders with the current settings; back on the Plan page after."""
    t = time.time()
    for p in PAGES:
        page(p)
    page("plan")
    print(f"{what:38} every page renders ({time.time() - t:.0f} s)")


at = AppTest.from_file("app.py", default_timeout=600).run()
check(at, "pure, avg_man, ah")
every_page("pure, avg_man, ah")
import appcore as A
_r = A.pure(profile="avg_man", chain="ah", cooked=True, excluded=[], min3=False)
_intake = {x["nutrient"]: x["intake"] for x in _r["reqs"]}
for n in {x["nutrient"] for x in _r["by_food"]}:
    got = sum(x["amount"] for x in _r["by_food"] if x["nutrient"] == n)
    assert abs(got - _intake[n]) < 1e-6 * max(1, _intake[n]), (n, got, _intake[n])
print("food coverage adds up to each nutrient's intake")
_basket = {b["food"] for b in _r["basket"]}
assert {(x["food"], x["nutrient"]) for x in _r["macros"]} == {(f, A.nice(n)) for f in _basket for n in A.MACRO}, \
    "the macro split is a full grid: every food x every macro, zeros too"
for n in {x["nutrient"] for x in _r["macros"]}:
    _m = [x for x in _r["macros"] if x["nutrient"] == n]
    assert abs(sum(x["amount"] for x in _m) - _m[0]["day_total"]) < 1e-6 * max(1, _m[0]["day_total"]), n
    assert abs(sum(x["pct"] for x in _m) - (100 if _m[0]["day_total"] > 0 else 0)) < 1e-6, n
assert abs(sum(x["amount"] for x in _r["macros"] if x["nutrient"] == "energy") - _intake["energy"]) < 1e-6 * _intake["energy"]
print("macro split: a full grid, every column adds up to 100% (0 for a macro the diet has none of) and to the day's total")
# A macro the diet has none of keeps its column in the chart (free sugars are often 0).
import charts as C
_zero = [{**x, "amount": 0.0, "pct": 0.0, "day_total": 0.0} if x["nutrient"] == "free sugars" else x for x in _r["macros"]]
_spec = C.macro_split(_zero, "light").to_dict()
assert "free sugars (0 g)" in json.dumps(_spec), "the free sugars column must be drawn at 0 g"
print("macro chart: free sugars keep their column at 0 g")
# Wiggle room: no food that fits in a diet within 5% is missing (the old screen skipped foods entering under 100 g).
_w = A.wiggle(profile="avg_man", chain="ah", cooked=True, excluded=[], min3=False)
_v = A.worth(profile="avg_man", chain="ah", cooked=True, excluded=[], min3=False)
assert len(_w["rows"]) > 100 and any(r["food"] == "Milk semi-skimmed" and r["max"] > 100 for r in _w["rows"]), len(_w["rows"])
assert all(r["reduced_cost"] > -1e-9 for r in _v["rows"]), "dual feasibility: no food is worth more than its price"
assert all(abs(r["reduced_cost"]) < 1e-6 for r in _v["rows"] if r["in_diet"]), "a food in the diet is worth its price"
print(f"wiggle room: {len(_w['rows'])} foods fit within 5%; worth <= price for every food, = for the diet's")
for k, v in [("chain", "all"), ("cook_flip", ["n1139", "pasta"]), ("profile", "avg_woman"), ("min3", True)]:
    at.session_state[k] = v
    at.run()
    check(at, f"pure, {k}={v}")
every_page("pure, avg_woman, all chains, min3")
at.session_state["profile"], at.session_state["chain"], at.session_state["cook_flip"] = "avg_man", "ah", []
at.session_state["min3"] = False
for k, v in [("weight", 95.0), ("height", 190.0), ("kcal", 2400.0), ("protein", 160.0)]:
    at.session_state[k] = v
    at.run()
    check(at, f"pure, {k}={v}")
at.session_state["kcal"], at.session_state["protein"] = 800.0, 500.0
at.run()
assert not at.exception and at.error, "impossible targets should say so"
print("impossible targets: error shown")
for k in ("weight", "height", "kcal", "protein"):
    at.session_state[k] = None
# own profiles and limits
base_cost = A.pure(profile="avg_man", chain="ah", cooked=True, excluded=[], min3=False)["cost"]
key = A.save_profile("avg_man", new_name="Test Person", label="Test Person", sex="f", age=40, weight=60.0, height=165.0, pal=1.5, kcal=None)
assert key == "test_person" and key in A.profiles()
info = A.person_info(key)
assert abs(info["kcal"] - (8.18 * 60 + 502 * 1.65 - 11.6) * 1.5) < 1e-6, info
at.session_state["switch_profile"] = key
at.run()
check(at, "own profile, woman 60 kg")
rows_ = A.limit_rows(key)
assert not A.limit_errors(rows_)
vitc = next(r for r in rows_ if r["key"] == "vitC")
A.set_limits(key, [{**r, "min": 500.0} if r["key"] == "vitC" else r for r in rows_])
assert next(r for r in A.limit_rows(key) if r["key"] == "vitC")["min"] == 500
at.run()
check(at, "own limit: vitamin C at least 500 mg")
req = next(r for r in A.pure(profile=key, chain="ah", cooked=True, excluded=[], min3=False)["reqs"] if r["name"] == "vitC")
assert req["intake"] >= 500 * 0.999, req
rows_ = A.limit_rows(key)
A.set_limits(key, [{**r, "min": 0.0, "max": None} if r["key"] in ("vitC", "potassium") else r for r in rows_])
at.run()
check(at, "own limit: two nutrients without limit")
A.set_limits(key, [{**r, "min": 9000.0} if r["key"] == "energy" else r for r in A.limit_rows(key)])
at.run()
assert not at.exception and at.error
print("impossible own limit: error shown")
assert A.limit_errors([{**vitc, "min": 10.0, "max": 5.0}])
A.set_limits("avg_man", [{**r, "min": 100.0} if r["key"] == "vitC" else r for r in A.limit_rows("avg_man")])
assert A.is_own("avg_man") and A.is_standard("avg_man")
A.set_limits("avg_man", [{**r, "min": r["standard min"], "max": r["standard max"]} for r in A.limit_rows("avg_man")])
assert not A.is_own("avg_man"), "putting the limits back should restore the standard profile"
A.delete_profile(key)
assert key not in A.profiles() and json.loads(open(os.environ["NEVO_DIET_PROFILES"]).read()) == {}
at.session_state["switch_profile"] = "avg_man"
at.run()
assert abs(A.pure(profile="avg_man", chain="ah", cooked=True, excluded=[], min3=False)["cost"] - base_cost) < 1e-9
print("back to the standard profile: same cost")
at.session_state["excluded"] = ["flour_wholemeal", "flour_white"]
at.run()
check(at, "pure, flours excluded")
at.session_state["excluded"] = []
at.session_state["mode"] = "realistic"
at.run()
check(at, "realistic before Solve")
for b in at.button:
    if b.label.startswith("Solve"):
        b.click().run()
check(at, "realistic, solved")
print("bent:", [w.value for w in at.warning])
every_page("realistic, solved")
at.session_state["strictness"] = "strict"
at.run()
for b in at.button:
    if b.label.startswith("Solve"):
        b.click().run()
check(at, "realistic, strict")
# ---------------- your own foods and the category ticks ----------------
import categories as CAT

KW = dict(profile="avg_man", chain="ah", cooked=True, min3=False)
at.session_state["mode"], at.session_state["strictness"] = "pure", "medium"
at.session_state["excluded"] = []
at.run()
assert at.session_state["chain"] == "ah" and at.metric[0].value == f"€{base_cost:.2f}", "back from realistic, the chain should stay"
foods = {f["key"]: f for f in A.P.FOODS.values()}
assert not [k for k in foods if not CAT.FOOD_CATS[k]], "every food needs a category"
by_name = lambda n: next(k for k, f in foods.items() if f["name"] == n)
for name, cat, want in [("Peanuts unsalted", "nuts", True), ("Chestnuts raw", "nuts", True), ("Oil peanut", "nuts", True),
                        ("Peanut butter light", "nuts", True), ("Coconut milk", "nuts", False),
                        ("Milk goats- full fat", "dairy", True), ("Butter unsalted", "dairy", True),
                        ("Drink soya wo sugar", "dairy", False), ("Drink oat wo sugar", "dairy", False),
                        ("Peanut butter", "dairy", False), ("Crackers cream", "dairy", False),
                        ("Oil sunflower seed", "seeds", False), ("Egg whole chicken av raw", "meat", False),
                        ("Lettuce lambs raw", "meat", False), ("Beans French raw", "legumes", False),
                        ("Tofu unprepared", "legumes", True), ("Flour wheat self-raising", "fruit", False),
                        ("Beef av raw", "eggs", False), ("Pork schnitzel breaded raw", "grain", True),
                        ("Pasta white raw", "eggs", False), ("Salad egg", "eggs", True)]:
    assert (cat in CAT.FOOD_CATS[by_name(name)]) == want, (name, cat, want)
assert {c[0] for c in CAT.CATEGORIES} >= {v for v in CAT.BY_NEVO_GROUP.values()}, "a category without a tick"
print("categories: every food has one, the borderline foods are right")

plain = A.pure(**KW, excluded=[], own=[])
# the search box adds a food, then the amount is changed
at.selectbox(key=f"own_pick_{at.session_state['own_v']}").set_value("milk_semi").run()
assert not at.exception and at.session_state["my_foods"] == [{"key": "milk_semi", "grams": 100.0, "how": "exactly", "per": "day"}]
at.session_state["my_foods"] = [{"key": "milk_semi", "grams": 500.0, "how": "exactly", "per": "day"}]
at.run()
check(at, "my foods: 500 g milk")
got = A.pure(**KW, excluded=[], own=[["milk_semi", 500.0, True]])
assert at.metric[0].value == f"€{got['cost']:.2f}" and at.metric[0].delta.startswith("+€"), (at.metric[0].value, at.metric[0].delta)
assert [e.label for e in at.expander if "What changed" in e.label] and any(f"Compared with the plan without your foods: €{plain['cost']:.2f}" in m.value for m in at.markdown)
assert abs(got["grams"]["milk_semi"] - 500) < 1e-6 and got["cost"] > plain["cost"]
assert abs(got["own_eur"] - 5 * next(float(r["eur_per_100g"]) for r in A.prices_of("milk_semi") if r["chain"] == "ah")) < 1e-9
rows_ = A.compare(got, plain, [["milk_semi", 500.0, True]])
assert rows_[0]["food"] == "Milk semi-skimmed" and rows_[0]["change"] == 500 and abs(sum(r["€/day change"] for r in rows_) - (got["cost"] - plain["cost"])) < 0.02
assert not [s for s in got["shares"] if s["food"] == "Milk semi-skimmed"], "your own food has no LP reason to explain"
assert json.loads(open(os.environ["NEVO_DIET_SETTINGS"]).read())["my_foods"], "my foods should be saved"
print(f"my foods: milk costs +€{got['cost'] - plain['cost']:.3f}/day, saved, compared")
# exactly and at least: the LP wants 99 g of peanuts
exact = A.pure(**KW, excluded=[], own=[["peanuts", 50.0, True]])["grams"]["peanuts"]
least = A.pure(**KW, excluded=[], own=[["peanuts", 50.0, False]])["grams"]["peanuts"]
assert abs(exact - 50) < 1e-6 and least > 60, (exact, least)
at.session_state["my_foods"] = [{"key": "peanuts", "grams": 350.0, "how": "at least", "per": "week"}]
at.run()
assert not at.exception and abs(A.own_spec(at.session_state["my_foods"])[0][1] - 50) < 1e-9 and not A.own_spec(at.session_state["my_foods"])[0][2]
print(f"exactly 50 g gives {exact:.0f} g, at least 50 g gives {least:.0f} g; a week's amount is divided by 7")
# impossible: what's in the way, and how much still works
at.session_state["my_foods"] = [{"key": "milk_semi", "grams": 3000.0, "how": "exactly", "per": "day"}]
at.run()
assert not at.exception and at.error and "calcium" in at.error[0].value and re.search(r"the most that still works is [\d,]+ g a day", at.error[0].value), [e.value for e in at.error]
print("impossible amount:", at.error[0].value.split("\n\n")[1].replace("\n", " "))
# a food the chain doesn't sell: cheapest other chain, marked
away = next(k for k in A.P.FOODS if not any(r["chain"] == "ah" for r in A.prices_of(k)))
at.session_state["my_foods"] = [{"key": away, "grams": 50.0, "how": "exactly", "per": "day"}]
at.run()
assert not at.exception and any(k == away and b["away"] for b in A.pure(**KW, excluded=[], own=[[away, 50.0, True]])["basket"] for k in [b["key"]])
print(f"not at ah: {A.label(away)} priced at another chain")
# the ticks: a checkbox on the Foods page, and My foods wins
at.session_state["my_foods"] = []
page("foods")
at.checkbox(key="nocat_nuts").check().run()
at.checkbox(key="nocat_dairy").check().run()
assert not at.exception and at.session_state["no_categories"] == [], "a tick waits for Apply"
at.checkbox(key="nocat_dairy").uncheck().run()
at.button(key="foods_apply_top").click().run()
assert not at.exception and at.session_state["no_categories"] == ["nuts"], at.session_state["no_categories"]
print("ticks: several clicks wait in the form, Apply takes them all")
got = A.pure(**KW, excluded=A.effective_excluded([], ["nuts"]), own=[])
assert not [b for b in got["basket"] if "nuts" in CAT.FOOD_CATS[b["key"]]] and got["cost"] > plain["cost"]
page("plan")
assert any("without your category ticks" in m.value for m in at.markdown)
page("foods")
at.checkbox(key="nocat_nuts").uncheck().run()
at.button(key="foods_apply_bottom").click().run()
assert at.session_state["no_categories"] == []
page("plan")
print(f"tick no nuts: €{got['cost']:.2f}/day, nothing with nuts in it")
# kinds: a whole kind of food out at once (all pasta, all rice ...), from the Plan page and from the Foods page
import kinds as K
assert set(K.KIND.values()) <= {r[0] for r in K.RULES} | {"supplements"}, "every food gets a kind from data/kinds.tsv"
assert {A.label(k) for k in K.members(["pasta and noodles"])} >= {"Pasta white raw", "Pasta wholemeal raw"}
assert K.KIND["n1139"] == "peas, beans and sweetcorn" and K.KIND["flour_wholemeal"] == "wheat flour"
at.multiselect(key=f"lo_kinds_plan_{at.session_state['editor_v']}").select("rice").run()
assert at.session_state["no_kinds"] == [], "a kind waits for Apply"
at.button(key="left_out_apply_plan").click().run()
assert not at.exception and at.session_state["no_kinds"] == ["rice"], at.session_state["no_kinds"]
norice = A.pure(**KW, excluded=sorted(K.members(["rice"])), own=[])
assert at.metric[0].value == f"€{norice['cost']:.2f}" and not [b for b in norice["basket"] if K.KIND.get(b["key"]) == "rice"]
page("foods")
at.multiselect(key=f"foods_kinds_{at.session_state['editor_v']}").select("pasta and noodles").run()
at.button(key="foods_apply_top").click().run()
assert not at.exception and at.session_state["no_kinds"] == ["pasta and noodles", "rice"], at.session_state["no_kinds"]
assert K.members(["pasta and noodles"]) <= set(at.session_state["_ctx"].ex) and "pasta" not in at.session_state["excluded"]
page("plan")
at.multiselect(key=f"lo_kinds_plan_{at.session_state['editor_v']}").unselect("rice").unselect("pasta and noodles").run()
at.button(key="left_out_apply_plan").click().run()
assert at.session_state["no_kinds"] == [] and at.metric[0].value == f"€{plain['cost']:.2f}"
print(f"kinds: no rice €{norice['cost']:.2f}/day; out and back from the Plan and Foods pages")
# limits on foods and kinds: none by default, set from the Plan page
import numpy as np
import lp
import meals as M
assert A.DEFAULTS["food_limits"] == [] and not [r for r in plain["reqs"] if r["kind"] == "food"], "no limits by default"
assert np.isinf(A.model("avg_man", "ah", True).cap).all(), "no food has a cap of its own, the vitamin D tablet neither"
assert "kcal_30" not in M.RULES, "the 30%-of-energy rule is gone"
at.selectbox(key=f"limit_pick_{at.session_state['food_limits_v']}").set_value("kind:wheat flour").run()
assert not at.exception and at.session_state["food_limits"] == [{"key": "kind:wheat flour", "grams": 100.0, "per": "day"}]
at.session_state["food_limits"] = [{"key": "kind:wheat flour", "grams": 50.0, "per": "day"},
                                   {"key": "peanuts", "grams": 350.0, "per": "week"}]
at.run()
check(at, "limits: flour 50 g/day, peanuts 350 g/week")
spec = A.limit_spec(at.session_state["food_limits"])
assert spec == [["limit: Peanuts unsalted", ["peanuts"], 50.0], ["limit: wheat flour (kind)", sorted(K.members(["wheat flour"])), 50.0]]
lim = A.pure(**KW, excluded=[], own=[], limits=spec)
flour = sum(g for k, g in lim["grams"].items() if K.KIND.get(k) == "wheat flour")
assert at.metric[0].value == f"€{lim['cost']:.2f}" and lim["cost"] > plain["cost"] and flour <= 50 + 1e-6
assert lim["grams"].get("peanuts", 0) <= 50 + 1e-6 and "limit: wheat flour (kind)" in lim["binding"]
assert any(b["at_limit"] for b in lim["basket"] if K.KIND.get(b["key"]) == "wheat flour")
assert any("limit: wheat flour (kind)" in s.value for s in at.success), "the nutrient check names the limit that sets the price"
json_limits = json.loads(open(os.environ["NEVO_DIET_SETTINGS"]).read())["food_limits"]
assert json_limits == at.session_state["food_limits"], "limits are saved"
page("why")
page("nutrients")
page("plan")
# a limit below what My foods asks for: no plan, and the message names the limit
at.session_state["my_foods"] = [{"key": "peanuts", "grams": 100.0, "how": "at least", "per": "day"}]
at.run()
assert at.error and "limit: Peanuts unsalted" in at.error[0].value and "the most that still works is 50 g a day" in at.error[0].value, \
    [e.value for e in at.error]
at.session_state["my_foods"] = []
# 0 g of a kind: none of it
nopasta = A.pure(**KW, excluded=[], own=[], limits=A.limit_spec([{"key": "kind:pasta and noodles", "grams": 0.0, "per": "day"}]))
assert nopasta["ok"] and not [k for k in nopasta["grams"] if K.KIND.get(k) == "pasta and noodles"]
at.session_state["food_limits"] = []
at.run()
assert at.metric[0].value == f"€{plain['cost']:.2f}"
print(f"limits: €{plain['cost']:.2f} -> €{lim['cost']:.2f}/day with flour <= 50 g and peanuts <= 350 g a week; "
      "a clash with My foods names the limit")
own = [["oats", 100.0, True]]
ex_ = A.effective_excluded([], ["grain"], own)
assert "oats" not in ex_ and "pasta" in ex_
got = A.pure(**KW, excluded=ex_, own=own)
assert [b["key"] for b in got["basket"] if "grain" in CAT.FOOD_CATS.get(b["key"], ())] == ["oats"]
at.session_state["no_categories"] = ["grain"]
at.session_state["my_foods"] = [{"key": "oats", "grams": 100.0, "how": "exactly", "per": "day"}]
at.run()
check(at, "no grain, but 100 g oats")
assert at.toggle(key="compare_ticks") is not None
at.toggle(key="compare_ticks").set_value(True).run()
assert not at.exception and any("your foods and category ticks" in m.value for m in at.markdown)
at.session_state["compare_ticks"] = False
for cat in CAT.CATEGORIES:                          # every tick renders, feasible or not
    at.session_state["my_foods"], at.session_state["no_categories"] = [], [cat[0]]
    at.run()
    assert not at.exception, cat
print("all ticks render")
# vegan: refused, and the reason is the EPA+DHA minimum
at.session_state["no_categories"] = ["meat", "fish", "eggs", "dairy"]
at.run()
assert at.error and "EPA+DHA" in at.error[0].value, [e.value for e in at.error]
print("vegan:", at.error[0].value.split("\n\n")[1])

# the realistic week
def solve_it():
    at.run()
    for b in at.button:
        if b.label.startswith("Solve"):
            b.click().run()
    assert not at.exception


REAL = dict(profile="avg_man", chain="ah", cooked=True, excluded=[], strictness="medium", pattern="brunch", batch=True)
at.session_state["mode"], at.session_state["no_categories"] = "realistic", []
at.session_state["my_foods"] = [{"key": "milk_semi", "grams": 500.0, "how": "exactly", "per": "day"}]
solve_it()
check(at, "realistic: 500 g milk")
assert [e.label for e in at.expander if "What changed" in e.label] and at.metric[0].delta.startswith("+€")
real0 = A.realistic(**REAL, no_cats=[], own=[])
real1 = A.realistic(**REAL, no_cats=[], own=[["milk_semi", 500.0, True]])
assert real1["ok"] and real1["cost"] > real0["cost"] and any(d["food"] == "Milk semi-skimmed ★" and d["amount"] == "500 g" for d in real1["direct"])
assert any(s["food"] == "Milk semi-skimmed" for s in real1["shop"]) and A.compare(real1, real0, [["milk_semi", 500.0, True]])[0]["food"] == "Milk semi-skimmed"
print(f"realistic: €{real0['cost']:.2f} -> €{real1['cost']:.2f}, milk on the shopping list as {next(s['buy'] for s in real1['shop'] if s['food'] == 'Milk semi-skimmed')}")
at.session_state["my_foods"] = [{"key": "milk_semi", "grams": 500.0, "how": "at least", "per": "day"}]
solve_it()
real2 = A.realistic(**REAL, no_cats=[], own=[["milk_semi", 500.0, False]])
assert next(float(d["amount"].split()[0]) for d in real2["direct"] if d["food"] == "Milk semi-skimmed ★") >= 500
# a food the week wouldn't eat as such, and one the chain doesn't sell
at.session_state["my_foods"] = [{"key": away, "grams": 50.0, "how": "exactly", "per": "day"}]
solve_it()
check(at, f"realistic: {A.label(away)[:20]} from elsewhere")
assert any("⚠" in s["product"] for s in A.realistic(**REAL, no_cats=[], own=[[away, 50.0, True]])["shop"])
at.session_state["my_foods"] = []
# ticks: a dinner with the ingredient goes; a cooking basic stays in dinners but isn't eaten as such
at.session_state["no_categories"] = ["grain"]
solve_it()
check(at, "realistic: no grain products")
nog = A.realistic(**REAL, no_cats=["grain"], own=[])
assert nog["ok"] and nog["n_dishes"] < real0["n_dishes"] and not [g for g in nog["grams"] if "grain" in CAT.FOOD_CATS.get(g, ())]
at.session_state["no_categories"] = ["fats"]
solve_it()
check(at, "realistic: no fats and oils")
nof = A.realistic(**REAL, no_cats=["fats"], own=[])
assert nof["ok"] and nof["n_dishes"] == real0["n_dishes"], "dinners keep their spoon of oil"
assert not [d for d in nof["direct"] if d["group"] == "fat"], "but no fat eaten as such"
norice_wk = A.realistic(**{**REAL, "excluded": sorted(K.members(["rice"]))}, no_cats=[], own=[])
assert norice_wk["ok"] and not [g for g in norice_wk["grams"] if K.KIND.get(g) == "rice"], "no rice, in dinners neither"
print(f"realistic, no rice (kind): €{norice_wk['cost']:.2f}/day, {len(norice_wk['dinners'])} dinners")
# a limit counts what dinners use as well: potatoes at most 300 g a week, hutspot and stamppot included
at.session_state["food_limits"] = [{"key": "kind:potatoes", "grams": 300.0, "per": "week"}]
at.session_state["no_categories"] = []
solve_it()
check(at, "realistic: potatoes <= 300 g a week")
pot_wk = A.realistic(**REAL, no_cats=[], own=[], limits=A.limit_spec(at.session_state["food_limits"]))
pot_g = sum(g for k, g in pot_wk["grams"].items() if K.KIND.get(k) == "potatoes")
pot_row = next(r for r in pot_wk["reqs"] if r["kind"] == "food")
assert pot_wk["ok"] and pot_g <= 300 / 7 + 1e-3 and abs(pot_row["intake"] - pot_g) < 1e-3, (pot_g, pot_row)
at.session_state["food_limits"] = []
# without the old meal rules any food sold at >= 3 chains may be eaten as such, in any amount; flour too
_ah = lp.load(chain="ah")
assert M.direct_ok(_ah, _ah.keys.index("flour_wholemeal"))
print(f"realistic, potatoes <= 300 g a week: €{pot_wk['cost']:.2f}/day, {pot_g:.0f} g a day bought, dinners included")
# impossible week
at.session_state["no_categories"] = []
at.session_state["my_foods"] = [{"key": "milk_semi", "grams": 3000.0, "how": "exactly", "per": "day"}]
solve_it()
assert at.error and "calcium" in at.error[0].value and "most that still works" in at.error[0].value, [e.value for e in at.error]
print("impossible week:", at.error[0].value.split("\n\n")[1].replace("\n", " "))
at.session_state["my_foods"] = []
# ---------------- the "cheapest chain" option ----------------
at.session_state["mode"], at.session_state["chain"], at.session_state["no_categories"] = "pure", "cheapest", []
at.run()
check(at, "pure, cheapest chain")
pure_at = {ch: A.pure(profile="avg_man", chain=ch, cooked=True, excluded=[], min3=False, own=[]) for ch in A.chains()}
pure_best = min((ch for ch in pure_at if pure_at[ch]["ok"]), key=lambda ch: pure_at[ch]["cost"])
assert at.metric[0].value == f"€{pure_at[pure_best]['cost']:.2f}", (at.metric[0].value, pure_best)
assert at.session_state["chain"] == "cheapest" and any(A.CHAIN_NAMES[pure_best] in c_.value for c_ in at.caption)
assert any(e.label == "Every chain compared" for e in at.expander)
print(f"pure: cheapest chain is {pure_best}")
at.session_state["mode"] = "realistic"
at.run()
WEEK = {**{k: v for k, v in REAL.items() if k != "chain"}, "food_cost": 0.0}
assert not at.exception
if not A.week_prices.is_cached(**WEEK, no_cats=[], own=[]):       # with an earlier run in the cache there's no wait
    assert not [m for m in at.metric if m.label == "€ per day"], "no week before Solve: the pure LP's pick is only a stand-in"
    assert any("Press **Solve** to compare" in c_.value for c_ in at.caption)
solve_it()
check(at, "realistic, cheapest chain")
weeks = {ch: A.realistic(**WEEK, chain=ch, no_cats=[], own=[]) for ch in A.chains()}
week_best = min((ch for ch in weeks if weeks[ch]["ok"]), key=lambda ch: weeks[ch]["cost"])
assert A.week_prices(**WEEK, no_cats=[], own=[])["best"] == week_best
assert at.metric[0].value == f"€{weeks[week_best]['cost']:.2f}", (at.metric[0].value, week_best)
print(f"realistic: cheapest chain is {week_best}: " + ", ".join(f"{ch} {w['cost']:.2f}" for ch, w in weeks.items() if w["ok"]))
at.session_state["mode"] = "pure"
at.run()
assert at.session_state["chain"] == "cheapest", "the option exists in both modes, so it should stay"
at.session_state["kcal"], at.session_state["protein"] = 800.0, 500.0
at.run()
assert not at.exception and at.error and any("No chain has a plan" in c_.value for c_ in at.caption)
print("no chain has a plan: said so")
at.session_state["kcal"], at.session_state["protein"] = None, None
# ---------------- the cost per food ----------------
DEKA = dict(profile="avg_man", chain="dekamarkt", cooked=True, excluded=[], min3=False, own=[])
bare, few = A.pure(**DEKA), A.pure(**DEKA, food_cost=0.02)
assert "kale_frozen" in bare["grams"] and bare["grams"]["kale_frozen"] < 2 and "kale_frozen" not in few["grams"], "the 1 g of kale"
assert len(few["basket"]) < len(bare["basket"]) and bare["cost"] < few["cost"] < bare["cost"] + 0.02 * (len(bare["basket"]) - len(few["basket"]))
assert abs(sum(few["eur"].values()) - few["cost"]) < 1e-9, "the price is the food, without the cost per food"
assert few["bare"] == {"cost": bare["cost"], "n": len(bare["basket"])}
assert all(r["ok"] for r in few["reqs"]), "still adequate"
assert A.pure(**{**DEKA, "own": [["kale_frozen", 1.0, True]]}, food_cost=0.02)["grams"]["kale_frozen"] == 1.0, "your own foods are free"
print(f"cost per food: {len(bare['basket'])} foods €{bare['cost']:.3f} -> {len(few['basket'])} foods €{few['cost']:.3f}, kale gone")
at.session_state["kcal"], at.session_state["protein"] = None, None
at.session_state["mode"], at.session_state["chain"], at.session_state["food_cost"] = "pure", "dekamarkt", 0.02
at.run()
check(at, "pure, cost per food 0.02")
assert at.metric[0].value == f"€{few['cost']:.2f}" and at.metric[3].value == str(len(few["basket"]))
at.session_state["chain"] = "cheapest"
at.run()
_rank = A.chain_prices(profile="avg_man", cooked=True, excluded=[], min3=False, own=[], food_cost=0.02)
assert at.metric[0].value == f"€{_rank['rows'][0]['cost']:.2f}"
WEEK0 = dict(profile="avg_man", chain="ah", cooked=True, excluded=[], strictness="medium", pattern="brunch", batch=True, no_cats=[], own=[])
w0, w1 = A.realistic(**WEEK0), A.realistic(**WEEK0, food_cost=0.02)
assert w1["ok"] and len(w1["direct"]) < len(w0["direct"]), "fewer foods eaten as such"
assert abs(sum(s["eur_week"] for s in w1["shop"]) / 7 - w1["cost"]) < 0.05, "the week's price is the shopping list, without the cost per food"
print(f"realistic: {len(w0['direct'])} foods as such €{w0['cost']:.2f} -> {len(w1['direct'])} foods €{w1['cost']:.2f}; smallest now " + min((d for d in w1["direct"] if d["g_day"]), key=lambda d: d["g_day"])["amount"])
# ---------------- allergies ----------------
at.session_state["food_cost"], at.session_state["chain"], at.session_state["mode"] = 0.0, "ah", "pure"
name_of = lambda k: A.label(k)
key_of = {f["name"]: k for k, f in foods.items()}
for tick, out_, in_ in [
        ("x_gluten", ["Oat flakes", "Wheat bread brown", "Pasta white raw", "Liver sausage", "Bread crumbs"], ["Rice white raw", "Potatoes raw", "Pasta gluten free raw"]),
        ("x_lactose", ["Milk semi-skimmed", "Butter unsalted", "Cheese Gouda 48+ av"], ["Milk semi-skimmed lactose free", "Drink soya wo sugar", "Drink oat wo sugar"]),
        ("x_milk", ["Milk semi-skimmed lactose free", "Butter unsalted", "Spread chocolate dark"], ["Drink soya wo sugar", "Oil olive"]),
        ("x_egg", ["Egg whole chicken av raw", "Salad egg"], ["Rice white raw"]),
        ("x_fish", ["Cod raw", "Salad tuna"], ["Mussels raw"]),
        ("x_shellfish", ["Mussels raw", "Salad shrimp"], ["Cod raw"]),
        ("x_peanut", ["Peanuts unsalted", "Oil peanut", "Peanut butter", "Hummus natural"], ["Rice white raw"]),
        ("x_nuts", ["Almonds blanched unsalted", "Walnuts unsalted"], ["Coconut milk", "Cranberries fresh"]),
        ("x_soy", ["Drink soya wo sugar", "Tofu unprepared", "Low fat margarine Blue Band"], ["Drink oat wo sugar", "Rice white raw"]),
        ("x_sesame", ["Sesame seeds wo hull", "Oil sesame", "Hummus natural", "Wheat bread brown"], ["Rice white raw"])]:
    have = CAT.members([tick])
    for n in out_:
        assert key_of[n] in have, (tick, n, "should be out")
    for n in in_:
        assert key_of[n] not in have, (tick, n, "should stay")
    at.session_state["no_categories"] = [tick]
    at.run()
    assert not at.exception, tick
    assert any("Leaving out" in w.value for w in at.warning), "the Plan tab should say it's no guarantee"
    got = A.pure(profile="avg_man", chain="ah", cooked=True, excluded=A.effective_excluded([], [tick]), min3=False, own=[])
    assert not [b for b in got["basket"] if b["key"] in have], tick
    print(f"no {CAT.LABEL[tick]:10} {len(have):4} foods out, " + (f"€{got['cost']:.2f}/day" if got["ok"] else "no plan: " + ", ".join(m["nutrient"] for m in got["why"]["misses"])))
for tick in ("x_gluten", "x_milk", "x_peanut"):         # a real week: no dinner and nothing on the list has it
    wk = A.realistic(**REAL, no_cats=[tick], own=[])
    assert wk["ok"], tick
    assert not [g for g in wk["grams"] if g in CAT.members([tick])], tick
    codes = [d["nevo_dish"].split("NEVO ")[1].rstrip(")") for d in wk["dinners"]]
    assert not [c_ for c_ in codes if tick in CAT.of_code(c_)], tick
    print(f"realistic, no {CAT.LABEL[tick]}: €{wk['cost']:.2f}/day, {wk['n_dishes']} dinners to choose from")
# your own food against your allergy tick: it stays, and the app says so
at.session_state["no_categories"], at.session_state["my_foods"] = ["x_gluten"], [{"key": "oats", "grams": 50.0, "how": "exactly", "per": "day"}]
at.run()
assert not at.exception and any("may go against your allergy ticks" in e.value and "Oat flakes" in e.value for e in at.error)
at.session_state["my_foods"], at.session_state["no_categories"] = [], []
# ---------------- exclude everything, put it back, reset ----------------
page("foods")
next(b for b in at.button if b.label == "Exclude all foods").click().run()
assert not at.exception and set(at.session_state["excluded"]) >= set(foods), "every food out"
page("plan")
assert any("Every food is excluded" in i.value for i in at.info), "says so, no crash"
every_page("every food excluded")
for ch, mode in (("cheapest", "pure"), ("all", "pure"), ("ah", "realistic"), ("cheapest", "realistic")):
    at.session_state["chain"], at.session_state["mode"] = ch, mode
    solve_it()
    assert not at.exception, (ch, mode, at.exception)
at.session_state["chain"], at.session_state["mode"] = "ah", "pure"
at.session_state["excluded"] = [k for k in at.session_state["excluded"] if k not in ("oats", "milk_semi", "peanuts")]
at.run()
assert not at.exception and at.error, "three foods aren't a diet, and that's said without a crash"
every_page("three foods left")
at.session_state["food_q"] = "milk"
page("foods")
assert next(b for b in at.button if b.label == "Put back all foods shown")
next(b for b in at.button if b.label == "Put back all foods shown").click().run()
assert not at.exception and "milk_skimmed" not in at.session_state["excluded"] and "oats" not in at.session_state["excluded"] and len(at.session_state["excluded"]) > 100
at.session_state["food_q"] = ""
at.run()
next(b for b in at.button if b.label == "Put back all foods").click().run()
page("plan")
assert not at.exception and at.session_state["excluded"] == [] and at.metric[0].value == f"€{base_cost:.2f}"
print("exclude all, put back what's shown, put back all: fine")
# fruit per day: whole fruit only, in both modes (left at 200 g, so the reset below has to put it back to 0)
_m = A.model("avg_man", "ah", True)
_whole = {A.label(k) for k, v in zip(_m.keys, _m.N["FRUIT"]) if v}
assert "Banana" in _whole and not _whole & {"Apple sauce tinned", "Lemon", "Prunes", "Olives ripe in brine tinned/glass"}
at.session_state["chain"], at.session_state["mode"], at.session_state["fruit"] = "ah", "pure", 200.0
at.run()
check(at, "pure, 200 g fruit")
_fp = A.pure(profile=A.person("avg_man", fruit=200.0), chain="ah", cooked=True, excluded=[], min3=False)
_g = sum(b["g_day"] for b in _fp["basket"] if b["food"] in _whole)
assert _g >= 200 - 1e-3 and _fp["cost"] > base_cost, (_g, _fp["cost"])
at.session_state["mode"] = "realistic"
solve_it()
check(at, "realistic, 200 g fruit")
every_page("realistic, 200 g fruit")
_fw = A.realistic(**{**REAL, "profile": A.person("avg_man", fruit=200.0)}, no_cats=[], own=[])
_gw = sum(d["g_day"] for d in _fw["direct"] if d["food"].rstrip(" ★") in _whole)
assert _gw >= 200 - 1e-3, _gw
print(f"fruit: pure €{base_cost:.2f} -> €{_fp['cost']:.2f} ({_g:.0f} g), realistic {_gw:.0f} g whole fruit a day")
# ---------------- cooking: per-food ticks ----------------
import lp
_m = lp.load(chain="ah")
_i = _m.keys.index("n1139")                             # Peas and carrots frozen unprepared: 10 mg vitamin C raw
assert "n1139" in _m.cooked and abs(_m.N["VITC"][_i] - 10 * 0.80) < 1e-9, _m.N["VITC"][_i]   # USDA 3789: 80% kept
_r = lp.load(chain="ah", flip={"n1139"})
assert "n1139" not in _r.cooked and abs(_r.N["VITC"][_r.keys.index("n1139")] - 10) < 1e-9
assert _r.N["PROT"][_r.keys.index("n1139")] == _m.N["PROT"][_i], "no USDA factor for protein: kept at 100%"
assert not lp.load(chain="ah", cooked=False).cooked
_b = _m.keys.index("n564")                              # Brussels sprouts: NEVO's own boiled entry
assert abs(_m.N["VITC"][_b] - 132) < 1e-9 and _m.how["n564"].default == "usual"
assert not _m.how["milk_semi"].cookable and _m.how["n2734"].default == "raw" and "n2734" not in _m.cooked
assert A.raw_but_must(["n1139", "n2734", "milk_semi"]) == ["n1139"]
at.session_state["cook_flip"] = ["n1139"]
at.run()
assert not at.exception and any("meant to be cooked" in e.value and "Peas and carrots" in e.value for e in at.error)
page("settings")
next(b for b in at.button if b.label.startswith("Reset the cook ticks")).click().run()
page("plan")
assert not at.exception and at.session_state["cook_flip"] == [] and not any("meant to be cooked" in e.value for e in at.error)
print(f"cooking: peas and carrots {_r.N['VITC'][_r.keys.index('n1139')]:.0f} -> {_m.N['VITC'][_i]:.0f} mg vitamin C per 100 g; "
      "warning and reset work")
# ---------------- supplements ----------------
import supplements as S
_s = {k: S.counted(k)[0] for k in S.SUPP}
assert abs(_s["b12_1000"]["VITB12"] - 22.4) < 1e-9 and abs(_s["b12_100"]["VITB12"] - 4.4) < 1e-9, "B12 by dose"
assert abs(_s["folic_400"]["FOL"] - 680) < 1e-9 and _s["folic_400"]["FOLAC"] == 400, "folic acid x1.7 as folate"
assert abs(_s["multi_plus_az"]["VITE"] - 12 * 0.45 / 0.67) < 1e-9 and _s["fish_oil"]["VITE"] == 15, "synthetic vitamin E"
assert _s["multi_plus_az"]["MG_SUPP"] == _s["multi_plus_az"]["MG"] == 125 and _s["multi_plus_az"]["RETOL"] == 800
assert all(S.offers(k) for k in S.SUPP), "every supplement has a priced product"
assert all(S.SUPP[k]["label"] and S.SUPP[k]["label_date"] for k in S.SUPP), "every label has a source and date"
_d = lp.load(chain="ah")
assert [k for k in _d.keys if k in S.SUPP] == ["vitD_tablet"] and abs(_d.c[_d.keys.index("vitD_tablet")] - 4.99 / 300) < 1e-12, \
    "by default only the vitamin D tablet, at its old price"
_rd, _ra = lp.solve(_d)[0], lp.solve(_all := lp.load(chain="ah", pills=S.spec("priced")))[0]
assert _ra.status == 0 and _ra.fun <= _rd.fun + 1e-9, "more supplements can only make the plan cheaper"
assert any(r["name"] == "magnesium_pills" for r in _all.reqs) and _all.N["MG_SUPP"] @ _ra.x <= 250 + 1e-6
_e = lp.load(chain="jumbo", pills=S.spec("ticked", [], False, {}, [["b12_1000", 1 / 7]]))
_i = _e.keys.index("b12_1000")
assert _e.lb[_i] == _e.cap[_i] == 1 / 7 and _e.pills["b12_1000"]["free"] and _e.c[_i] == 0, "exact, and free off-chain"
assert abs(lp.solve(_e)[0].x[_i] - 1 / 7) < 1e-9
assert all(abs(7 * n - round(7 * n)) < 1e-6 for n in _fw["units"].values()) and _fw["units"], \
    "the realistic week takes supplements in whole units a week"
at.session_state["mode"], at.session_state["fruit"], at.session_state["chain"] = "pure", 0.0, "ah"   # the fruit test left realistic
for _mode in ("ticked", "priced", "all"):
    at.session_state["pill_mode"] = _mode
    page("supplements")
    page("plan")
    check(at, f"supplements: {_mode}")
at.session_state["pill_mode"], at.session_state["pill_anywhere"] = "ticked", False
at.session_state["pills_on"], at.session_state["chain"] = ["vitD_tablet", "b12_1000"], "jumbo"
page("plan")
assert any("free supplement" in w.value for w in at.warning), "a free supplement in the plan gets a warning"
at.session_state["pill_prices"] = {"vitD_tablet": 0.02, "b12_1000": 0.05, "iron_14": 0.04}   # iron: drugstore only
at.session_state["pill_exact"] = [{"key": "iron_14", "n": 1.0, "per": "week"}]
page("supplements")
page("plan")
assert not any("free supplement" in w.value for w in at.warning), "your prices replace the missing ones"
assert abs(at.session_state["_ctx"].pure["units"]["iron_14"] - 1 / 7) < 1e-9, "an exact amount a week"
at.session_state["pill_prices"], at.session_state["pill_exact"], at.session_state["chain"] = {}, [], "ah"
at.session_state["pills_on"], at.session_state["pill_anywhere"] = list(S.DEFAULT_ON), True
page("plan")
print(f"supplements: default €{_rd.fun:.2f} -> €{_ra.fun:.2f} with every priced one; modes, exact, free warning, your prices")
at.session_state["my_foods"], at.session_state["no_categories"], at.session_state["excluded"] = [{"key": "oats", "grams": 50.0, "how": "exactly", "per": "day"}], ["x_soy"], ["rice"]
at.session_state["mode"], at.session_state["budget"], at.session_state["kcal"] = "pure", 7.0, 2500.0
at.session_state["food_limits"] = [{"key": "kind:rice", "grams": 50.0, "per": "day"}]
page("settings")
next(b for b in at.button if b.label == "Reset everything").click().run()
next(b for b in at.button if b.label == "Yes, reset everything").click().run()
assert not at.exception
for k_, v_ in A.DEFAULTS.items():
    assert at.session_state[k_] == v_, (k_, at.session_state[k_], v_)
assert json.loads(open(os.environ["NEVO_DIET_SETTINGS"]).read())["my_foods"] == []
assert "Test Person" not in str(A.DEFAULTS)
print("reset everything: back to the defaults")
print("all good")
