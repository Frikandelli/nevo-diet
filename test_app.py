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
print("all good")
