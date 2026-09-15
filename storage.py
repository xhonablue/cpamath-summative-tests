"""Storage backend for MathCraft CPA Summative Test Sessions (LIVE).

Production storage is a private Google Sheet you own, shared only with a
Google Cloud service account (see SETUP.md). Student data is never written
to the public GitHub repo.

There is no silent "demo" fallback: if Google Sheets isn't configured, or
the connection fails, `get_storage()` reports that and the app blocks
student testing instead of quietly writing records somewhere temporary.

LocalCSVStorage exists only for local development and automated tests. It
is used only when `dev_mode = true` is set in secrets or the environment
variable CPA_DEV=1 is set.

Worksheets (tabs) created automatically inside the Sheet:
  sessions         one row per submitted test
  item_responses   one row per question answered
  roster           imported class rosters (Google Classroom / PowerSchool / CSV)
  class_variants   class/section -> representation image variant (research)
  classroom_links  day + Classroom course -> Classroom assignment id
"""
import csv
import datetime
import os
import uuid
from dataclasses import asdict, dataclass

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

SESSION_FIELDS = [
    "session_id", "timestamp", "student_id", "student_name", "student_email",
    "class_section", "representation_variant", "day", "day_title",
    "score_correct", "score_total", "score_percent",
]
ITEM_RESPONSE_FIELDS = [
    "session_id", "item_id", "day", "standard", "research_tag", "item_type",
    "given_answer", "expected_answer", "correct", "skipped",
]
ROSTER_FIELDS = ["student_id", "first_name", "last_name", "email", "class_section", "source", "updated_at"]
VARIANT_FIELDS = ["class_section", "variant", "updated_at"]
CLASSROOM_LINK_FIELDS = ["course_id", "course_name", "day", "coursework_id", "alternate_link", "created_at"]

TABLES = {
    "sessions": SESSION_FIELDS,
    "item_responses": ITEM_RESPONSE_FIELDS,
    "roster": ROSTER_FIELDS,
    "class_variants": VARIANT_FIELDS,
    "classroom_links": CLASSROOM_LINK_FIELDS,
}


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


@dataclass
class SessionRecord:
    student_id: str
    student_name: str
    class_section: str
    representation_variant: str
    day: int
    day_title: str
    score_correct: int
    score_total: int
    score_percent: float
    student_email: str = ""
    session_id: str = None
    timestamp: str = None

    def __post_init__(self):
        self.session_id = self.session_id or str(uuid.uuid4())
        self.timestamp = self.timestamp or _now()


class _BaseStorage:
    """Shared higher-level operations built on _read(table) / _append(table, rows) /
    _replace(table, rows)."""

    # ---- sessions ----
    def save_session(self, session: SessionRecord, item_rows: list):
        d = asdict(session)
        # write item rows first: if the session row lands, its items are guaranteed present
        self._append("item_responses", [[r.get(k, "") for k in ITEM_RESPONSE_FIELDS] for r in item_rows])
        self._append("sessions", [[d.get(k, "") for k in SESSION_FIELDS]])
        return session.session_id

    def load_sessions(self):
        return self._read("sessions")

    def load_item_responses(self):
        return self._read("item_responses")

    def prior_attempts(self, student_id: str, day: int):
        sid = str(student_id).strip().lower()
        return [s for s in self.load_sessions()
                if str(s.get("student_id", "")).strip().lower() == sid and str(s.get("day")) == str(day)]

    # ---- roster ----
    def load_roster(self):
        return self._read("roster")

    def upsert_roster(self, students: list, source: str):
        """Insert/replace students keyed on student_id (case-insensitive)."""
        existing = {str(r["student_id"]).lower(): r for r in self.load_roster()}
        for s in students:
            rec = {k: s.get(k, "") for k in ROSTER_FIELDS}
            rec["source"], rec["updated_at"] = source, _now()
            existing[str(rec["student_id"]).lower()] = rec
        self._replace("roster", [[r.get(k, "") for k in ROSTER_FIELDS] for r in existing.values()])
        return len(existing)

    def find_student_by_email(self, email: str):
        email = (email or "").strip().lower()
        if not email:
            return None
        for r in self.load_roster():
            if str(r.get("email", "")).strip().lower() == email:
                return r
        return None

    def class_sections(self):
        return sorted({str(r["class_section"]) for r in self.load_roster() if r.get("class_section")})

    # ---- representation variants ----
    def load_variants(self) -> dict:
        return {str(r["class_section"]): r["variant"] for r in self._read("class_variants")}

    def set_variant(self, class_section: str, variant: str):
        v = self.load_variants()
        v[class_section] = variant
        self._replace("class_variants", [[k, val, _now()] for k, val in v.items()])

    # ---- classroom assignment links ----
    def load_classroom_links(self):
        return self._read("classroom_links")

    def save_classroom_link(self, course_id, course_name, day, coursework_id, alternate_link):
        self._append("classroom_links", [[course_id, course_name, day, coursework_id, alternate_link, _now()]])


