"""Loads the 30-day summative item bank from content/day##.json.

Used by both the student test-taking flow and the teacher portal, so the
item bank is defined exactly once and can't drift between the two.
"""
import json
import os

CONTENT_DIR = os.path.dirname(__file__)


def load_day(day_number: int) -> dict:
    """Load one day's test (1-30). Raises FileNotFoundError if it doesn't exist yet."""
    path = os.path.join(CONTENT_DIR, f"day{day_number:02d}.json")
    with open(path) as f:
        return json.load(f)


def load_all_days() -> dict:
    """Load every day 1-30 into {day_number: day_dict}."""
    days = {}
    for n in range(1, 31):
        try:
            days[n] = load_day(n)
        except FileNotFoundError:
            continue
    return days


def available_days() -> list:
    return sorted(
        int(f[3:5]) for f in os.listdir(CONTENT_DIR)
        if f.startswith("day") and f.endswith(".json")
    )


def all_items_flat(days: dict = None) -> list:
    """Flatten every item across every day into one list, each tagged with its day number/title."""
    days = days or load_all_days()
    flat = []
    for day_num, day in days.items():
        for item in day["items"]:
            flat.append({**item, "day": day_num, "day_title": day["title"], "standards": day.get("standards", [])})
    return flat
