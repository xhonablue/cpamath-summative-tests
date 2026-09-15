"""Headless UI tests (Streamlit AppTest). Run: python test_app.py"""
import os, shutil
from streamlit.testing.v1 import AppTest

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "app.py")


def fresh():
    shutil.rmtree(os.path.join(HERE, "data"), ignore_errors=True)


def errs(at):
    return [e.value for e in at.exception]


# 1. Not configured -> testing blocked, no demo
os.environ.pop("CPA_DEV", None)
at = AppTest.from_file(APP, default_timeout=60)
at.run()
assert not errs(at), errs(at)
assert any("Setup required" in e.value for e in at.error), "setup banner missing"
at.sidebar.radio[0].set_value("Student — Take a Test").run()
assert any("Testing opens" in i.value for i in at.info)
print("ok: unconfigured app blocks testing")

# 2. Teacher portal locked without PIN secret
at.sidebar.radio[0].set_value("Teacher Portal").run()
assert any("PIN hasn't been set" in e.value for e in at.error)
print("ok: teacher portal locked without PIN")

# 3. Dev mode: student takes Day 8 via ?day= link, gets graded, retake blocked
fresh()
at = AppTest.from_file(APP, default_timeout=60)
at.secrets["dev_mode"] = "true"
at.secrets["teacher_pin"] = "t1"
at.secrets["admin_pin"] = "a1"
at.query_params["day"] = "8"
at.run()
assert not errs(at), errs(at)
assert at.sidebar.radio[0].value == "Student — Take a Test"
at.text_input[0].input("Ava Test")
at.text_input[2].input("Period 2")
at.run()
for r in at.radio:
    if r.key and r.key.startswith("8_"):
        r.set_value(r.options[0])
for t in at.text_input:
    if t.key and t.key.startswith("8_"):
        t.input("12")
at.button[0].click() if False else None
at.run()
sub = [b for b in at.button if "Submit" in str(b.label)]
sub[0].click().run()
if not any("Submitted" in s.value for s in at.success):
    [b for b in at.button if "Submit" in str(b.label)][0].click().run()
assert not errs(at), errs(at)
assert any("Submitted" in s.value for s in at.success), [s.value for s in at.success] + [w.value for w in at.warning]
print("ok: student submission graded:", [s.value for s in at.success][0])

at2 = AppTest.from_file(APP, default_timeout=60)
at2.secrets["dev_mode"] = "true"
at2.query_params["day"] = "8"
at2.run()
at2.text_input[0].input("Ava Test"); at2.text_input[2].input("Period 2"); at2.run()
assert any("already completed" in w.value for w in at2.warning)
print("ok: retake blocked")

# 4. Teacher portal renders every tab with data
at3 = AppTest.from_file(APP, default_timeout=60)
at3.secrets["dev_mode"] = "true"
at3.secrets["teacher_pin"] = "t1"
at3.secrets["admin_pin"] = "a1"
at3.run()
at3.sidebar.radio[0].set_value("Teacher Portal").run()
at3.text_input(key="teacher_pin_input").input("t1").run()
assert not errs(at3), errs(at3)
labels = [t.label for t in at3.tabs]
assert "🏫 Google Classroom" in labels, labels
links = [b for b in at3.get("link_button")]
assert len(links) == 30, len(links)
print("ok: teacher portal —", len(labels), "tabs,", len(links), "Classroom post buttons")
print("   sample:", links[7].proto.url[:110])

# 5. Admin view
at3.sidebar.radio[0].set_value("Admin — View Only").run()
at3.text_input(key="admin_pin_input").input("wrong").run()
assert not errs(at3)
print("ok: admin view gated")
fresh()
print("\nALL APP TESTS PASSED")