class LocalCSVStorage(_BaseStorage):
    """DEVELOPMENT / TESTING ONLY. Not private, not durable on Streamlit Cloud."""

    is_live = False
    label = "Local CSV (development only)"

    def __init__(self, data_dir=DATA_DIR):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        for t, fields in TABLES.items():
            p = self._path(t)
            if not os.path.exists(p):
                with open(p, "w", newline="") as f:
                    csv.writer(f).writerow(fields)

    def _path(self, table):
        return os.path.join(self.data_dir, f"{table}.csv")

    def _read(self, table):
        with open(self._path(table), newline="") as f:
            return list(csv.DictReader(f))

    def _append(self, table, rows):
        if rows:
            with open(self._path(table), "a", newline="") as f:
                csv.writer(f).writerows(rows)

    def _replace(self, table, rows):
        with open(self._path(table), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(TABLES[table])
            w.writerows(rows)


class GoogleSheetsStorage(_BaseStorage):
    """LIVE backend: a private Google Sheet shared with a service account."""

    is_live = True
    label = "Google Sheets (private, live)"

    def __init__(self, secrets):
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(dict(secrets["gcp_service_account"]), scopes=scopes)
        self._client = gspread.authorize(creds)
        self._sheet = self._client.open_by_key(secrets["sheet_id"])
        self.sheet_url = f"https://docs.google.com/spreadsheets/d/{secrets['sheet_id']}/edit"
        self.service_account_email = secrets["gcp_service_account"].get("client_email", "")
        existing = {ws.title: ws for ws in self._sheet.worksheets()}
        self._ws = {}
        for title, header in TABLES.items():
            ws = existing.get(title)
            if ws is None:
                ws = self._sheet.add_worksheet(title=title, rows=1000, cols=len(header))
                ws.append_row(header)
            else:
                first = ws.row_values(1)
                if first != header:
                    # upgrade older sheets: add any new columns at the end, never drop data
                    merged = first + [h for h in header if h not in first] if first else header
                    if ws.col_count < len(merged):
                        ws.add_cols(len(merged) - ws.col_count)
                    ws.update(range_name="A1", values=[merged])
            self._ws[title] = ws

    def _read(self, table):
        rows = self._ws[table].get_all_values()
        if not rows:
            return []
        header = rows[0]
        return [dict(zip(header, r + [""] * (len(header) - len(r)))) for r in rows[1:] if any(r)]

    def _append(self, table, rows):
        if not rows:
            return
        ws = self._ws[table]
        header = ws.row_values(1)
        fields = TABLES[table]
        # align to the sheet's actual column order (handles upgraded sheets)
        aligned = [[dict(zip(fields, r)).get(h, "") for h in header] for r in rows]
        ws.append_rows([[_cell(v) for v in r] for r in aligned], value_input_option="RAW")

    def _replace(self, table, rows):
        ws = self._ws[table]
        header = TABLES[table]
        ws.clear()
        ws.update(range_name="A1", values=[header] + [[_cell(v) for v in r] for r in rows])


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    return v


def get_storage(secrets=None):
    """Returns (storage_or_None, status, message).

    status is one of:
      "live"            Google Sheets connected
      "dev"             local CSV, explicitly enabled for development
      "not_configured"  no Sheets secrets yet -> testing is blocked
      "error"           Sheets secrets present but connection failed -> testing is blocked
    """
    def _get(key, default=None):
        try:
            return secrets.get(key, default) if secrets is not None else default
        except Exception:
            return default

    has_sheets = False
    try:
        has_sheets = secrets is not None and "gcp_service_account" in secrets and "sheet_id" in secrets
    except Exception:
        has_sheets = False

    if has_sheets:
        try:
            return GoogleSheetsStorage(secrets), "live", "Connected to Google Sheets."
        except Exception as e:  # never fall back silently
            return None, "error", f"{type(e).__name__}: {e}"

    if str(_get("dev_mode", "")).lower() == "true" or os.environ.get("CPA_DEV") == "1":
        return LocalCSVStorage(), "dev", "Development mode (local CSV)."

    return None, "not_configured", "Google Sheets storage has not been configured yet."
