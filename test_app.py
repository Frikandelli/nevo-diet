"""Smoke test of the app: every tab (charts included) renders without errors in several settings.
nix-shell --run 'python3 test_app.py'   (uses a temporary settings file; the cache is the normal one)"""
import json
import os
import tempfile

from streamlit.testing.v1 import AppTest

_tmp = tempfile.mkdtemp()
os.environ["NEVO_DIET_SETTINGS"] = os.path.join(_tmp, "settings.json")
os.environ["NEVO_DIET_PROFILES"] = os.path.join(_tmp, "profiles.json")


def check(at, what):
    assert not at.exception, (what, at.exception)
    print(f"{what:38} " + " | ".join(str(m.value) for m in at.metric[:4]))


at = AppTest.from_file("app.py", default_timeout=300).run()
check(at, "pure, average man, ah")
import appcore as A
_r = A.pure(profile="avg_man", chain="ah", cooked=True, excluded=[], min3=False)
_intake = {x["nutrient"]: x["intake"] for x in _r["reqs"]}
for n in {x["nutrient"] for x in _r["by_food"]}:
    got = sum(x["amount"] for x in _r["by_food"] if x["nutrient"] == n)
    assert abs(got - _intake[n]) < 1e-6 * max(1, _intake[n]), (n, got, _intake[n])
print("food coverage adds up to each nutrient's intake")
for k, v in [("chain", "all"), ("cooked", False), ("profile", "avg_woman"), ("min3", True)]:
    at.session_state[k] = v
    at.run()
    check(at, f"pure, {k}={v}")
at.session_state["profile"], at.session_state["chain"], at.session_state["cooked"] = "avg_man", "ah", True
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
_milk = A.pure(**KW, excluded=[], own=[["milk_semi", 500.0, True]])["cost"]
assert at.metric[0].value == f"€{_milk:.2f}" and at.metric[0].delta == f"+€{_milk - plain['cost']:.2f}", (at.metric[0].value, at.metric[0].delta)
assert [e.label for e in at.expander if "What changed" in e.label] and any(f"Compared with the plan without your foods: €{base_cost:.2f}" in m.value for m in at.markdown)
got = A.pure(**KW, excluded=[], own=[["milk_semi", 500.0, True]])
assert abs(got["grams"]["milk_semi"] - 500) < 1e-6 and got["cost"] > plain["cost"]
assert abs(got["own_eur"] - 5 * next(float(r["eur_per_100g"]) for r in A.prices_of("milk_semi") if r["chain"] == "ah")) < 1e-9
rows_ = A.compare(got, plain, [["milk_semi", 500.0, True]])
assert rows_[0]["food"] == "Milk semi-skimmed" and rows_[0]["change"] == 500 and abs(sum(r["€/day change"] for r in rows_) - (got["cost"] - plain["cost"])) < 0.02
assert not [s for s in got["shares"] if s["food"] == "Milk semi-skimmed"], "your own food has no LP reason to explain"
assert json.loads(open(os.environ["NEVO_DIET_SETTINGS"]).read())["my_foods"], "my foods should be saved"
print(f"my foods: milk costs +€{got['cost'] - plain['cost']:.3f}/day, saved, compared")
# exactly and at least: the LP wants more peanuts than 50 g
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
assert not at.exception and at.error and "calcium" in at.error[0].value and "most that still works" in at.error[0].value, [e.value for e in at.error]
print("impossible amount:", at.error[0].value.split("\n\n")[1].replace("\n", " "))
# a food the chain doesn't sell: cheapest other chain, marked
away = next(k for k in A.P.FOODS if not any(r["chain"] == "ah" for r in A.prices_of(k)))
at.session_state["my_foods"] = [{"key": away, "grams": 50.0, "how": "exactly", "per": "day"}]
at.run()
assert not at.exception and any(k == away and b["away"] for b in A.pure(**KW, excluded=[], own=[[away, 50.0, True]])["basket"] for k in [b["key"]])
print(f"not at ah: {A.label(away)} priced at another chain")
# the ticks: a checkbox on the Foods tab, and My foods wins
at.session_state["my_foods"] = []
at.run()
at.checkbox(key="nocat_nuts").check().run()
assert not at.exception and at.session_state["no_categories"] == ["nuts"]
got = A.pure(**KW, excluded=A.effective_excluded([], ["nuts"]), own=[])
assert not [b for b in got["basket"] if "nuts" in CAT.FOOD_CATS[b["key"]]] and got["cost"] > plain["cost"]
assert any("without your category ticks" in m.value for m in at.markdown)
at.checkbox(key="nocat_nuts").uncheck().run()
assert at.session_state["no_categories"] == []
print(f"tick no nuts: €{got['cost']:.2f}/day, nothing with nuts in it")
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
assert at.session_state["chain"] == "cheapest" and any(pure_best in c_.value for c_ in at.caption)
assert any(e.label == "Every chain compared" for e in at.expander)
print(f"pure: cheapest chain is {pure_best}")
at.session_state["mode"] = "realistic"
at.run()
assert not at.exception and not [m for m in at.metric if m.label == "€ per day"], "no week before Solve: the pure LP's pick is only a stand-in"
assert any("Press **Solve** to compare" in c_.value for c_ in at.caption)
solve_it()
check(at, "realistic, cheapest chain")
WEEK = {k: v for k, v in REAL.items() if k != "chain"}
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
print("all good")
