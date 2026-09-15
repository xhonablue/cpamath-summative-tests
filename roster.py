"""Roster import from Google Classroom and PowerSchool CSV exports.

Neither system's live API is wired up yet (both need district-issued
credentials — see SETUP.md). Until then, a teacher can export a class
roster as CSV from either system and upload it here; this module maps
whatever columns that export happens to use onto one canonical schema
so the rest of the app never has to care which SIS the data came from.

Google Classroom "Students" export typically has: Last Name, First Name, Email
PowerSchool student exports vary by field selection, but commonly include
some combination of: Student_Number / Student ID, Last_Name, First_Name,
Grade_Level, Section / Class.
"""
import csv
import io

CANONICAL_FIELDS = ["student_id", "first_name", "last_name", "email", "class_section"]

# Maps many possible source-column spellings -> canonical field name.
COLUMN_ALIASES = {
    "student_id": ["student_id", "student id", "student_number", "student number",
                   "studentnumber", "id", "sis id", "sisid"],
    "first_name": ["first_name", "first name", "firstname", "given name"],
    "last_name": ["last_name", "last name", "lastname", "surname", "family name"],
    "email": ["email", "email address", "student email"],
    "class_section": ["class_section", "class", "section", "period", "course", "class name"],
}


def _canonical_map(fieldnames):
    lower_to_original = {f.strip().lower(): f for f in fieldnames}
    mapping = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lower_to_original:
                mapping[canonical] = lower_to_original[alias]
                break
    return mapping


def parse_roster_csv(file_bytes_or_text) -> list:
    """Returns a list of dicts with the CANONICAL_FIELDS keys, best-effort
    mapped from whatever the uploaded export's columns actually are.
    Rows that can't produce at least a name are skipped."""
    if isinstance(file_bytes_or_text, bytes):
        text = file_bytes_or_text.decode("utf-8-sig")
    else:
        text = file_bytes_or_text

    reader = csv.DictReader(io.StringIO(text))
    mapping = _canonical_map(reader.fieldnames or [])

    students = []
    for row in reader:
        rec = {canonical: row.get(source, "").strip() for canonical, source in mapping.items()}
        for f in CANONICAL_FIELDS:
            rec.setdefault(f, "")
        if not (rec["first_name"] or rec["last_name"] or rec["email"] or rec["student_id"]):
            continue
        if not rec["student_id"]:
            # fall back to email (or name) as a stable-enough identifier
            rec["student_id"] = rec["email"] or f"{rec['first_name']}_{rec['last_name']}"
        students.append(rec)
    return students


def unmapped_columns_warning(file_bytes_or_text) -> list:
    """Returns column names from the upload that weren't recognized, so the
    teacher portal can flag them for a manual look rather than silently
    dropping data."""
    if isinstance(file_bytes_or_text, bytes):
        text = file_bytes_or_text.decode("utf-8-sig")
    else:
        text = file_bytes_or_text
    reader = csv.DictReader(io.StringIO(text))
    mapping = _canonical_map(reader.fieldnames or [])
    recognized = set(mapping.values())
    return [f for f in (reader.fieldnames or []) if f not in recognized]
