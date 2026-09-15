"""Google Classroom integration.

Two levels:

1. LINKS (works today, no approvals):
   - Every day's test has a direct link: <app_url>?day=N
   - "Post to Classroom" buttons use Google's official Classroom share
     endpoint (classroom.google.com/share). The teacher clicks, picks a
     class, and Classroom creates the assignment with the test link attached.

2. API SYNC (needs a one-time Workspace admin approval):
   Uses the same Google Cloud service account as Sheets storage, with
   domain-wide delegation, acting as the teacher (secrets:
   classroom_delegated_user). Enables:
   - listing your Classroom courses and pulling rosters directly
   - creating assignments for each day (with the test link attached)
   - pushing autograded scores into those assignments' grade columns,
     so students and guardians see them in Classroom.
   Classroom only lets an app grade assignments that the same app created,
   so grade sync works for assignments created from the Teacher Portal.
"""
from urllib.parse import urlencode

SHARE_ENDPOINT = "https://classroom.google.com/share"

SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
    "https://www.googleapis.com/auth/classroom.profile.emails",
    "https://www.googleapis.com/auth/classroom.coursework.students",
]


def test_link(app_url: str, day: int) -> str:
    base = (app_url or "").rstrip("/") + "/"
    return f"{base}?day={int(day)}"


def share_url(target_url: str, title: str, body: str = "", itemtype: str = "assignment") -> str:
    """Google's Classroom share button URL. itemtype: assignment | material |
    announcement | question."""
    params = {"url": target_url, "title": title, "itemtype": itemtype}
    if body:
        params["body"] = body
    return f"{SHARE_ENDPOINT}?{urlencode(params)}"


def api_configured(secrets) -> bool:
    try:
        return bool(secrets.get("classroom_delegated_user")) and "gcp_service_account" in secrets
    except Exception:
        return False


class ClassroomAPI:
    def __init__(self, secrets):
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        creds = Credentials.from_service_account_info(
            dict(secrets["gcp_service_account"]), scopes=SCOPES
        ).with_subject(secrets["classroom_delegated_user"])
        self.svc = build("classroom", "v1", credentials=creds, cache_discovery=False)

    # ---------- read ----------
    def list_courses(self):
        out, token = [], None
        while True:
            resp = self.svc.courses().list(teacherId="me", courseStates=["ACTIVE"],
                                           pageToken=token, pageSize=100).execute()
            out += resp.get("courses", [])
            token = resp.get("nextPageToken")
            if not token:
                return out

    def list_students(self, course_id: str, section_label: str):
        out, token = [], None
        while True:
            resp = self.svc.courses().students().list(courseId=course_id, pageToken=token,
                                                      pageSize=100).execute()
            for s in resp.get("students", []):
                p = s.get("profile", {})
                name = p.get("name", {})
                out.append({
                    "student_id": p.get("emailAddress") or s.get("userId"),
                    "first_name": name.get("givenName", ""),
                    "last_name": name.get("familyName", ""),
                    "email": p.get("emailAddress", ""),
                    "class_section": section_label,
                    "_user_id": s.get("userId"),
                })
            token = resp.get("nextPageToken")
            if not token:
                return out

    # ---------- write ----------
    def create_assignment(self, course_id: str, title: str, description: str, link: str,
                          max_points: int = 100, publish: bool = True):
        body = {
            "title": title,
            "description": description,
            "materials": [{"link": {"url": link}}],
            "workType": "ASSIGNMENT",
            "state": "PUBLISHED" if publish else "DRAFT",
            "maxPoints": max_points,
        }
        return self.svc.courses().courseWork().create(courseId=course_id, body=body).execute()

    def push_grades(self, course_id: str, coursework_id: str, email_to_score: dict,
                    return_to_students: bool = True):
        """email_to_score: {student_email_lower: points}. Returns (updated, unmatched_emails)."""
        roster = {s["_user_id"]: s["email"].lower() for s in self.list_students(course_id, "")}
        wanted = {k.lower(): v for k, v in email_to_score.items()}
        updated, seen, token = 0, set(), None
        subs = self.svc.courses().courseWork().studentSubmissions()
        while True:
            resp = subs.list(courseId=course_id, courseWorkId=coursework_id,
                             pageToken=token, pageSize=100).execute()
            for sub in resp.get("studentSubmissions", []):
                email = roster.get(sub.get("userId"), "")
                if email not in wanted:
                    continue
                pts = float(wanted[email])
                subs.patch(courseId=course_id, courseWorkId=coursework_id, id=sub["id"],
                           updateMask="assignedGrade,draftGrade",
                           body={"assignedGrade": pts, "draftGrade": pts}).execute()
                if return_to_students and sub.get("state") != "RETURNED":
                    try:
                        subs.return_(courseId=course_id, courseWorkId=coursework_id,
                                     id=sub["id"], body={}).execute()
                    except Exception:
                        pass  # grade is saved even if the return step is refused
                seen.add(email)
                updated += 1
            token = resp.get("nextPageToken")
            if not token:
                break
        return updated, sorted(set(wanted) - seen)
