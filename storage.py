"""Pluggable storage backend for Summative Test Sessions.

IMPORTANT — read before entering real student data:
This app's GitHub repo (cpamathlauncher) is PUBLIC. Real student names,
IDs, or test results must never be written to a file that gets committed
to that repo. This module never writes to the repo itself — it writes to
either:

  1. LocalCSVStorage — a `data/` folder that is git-ignored (see .gitignore).
     This is fine for your own local testing, but Streamlit Community
     Cloud's filesystem is EPHEMERAL: it can be wiped on every reboot or
     redeploy. Do not rely on it for real student records.

  2. GoogleSheetsStorage — writes to a private Google Sheet you own, shared
     only with a service account. This is the recommended path for real
     classroom use: free, private, and outside the public repo. See
     SETUP.md for the 10-minute setup (create a Google Cloud service
     account, share your Sheet with its email, paste its key into
     Streamlit secrets).

The app auto-selects Google Sheets storage if `st.secrets["gcp_service_account"]`
is configured, and otherwise falls back to LocalCSVStorage with an on-screen
"DEMO MODE" warning so nobody mistakes it for a safe place to store real data.
"""
import csv
import os
import uuid
import datetime
from dataclasses import dataclass, asdict

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

SESSION_FIELDS = [
    "session_id", "timestamp", "student_id", "student_name", "class_section",
    "representation_variant", "day", "day_title", "score_correct", "score_total", "score_percent",
]
ITEM_RESPONSE_FIELDS = [
    "session_id", "item_id", "day", "standard", "research_tag", "item_type",
    "given_answer", "expected_answer", "correct", "skipped",
]


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
    session_id: str = None
    timestamp: str = None

    def __post_init__(self):
        self.session_id = self.session_id or str(uuid.uuid4())
        self.timestamp = self.timestamp or datetime.datetime.utcnow().isoformat()


class LocalCSVStorage:
    """Default, zero-setup backend. NOT safe for real student PII on Streamlit
    Community Cloud (ephemeral filesystem) — see module docstring."""

    is_demo_mode = True
    label = "Local CSV (demo mode — not private storage)"

    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self._sessions_path = os.path.join(DATA_DIR, "sessions.csv")
        self._items_path = os.path.join(DATA_DIR, "item_responses.csv")
        self._ensure_file(self._sessions_path, SESSION_FIELDS)
        self._ensure_file(self._items_path, ITEM_RESPONSE_FIELDS)

    @staticmethod
    def _ensure_file(path, fields):
        if not os.path.exists(path):
            with open(path, "w", newline="") as f:
                csv.DictWriter(f, fieldnames=fields).writeheader()

    def save_session(self, session: SessionRecord, item_rows: list):
        with open(self._sessions_path, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=SESSION_FIELDS).writerow(asdict(session))
        with open(self._items_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=ITEM_RESPONSE_FIELDS)
            for row in item_rows:
                writer.writerow(row)
        return session.session_id

    def load_sessions(self):
        with open(self._sessions_path) as f:
            return list(csv.DictReader(f))

    def load_item_responses(self):
        with open(self._items_path) as f:
            return list(csv.DictReader(f))


class GoogleSheetsStorage:
    """Recommended backend for real classroom use. Requires `gspread` and a
    service account configured in st.secrets['gcp_service_account'], plus
    st.secrets['sheet_id'] pointing at a private Sheet you've shared with
    that service account's email. See SETUP.md."""

    is_demo_mode = False
    label = "Google Sheets (private)"

    def __init__(self, secrets):
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(dict(secrets["gcp_service_account"]), scopes=scopes)
        self._client = gspread.authorize(creds)
        self._sheet = self._client.open_by_key(secrets["sheet_id"])
        self._sessions_ws = self._get_or_create_ws("sessions", SESSION_FIELDS)
        self._items_ws = self._get_or_create_ws("item_responses", ITEM_RESPONSE_FIELDS)

    def _get_or_create_ws(self, title, header):
        try:
            ws = self._sheet.worksheet(title)
        except Exception:
            ws = self._sheet.add_worksheet(title=title, rows=1000, cols=len(header))
            ws.append_row(header)
        return ws

    def save_session(self, session: SessionRecord, item_rows: list):
        d = asdict(session)
        self._sessions_ws.append_row([d[k] for k in SESSION_FIELDS])
        for row in item_rows:
            self._items_ws.append_row([row.get(k, "") for k in ITEM_RESPONSE_FIELDS])
        return session.session_id

    def load_sessions(self):
        return self._sessions_ws.get_all_records()

    def load_item_responses(self):
        return self._items_ws.get_all_records()


def get_storage(st_secrets=None):
    """Auto-select the storage backend. Returns (storage_instance, is_demo_mode)."""
    try:
        if st_secrets and "gcp_service_account" in st_secrets and "sheet_id" in st_secrets:
            return GoogleSheetsStorage(st_secrets), False
    except Exception:
        pass  # fall back to CSV if Sheets setup is incomplete/misconfigured
    return LocalCSVStorage(), True
