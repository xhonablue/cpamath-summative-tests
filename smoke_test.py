"""Exercises grading, storage, and chart generation with synthetic data,
without needing a running Streamlit server. Run before shipping."""
import sys, os, random
sys.path.insert(0, os.path.dirname(__file__))

from content.loader import load_all_days
from grading import grade_session
from storage import LocalCSVStorage, SessionRecord
import charts
import pandas as pd

random.seed(42)
ALL_DAYS = load_all_days()
assert len(ALL_DAYS) == 30, f"expected 30 days, got {len(ALL_DAYS)}"

# wipe any previous demo data so this is a clean run
import shutil
data_dir = os.path.join(os.path.dirname(__file__), "data")
if os.path.exists(data_dir):
    shutil.rmtree(data_dir)

storage = LocalCSVStorage()

variants = ["Variant A", "Variant B"]
names = [f"Student{i}" for i in range(1, 41)]

def fake_response(item, student_idx, variant, day):
    """Simulate mostly-correct answers, with Variant B improving faster on the
    height-vs-slant misconception item across Day 8 -> 9 -> 30 (to sanity-check
    that the research chart can actually show a trend)."""
    if item.get("research_tag") == "height_vs_slant_misconception":
        base_error_rate = {"Variant A": 0.5, "Variant B": 0.5}[variant]
        decay = {"Variant A": 0.05, "Variant B": 0.20}[variant]  # B improves faster
        checkpoint = {8: 0, 9: 1, 30: 2}[day]
        error_rate = max(0.05, base_error_rate - decay * checkpoint)
        if random.random() < error_rate:
            return "B"  # the misconception distractor
        return item["answer"]

    if item["type"] == "multiple_choice":
        return item["answer"] if random.random() < 0.75 else random.choice(["A", "B", "C", "D"])
    if item["type"] == "numeric_entry":
        return item["answer"] if random.random() < 0.75 else (float(item["answer"]) + 1)
    return item["answer"] if random.random() < 0.75 else "wrong"

n_sessions = 0
for day, day_data in ALL_DAYS.items():
    for idx, name in enumerate(names[:15]):  # keep the smoke test fast
        variant = variants[idx % 2]
        responses = {item["id"]: fake_response(item, idx, variant, day) for item in day_data["items"]}
        graded = grade_session(day_data["items"], responses)
        session = SessionRecord(
            student_id=name, student_name=name, class_section=f"Period {1 if variant=='Variant A' else 2}",
            representation_variant=variant, day=day, day_title=day_data["title"],
            score_correct=graded["score_correct"], score_total=graded["score_total"],
            score_percent=graded["score_percent"],
        )
        item_rows = []
        for item in day_data["items"]:
            r = graded["results"][item["id"]]
            item_rows.append({
                "session_id": session.session_id, "item_id": item["id"], "day": day,
                "standard": ",".join(day_data.get("standards", [])),
                "research_tag": item.get("research_tag", ""),
                "item_type": item["type"], "given_answer": r["given"],
                "expected_answer": r["expected"], "correct": r["correct"], "skipped": r["skipped"],
            })
        storage.save_session(session, item_rows)
        n_sessions += 1

print(f"Simulated {n_sessions} test sessions across 30 days.")

sessions_df = pd.DataFrame(storage.load_sessions())
items_df = pd.DataFrame(storage.load_item_responses())
assert len(sessions_df) == n_sessions
print(f"sessions.csv: {len(sessions_df)} rows, item_responses.csv: {len(items_df)} rows")

# exercise every chart function
fig1 = charts.score_distribution_chart(sessions_df, 8)
fig2 = charts.growth_over_time_chart(sessions_df)
fig3 = charts.item_difficulty_chart(items_df, 8)

item_meta = {}
for d, day_data in ALL_DAYS.items():
    for item in day_data["items"]:
        item_meta[item["id"]] = {"standard": ",".join(day_data.get("standards", [])) or "Unassigned"}
fig4 = charts.standards_mastery_heatmap(items_df, item_meta)

fig5 = charts.misconception_trend_chart(items_df, sessions_df)

for name, fig in [("score_distribution", fig1), ("growth_over_time", fig2),
                   ("item_difficulty", fig3), ("standards_heatmap", fig4),
                   ("misconception_trend", fig5)]:
    assert fig is not None
    out = os.path.join(os.path.dirname(__file__), f"smoke_{name}.png")
    try:
        fig.write_image(out)
        print(f"  wrote {out}")
    except Exception as e:
        print(f"  ({name} figure built OK; PNG export skipped: {e})")

print("\nALL SMOKE TESTS PASSED")
