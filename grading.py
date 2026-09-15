"""Autograding logic for Summative Test Sessions.

Each item type is graded differently:
- multiple_choice: exact letter match (A/B/C/D)
- numeric_entry: numeric match, with a small floating-point tolerance and
  an optional explicit accept_range [lo, hi] on the item for rounding-sensitive
  questions (e.g. "round to the nearest whole percent")
- short_answer: lenient text match after normalizing whitespace, case, and
  common equivalent notations (e.g. "x<=10" vs "x <= 10" vs "x≤10")
"""
import re


def _normalize_short_answer(text: str) -> str:
    text = str(text).strip().lower()
    text = text.replace(" ", "")
    text = text.replace("≤", "<=").replace("≥", ">=")
    return text


def grade_item(item: dict, student_response) -> dict:
    """Returns {'correct': bool, 'expected': ..., 'given': ...}."""
    itype = item["type"]
    expected = item["answer"]

    if student_response is None or student_response == "":
        return {"correct": False, "expected": expected, "given": student_response, "skipped": True}

    if itype == "multiple_choice":
        given = str(student_response).strip().upper()
        correct = given == str(expected).strip().upper()

    elif itype == "numeric_entry":
        try:
            given_num = float(student_response)
        except (TypeError, ValueError):
            return {"correct": False, "expected": expected, "given": student_response, "skipped": False}
        accept_range = item.get("accept_range")
        if accept_range:
            correct = accept_range[0] - 1e-6 <= given_num <= accept_range[1] + 1e-6
        else:
            correct = abs(given_num - float(expected)) < 1e-6
        given = given_num

    elif itype == "short_answer":
        given = student_response
        correct = _normalize_short_answer(given) == _normalize_short_answer(expected)

    else:
        raise ValueError(f"Unknown item type: {itype}")

    return {"correct": correct, "expected": expected, "given": given, "skipped": False}


def grade_session(items: list, responses: dict) -> dict:
    """items: list of item dicts for the day being taken.
    responses: {item_id: student_response}.
    Returns per-item results plus a session summary.
    """
    results = {}
    n_correct = 0
    for item in items:
        r = grade_item(item, responses.get(item["id"]))
        results[item["id"]] = r
        if r["correct"]:
            n_correct += 1

    total = len(items)
    pct = round(100 * n_correct / total, 1) if total else 0.0
    return {
        "results": results,
        "score_correct": n_correct,
        "score_total": total,
        "score_percent": pct,
    }
