import json, os, math
from fractions import Fraction

CONTENT_DIR = os.path.join(os.path.dirname(__file__), "content")
errors = []
warnings = []
total_items = 0
day_files = sorted(f for f in os.listdir(CONTENT_DIR) if f.endswith(".json"))

if len(day_files) != 30:
    errors.append(f"Expected 30 day files, found {len(day_files)}")

seen_ids = set()

def safe_eval(formula):
    # restricted eval environment for verifying arithmetic
    allowed = {"abs": abs, "round": round, "sqrt": math.sqrt, "Fraction": Fraction}
    return eval(formula, {"__builtins__": {}}, allowed)

for fname in day_files:
    path = os.path.join(CONTENT_DIR, fname)
    with open(path) as f:
        data = json.load(f)

    day_num = data.get("day")
    items = data.get("items", [])
    if not items:
        errors.append(f"{fname}: no items found")
        continue

    for item in items:
        total_items += 1
        iid = item.get("id")
        if not iid:
            errors.append(f"{fname}: item missing id")
            continue
        if iid in seen_ids:
            errors.append(f"Duplicate item id: {iid}")
        seen_ids.add(iid)

        itype = item.get("type")
        if itype not in ("multiple_choice", "numeric_entry", "short_answer"):
            errors.append(f"{iid}: unknown type '{itype}'")

        if "prompt" not in item or not item["prompt"].strip():
            errors.append(f"{iid}: missing prompt")

        if "answer" not in item:
            errors.append(f"{iid}: missing answer")

        if itype == "multiple_choice":
            choices = item.get("choices", {})
            if set(choices.keys()) != {"A", "B", "C", "D"}:
                errors.append(f"{iid}: choices must be exactly A/B/C/D, got {list(choices.keys())}")
            if item.get("answer") not in ("A", "B", "C", "D"):
                errors.append(f"{iid}: MC answer must be A/B/C/D, got {item.get('answer')}")

        if itype == "numeric_entry" and "formula" in item:
            try:
                computed = safe_eval(item["formula"])
                expected = item["answer"]
                if isinstance(computed, float):
                    computed = round(computed, 6)
                if isinstance(expected, (int, float)) and abs(computed - expected) > 1e-6:
                    errors.append(f"{iid}: formula '{item['formula']}' = {computed}, but answer field = {expected}")
            except Exception as e:
                warnings.append(f"{iid}: could not verify formula '{item['formula']}' ({e})")

        if "misconception_key" in item:
            mk = item["misconception_key"]
            if item["type"] == "multiple_choice":
                if set(mk.keys()) != set(item["choices"].keys()):
                    errors.append(f"{iid}: misconception_key keys don't match choices")

print(f"Checked {len(day_files)} day files, {total_items} items, {len(seen_ids)} unique ids.")
if warnings:
    print(f"\n{len(warnings)} WARNINGS:")
    for w in warnings:
        print(" -", w)
if errors:
    print(f"\n{len(errors)} ERRORS:")
    for e in errors:
        print(" -", e)
    raise SystemExit(1)
else:
    print("\nAll checks passed.")
