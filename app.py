"""MathCraft CPA — Summative Test Sessions (LIVE)

Chandler Park Academy's own i-Ready-style summative platform for Grade 6 math:
  - Study Guide: open IXL prep for all 30 days.
  - Student: sign in with a school Google account (or name + class), take
    the day's check, get autograded instantly. One attempt per day unless
    the teacher enables retakes.
  - Teacher Portal: live Google Classroom links and assignment posting,
    roster sync, results dashboards, grade sync to Classroom, research
    charts, export, and a setup/status checklist.
  - Admin — View Only: aggregate, de-identified cohort charts.

Student data lives only in a private Google Sheet (see SETUP.md). If that
isn't connected, student testing is blocked — there is no demo fallback.
"""
import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))
from content.loader import load_all_days, available_days  # noqa: E402
from grading import grade_session  # noqa: E402
from storage import get_storage, SessionRecord  # noqa: E402
import roster as roster_mod  # noqa: E402
import classroom  # noqa: E402
import charts  # noqa: E402

st.set_page_config(page_title="MathCraft CPA — Summative Test Sessions", page_icon="📝", layout="wide")

NAVY = "#1F3864"
GOLD = "#B08D57"
DEFAULT_APP_URL = "https://cpamath-summative-tests.streamlit.app/"


# ------------------------------------------------------------- secrets ---
def secret(key, default=None):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def _as_list(v):
    if not v:
        return []
    if isinstance(v, str):
        return [x.strip().lower() for x in v.split(",") if x.strip()]
    return [str(x).strip().lower() for x in v]


APP_URL = secret("app_url", DEFAULT_APP_URL)
ALLOW_RETAKES = str(secret("allow_retakes", "false")).lower() == "true"
TEACHER_EMAILS = _as_list(secret("teacher_emails"))
ADMIN_EMAILS = _as_list(secret("admin_emails"))
STUDENT_DOMAIN = str(secret("student_email_domain", "") or "").strip().lower().lstrip("@")


def auth_configured():
    try:
        return "auth" in st.secrets and hasattr(st, "login")
    except Exception:
        return False


AUTH_ON = auth_configured()


def current_user():
    """Returns {'email','name'} when signed in with Google, else None."""
    if not AUTH_ON:
        return None
    try:
        if st.user.is_logged_in:
            return {"email": str(st.user.get("email", "")).lower(), "name": st.user.get("name", "")}
    except Exception:
        pass
    return None


# ------------------------------------------------------------- storage ---
@st.cache_resource(show_spinner="Connecting to secure storage…")
def _connect(signature: str):
    # _signature changes whenever storage-related secrets change, forcing a reconnect
    try:
        return get_storage(st.secrets)
    except Exception:
        return get_storage(None)


_sig = f"{secret('sheet_id', '')}|{secret('dev_mode', '')}|{os.environ.get('CPA_DEV', '')}"
storage, STORAGE_STATUS, STORAGE_MSG = _connect(_sig)
LIVE_OK = STORAGE_STATUS in ("live", "dev")


@st.cache_data(ttl=20, show_spinner=False)
def cached(table: str, _v: int = 0):
    return {
        "sessions": storage.load_sessions,
        "items": storage.load_item_responses,
        "roster": storage.load_roster,
        "variants": storage.load_variants,
        "links": storage.load_classroom_links,
    }[table]()


def refresh():
    cached.clear()


ALL_DAYS = load_all_days()
DAY_NUMS = available_days()


def item_meta():
    return {
        item["id"]: {"standard": ",".join(d.get("standards", [])) or "Unassigned"}
        for d in ALL_DAYS.values() for item in d["items"]
    }


# ------------------------------------------------------------- header ---
st.markdown(
    f"""
    <div style="background:linear-gradient(135deg,{NAVY} 0%, #142544 100%);
                color:white;padding:1.6rem 2rem;border-radius:14px;
                border-bottom:6px solid {GOLD};margin-bottom:1rem;">
        <h1 style="margin:0;color:white;">📝 MathCraft CPA — Summative Test Sessions</h1>
        <p style="margin:0.3rem 0 0 0;opacity:0.9;">Chandler Park Academy · Grade 6 Mathematics</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if STORAGE_STATUS == "not_configured":
    st.error("**Setup required** — secure storage isn't connected yet, so testing is paused. "
             "Teachers: open **Teacher Portal → Setup & Status**.", icon="🔒")
elif STORAGE_STATUS == "error":
    st.error("**Storage connection problem** — testing is paused so no answers are lost. "
             "Teachers: open **Teacher Portal → Setup & Status** for details.", icon="🛑")
elif STORAGE_STATUS == "dev":
    st.warning("Development mode (local test data only).", icon="🧪")

# ------------------------------------------------------------- sidebar ---
qp_day = st.query_params.get("day")
try:
    LINKED_DAY = int(qp_day) if qp_day and int(qp_day) in ALL_DAYS else None
except ValueError:
    LINKED_DAY = None

MODES = ["Study Guide", "Student — Take a Test", "Teacher Portal", "Admin — View Only"]
default_mode = 1 if LINKED_DAY else 0
mode = st.sidebar.radio("Mode", MODES, index=default_mode)

user = current_user()
if AUTH_ON:
    st.sidebar.divider()
    if user:
        st.sidebar.caption(f"Signed in as **{user['email']}**")
        if st.sidebar.button("Sign out"):
            st.logout()
    else:
        st.sidebar.button("Sign in with Google", on_click=st.login, type="primary")


def require_staff(role: str):
    """role: 'teacher' or 'admin'. Google sign-in allowlist if configured, else PIN."""
    allow = TEACHER_EMAILS if role == "teacher" else ADMIN_EMAILS + TEACHER_EMAILS
    if AUTH_ON and allow:
        if not user:
            st.info("Sign in with your CPA Google account to continue.")
            st.button("Sign in with Google", on_click=st.login, type="primary", key=f"login_{role}")
            st.stop()
        if user["email"] not in allow:
            st.error(f"{user['email']} isn't on the {role} access list.")
            st.stop()
        return
    key = "teacher_pin" if role == "teacher" else "admin_pin"
    configured = secret(key)
    if not configured:
        st.error(f"The {role} PIN hasn't been set. Add `{key}` in the app's Secrets "
                 "(see SETUP.md). Access is locked until then.")
        if role == "teacher":
            setup_status_panel()
        st.stop()
    pin = st.text_input(f"{role.title()} PIN", type="password", key=f"{role}_pin_input")
    if pin != configured:
        st.stop()


def setup_status_panel():
    st.markdown("#### Launch checklist")
    rows = [
        ("Secure storage (Google Sheet)", STORAGE_STATUS == "live",
         STORAGE_MSG if STORAGE_STATUS != "live" else f"[Open results sheet]({storage.sheet_url})"),
        ("Teacher access set", bool(secret("teacher_pin") or (AUTH_ON and TEACHER_EMAILS)),
         "teacher_pin or teacher_emails + Google sign-in"),
        ("Admin access set", bool(secret("admin_pin") or (AUTH_ON and ADMIN_EMAILS)),
         "admin_pin or admin_emails + Google sign-in"),
        ("Student Google sign-in", AUTH_ON, "[auth] section in Secrets (recommended)"),
        ("Classroom links & share buttons", True, f"Test links use {APP_URL}"),
        ("Classroom API sync (rosters, assignments, grades)", classroom.api_configured(st.secrets)
         if hasattr(st, "secrets") else False,
         "classroom_delegated_user + admin-approved domain-wide delegation"),
        ("Roster loaded", LIVE_OK and len(cached("roster")) > 0, "Teacher Portal → Roster"),
    ]
    for label, ok, note in rows:
        st.markdown(f"{'✅' if ok else '⬜'} **{label}** — {note}")
    if STORAGE_STATUS == "live":
        st.caption(f"Service account: `{storage.service_account_email}`")
    st.caption("Full instructions: SETUP.md in the GitHub repo.")


# ========================================================= STUDY GUIDE =====
if mode == "Study Guide":
    st.subheader("📚 Study Guide — What to Practice on IXL, and When")
    st.write("Every summative check is tied to specific IXL skills. Pick any day and practice ahead.")
    ARCS = [
        ("Getting Started & Data (Days 1–4)", range(1, 5)),
        ("Area of Rectangles, Parallelograms & Compound Figures (Days 5–9)", range(5, 10)),
        ("Multiplying Decimals & Fractions (Day 10)", range(10, 11)),
        ("Percent (Days 11–15)", range(11, 16)),
        ("Ratios & Rates (Days 16–20)", range(16, 21)),
        ("Expressions & Equations (Days 21–25)", range(21, 26)),
        ("Rational Numbers & the Coordinate Plane (Days 26–29)", range(26, 30)),
        ("Cumulative Review (Day 30)", range(30, 31)),
    ]
    for arc_title, day_range in ARCS:
        days_in_arc = [d for d in day_range if d in ALL_DAYS]
        if not days_in_arc:
            continue
        st.markdown(f"### {arc_title}")
        for d in days_in_arc:
            dd = ALL_DAYS[d]
            with st.container(border=True):
                st.markdown(f"**Day {d} — {dd['title']}**")
                if dd.get("standards"):
                    st.caption("Standards: " + ", ".join(dd["standards"]))
                prep = dd.get("ixl_prep") or []
                if prep:
                    st.markdown("Practice on IXL before this test:")
                    for skill in prep:
                        st.markdown(f"- [{skill['label']}]({skill['url']})")
                else:
                    st.caption(dd.get("ixl_prep_note", "No single IXL skill maps directly to this day."))

# ============================================================== STUDENT ====
elif mode == "Student — Take a Test":
    st.subheader("Start a Summative Check")
    if not LIVE_OK:
        st.info("Testing opens as soon as your teacher finishes setup. Check back soon!")
        st.stop()

    # --- identity ---
    roster_rec = None
    if AUTH_ON:
        if not user:
            st.info("Sign in with your **school Google account** to start your test.")
            st.button("Sign in with Google", on_click=st.login, type="primary", key="student_login")
            st.stop()
        if STUDENT_DOMAIN and not user["email"].endswith("@" + STUDENT_DOMAIN):
            st.error(f"Please sign in with your @{STUDENT_DOMAIN} school account.")
            st.stop()
        roster_rec = storage.find_student_by_email(user["email"])
        student_email = user["email"]
        if roster_rec:
            student_name = f"{roster_rec['first_name']} {roster_rec['last_name']}".strip() or user["name"]
            student_id = str(roster_rec["student_id"])
            class_section = str(roster_rec["class_section"])
            st.success(f"Welcome, **{student_name}** · {class_section}")
        else:
            student_name = user["name"] or student_email
            student_id = student_email
            sections = storage.class_sections()
            class_section = (st.selectbox("Your class", sections, index=None) if sections
                             else st.text_input("Class / Section", placeholder="e.g., Period 2"))
            st.caption(f"Signed in as {student_email}")
    else:
        student_email = ""
        sections = storage.class_sections()
        c1, c2, c3 = st.columns(3)
        student_name = c1.text_input("Your full name")
        student_id = c2.text_input("Student ID (optional)")
        class_section = (c3.selectbox("Class / Section", sections, index=None) if sections
                         else c3.text_input("Class / Section", placeholder="e.g., Period 2"))
        student_id = student_id.strip() or student_name.strip()

    # --- day ---
    if LINKED_DAY:
        day = LINKED_DAY
        st.markdown(f"#### Day {day} — {ALL_DAYS[day]['title']}")
    else:
        day = st.selectbox("Which day's summative check?", DAY_NUMS,
                           format_func=lambda d: f"Day {d} — {ALL_DAYS[d]['title']}")
    day_data = ALL_DAYS[day]
    st.caption(f"Standards: {', '.join(day_data.get('standards', []))}")

    if not student_name or not class_section:
        st.info("Enter your name and class/section above to begin.")
        st.stop()

    done_key = f"done_{student_id}_{day}"
    if not ALLOW_RETAKES and not st.session_state.get(done_key):
        prior = storage.prior_attempts(student_id, day)
        if prior:
            p = prior[-1]
            st.warning(f"You already completed Day {day} "
                       f"({p['score_correct']}/{p['score_total']}, {p['score_percent']}%). "
                       "Ask your teacher if you need a retake.", icon="✅")
            st.stop()

    if st.session_state.get(done_key):
        r = st.session_state[done_key]
        st.success(f"Submitted! Score: {r['score_correct']} / {r['score_total']}  ({r['score_percent']}%)")
        st.progress(min(r["score_percent"] / 100, 1.0))
        with st.expander("Review your answers", expanded=True):
            for item in day_data["items"]:
                res = r["results"][item["id"]]
                st.markdown(f"{'✅' if res['correct'] else '❌'} **{item['prompt']}**")
                st.caption(f"Your answer: {res['given']}  |  Correct answer: {res['expected']}")
                if item.get("rationale"):
                    st.caption(item["rationale"])
        st.stop()

    responses = {}
    with st.form("test_form"):
        for i, item in enumerate(day_data["items"], start=1):
            st.markdown(f"**{i}. {item['prompt']}**")
            key = f"{day}_{item['id']}"
            if item["type"] == "multiple_choice":
                labels = [f"{k}. {v}" for k, v in item["choices"].items()]
                choice = st.radio("Select one:", labels, key=key, index=None, label_visibility="collapsed")
                responses[item["id"]] = choice.split(".")[0] if choice else None
            elif item["type"] == "numeric_entry":
                responses[item["id"]] = st.text_input("Your answer (number):", key=key)
            else:
                responses[item["id"]] = st.text_input("Your answer:", key=key)
            st.markdown("---")
        submitted = st.form_submit_button("Submit Summative Check", type="primary")

    if submitted:
        unanswered = [i for i, it in enumerate(day_data["items"], 1) if not responses.get(it["id"])]
        if unanswered and not st.session_state.get(f"confirm_{day}"):
            st.session_state[f"confirm_{day}"] = True
            st.warning(f"Question(s) {', '.join(map(str, unanswered))} are blank. "
                       "Press **Submit** again to turn in anyway.")
            st.stop()

        graded = grade_session(day_data["items"], responses)
        variant = cached("variants").get(class_section, "Unassigned")
        session = SessionRecord(
            student_id=student_id, student_name=student_name, student_email=student_email,
            class_section=class_section, representation_variant=variant,
            day=day, day_title=day_data["title"],
            score_correct=graded["score_correct"], score_total=graded["score_total"],
            score_percent=graded["score_percent"],
        )
        item_rows = [{
            "session_id": session.session_id, "item_id": it["id"], "day": day,
            "standard": ",".join(day_data.get("standards", [])),
            "research_tag": it.get("research_tag", ""), "item_type": it["type"],
            "given_answer": graded["results"][it["id"]]["given"],
            "expected_answer": graded["results"][it["id"]]["expected"],
            "correct": graded["results"][it["id"]]["correct"],
            "skipped": graded["results"][it["id"]]["skipped"],
        } for it in day_data["items"]]
        try:
            with st.spinner("Saving your answers…"):
                storage.save_session(session, item_rows)
        except Exception as e:
            st.error("Your answers could not be saved. Don't close this page — press Submit "
                     f"again in a moment, or tell your teacher. ({type(e).__name__})")
            st.stop()
        refresh()
        st.session_state[done_key] = graded
        st.rerun()

# ========================================================= TEACHER PORTAL ==
elif mode == "Teacher Portal":
    st.subheader("Teacher Portal")
    require_staff("teacher")

    if not LIVE_OK:
        st.error(f"Storage: {STORAGE_MSG}")
        setup_status_panel()
        st.stop()

    top = st.columns([4, 1])
    top[0].caption(f"Storage: **{storage.label}**")
    if top[1].button("↻ Refresh data"):
        refresh()

    tabs = st.tabs(["🏫 Google Classroom", "📋 Roster", "📊 Results", "🧑‍🎓 Students",
                    "🎨 Variants", "🔬 Research", "⬇️ Export", "⚙️ Setup & Status"])
    tab_gc, tab_roster, tab_results, tab_students, tab_var, tab_research, tab_export, tab_setup = tabs

    # ---- Google Classroom ----
    with tab_gc:
        st.markdown("#### Post tests to Google Classroom")
        st.caption("Each link opens the app straight to that day's test. **Post** opens Classroom's "
                   "share window — pick your class and it creates the assignment with the link attached.")
        for d in DAY_NUMS:
            dd = ALL_DAYS[d]
            link = classroom.test_link(APP_URL, d)
            title = f"Day {d} Summative Check — {dd['title']}"
            body = (f"Sign in with your school Google account and complete the Day {d} check. "
                    f"Standards: {', '.join(dd.get('standards', []))}")
            c1, c2, c3 = st.columns([5, 4, 2])
            c1.markdown(f"**Day {d}** — {dd['title']}")
            c2.code(link, language=None)
            c3.link_button("Post to Classroom", classroom.share_url(link, title, body), width="stretch")

        st.divider()
        st.markdown("#### Classroom API sync")
        if not classroom.api_configured(st.secrets):
            st.info("Share buttons above work now. To also **pull rosters, create assignments, and push "
                    "grades automatically**, ask your Google Workspace admin to approve domain-wide "
                    "delegation for the app's service account, then add `classroom_delegated_user` "
                    "(your teacher email) to Secrets. Steps: SETUP.md → Classroom API.")
        else:
            try:
                api = classroom.ClassroomAPI(st.secrets)
                courses = api.list_courses()
            except Exception as e:
                st.error(f"Classroom API error: {e}")
                courses = []
            if courses:
                cmap = {c["id"]: c for c in courses}
                cid = st.selectbox("Course", list(cmap),
                                   format_func=lambda i: f"{cmap[i]['name']} {cmap[i].get('section', '')}")
                course = cmap[cid]
                label = course.get("section") or course["name"]

                a, b = st.columns(2)
                with a:
                    st.markdown("**Roster**")
                    if st.button("Import this course's roster"):
                        studs = api.list_students(cid, label)
                        n = storage.upsert_roster(studs, source=f"classroom:{cid}")
                        refresh()
                        st.success(f"Imported {len(studs)} students into '{label}' ({n} total in roster).")
                with b:
                    st.markdown("**Create assignments**")
                    days_sel = st.multiselect("Days", DAY_NUMS, format_func=lambda d: f"Day {d}")
                    publish = st.toggle("Publish immediately", value=False)
                    if st.button("Create in Classroom", disabled=not days_sel):
                        for d in days_sel:
                            link = classroom.test_link(APP_URL, d)
                            cw = api.create_assignment(
                                cid, f"Day {d} Summative Check — {ALL_DAYS[d]['title']}",
                                "Sign in with your school Google account and complete this check.",
                                link, publish=publish)
                            storage.save_classroom_link(cid, course["name"], d, cw["id"], cw.get("alternateLink", ""))
                        refresh()
                        st.success(f"Created {len(days_sel)} assignment(s).")

                links = [l for l in cached("links") if str(l["course_id"]) == str(cid)]
                if links:
                    st.markdown("**Push scores to Classroom grades** (points out of 100)")
                    lmap = {f"Day {l['day']}": l for l in links}
                    pick = st.selectbox("Assignment", list(lmap))
                    lk = lmap[pick]
                    if lk.get("alternate_link"):
                        st.markdown(f"[Open in Classroom]({lk['alternate_link']})")
                    if st.button("Sync grades now", type="primary"):
                        sdf = pd.DataFrame(cached("sessions"))
                        if sdf.empty:
                            st.info("No results yet.")
                        else:
                            sdf = sdf[(sdf["day"].astype(str) == str(lk["day"])) & (sdf["student_email"] != "")]
                            best = sdf.assign(p=sdf["score_percent"].astype(float)) \
                                      .groupby(sdf["student_email"].str.lower())["p"].max().to_dict()
                            n, missing = api.push_grades(cid, lk["coursework_id"], best)
                            st.success(f"Updated {n} grade(s) in Classroom.")
                            if missing:
                                st.caption("Not in this course: " + ", ".join(missing))

    # ---- Roster ----
    with tab_roster:
        st.markdown("Upload a roster CSV from **Google Classroom** or **PowerSchool** (column names are "
                    "auto-detected). Saved rosters let signed-in students skip typing their class.")
        default_section = st.text_input("Class/section for rows that don't include one",
                                        placeholder="e.g., Period 2")
        up = st.file_uploader("Roster CSV", type=["csv"])
        if up:
            students = roster_mod.parse_roster_csv(up.getvalue())
            for s in students:
                if not s["class_section"]:
                    s["class_section"] = default_section
            st.dataframe(pd.DataFrame(students), hide_index=True)
            unmapped = roster_mod.unmapped_columns_warning(up.getvalue())
            if unmapped:
                st.caption("Columns ignored: " + ", ".join(unmapped))
            if st.button(f"Save {len(students)} students", type="primary"):
                n = storage.upsert_roster(students, source="csv")
                refresh()
                st.success(f"Saved. Roster now has {n} students.")
        r = pd.DataFrame(cached("roster"))
        if not r.empty:
            st.markdown(f"**Current roster — {len(r)} students**")
            st.dataframe(r.drop(columns=["updated_at"], errors="ignore"), hide_index=True)

    sessions = pd.DataFrame(cached("sessions"))
    items_df = pd.DataFrame(cached("items"))

    # ---- Results ----
    with tab_results:
        if sessions.empty:
            st.info("No results yet. They appear here seconds after students submit.")
        else:
            sessions["score_percent"] = pd.to_numeric(sessions["score_percent"], errors="coerce")
            secs = ["All"] + sorted(sessions["class_section"].astype(str).unique())
            f1, f2 = st.columns(2)
            sec = f1.selectbox("Class", secs)
            view = sessions if sec == "All" else sessions[sessions["class_section"].astype(str) == sec]
            iv = items_df[items_df["session_id"].isin(view["session_id"])] if not items_df.empty else items_df
            days_taken = sorted(view["day"].astype(int).unique())
            if not days_taken:
                st.info("No results for this class yet.")
            else:
                d = f2.selectbox("Day", days_taken,
                                 format_func=lambda x: f"Day {x} — {ALL_DAYS.get(x, {}).get('title', '')}")
                vd = view[view["day"].astype(int) == d]
                m = st.columns(4)
                m[0].metric("Tests submitted", len(vd))
                m[1].metric("Average", f"{vd['score_percent'].mean():.0f}%")
                m[2].metric("At/above 70%", f"{(vd['score_percent'] >= 70).mean() * 100:.0f}%")
                m[3].metric("Below 50%", int((vd["score_percent"] < 50).sum()))
                c1, c2 = st.columns(2)
                c1.plotly_chart(charts.score_distribution_chart(view, d), width="stretch")
                c2.plotly_chart(charts.item_difficulty_chart(iv, d), width="stretch")
                st.plotly_chart(charts.growth_over_time_chart(view), width="stretch")
                st.plotly_chart(charts.standards_mastery_heatmap(iv, item_meta()), width="stretch")

    # ---- Students (placement / needs support) ----
    with tab_students:
        if sessions.empty:
            st.info("No results yet.")
        else:
            s = sessions.copy()
            s["score_percent"] = pd.to_numeric(s["score_percent"], errors="coerce")
            summary = (s.groupby(["student_id", "student_name", "class_section"])
                        .agg(tests=("day", "count"), average=("score_percent", "mean"),
                             latest=("score_percent", "last"))
                        .reset_index())
            summary["average"] = summary["average"].round(1)
            summary["support tier"] = pd.cut(summary["average"], [-1, 49.99, 69.99, 101],
                                             labels=["Intensive", "Strategic", "On track"])
            st.markdown("**Student overview** (tiers: <50 Intensive · 50–69 Strategic · 70+ On track)")
            st.dataframe(summary.sort_values("average"), hide_index=True, width="stretch")
            pick = st.selectbox("Student detail", summary["student_name"].unique(), index=None)
            if pick:
                st.dataframe(s[s["student_name"] == pick][["timestamp", "day", "day_title",
                             "score_correct", "score_total", "score_percent"]], hide_index=True)

    # ---- Variants ----
    with tab_var:
        st.markdown("Tag each class with the Day 8 parallelogram image variant it saw. Saved permanently "
                    "and applied to every future submission from that class.")
        variants = cached("variants")
        known = sorted(set(storage.class_sections()) | set(variants))
        c1, c2, c3 = st.columns([3, 2, 1])
        sec = c1.selectbox("Class / Section", known, index=None, accept_new_options=True)
        var = c2.selectbox("Variant", ["Variant A", "Variant B", "Unassigned"])
        if c3.button("Save", disabled=not sec):
            storage.set_variant(sec, var)
            refresh()
            st.success(f"{sec} → {var}")
            st.rerun()
        if variants:
            st.table(pd.DataFrame([{"Class/Section": k, "Variant": v} for k, v in variants.items()]))

    # ---- Research ----
    with tab_research:
        st.markdown("**Height-vs-slant misconception** across Day 8 → Day 9 → Day 30, split by image variant.")
        if items_df.empty or not (items_df.get("research_tag", pd.Series(dtype=str))
                                  == "height_vs_slant_misconception").any():
            st.info("No data yet for the tagged diagnostic items (d8_q4, d9_q3, d30_q2).")
        else:
            st.plotly_chart(charts.misconception_trend_chart(items_df, sessions), width="stretch")
            st.caption("Descriptive, not causal: small samples and non-random assignment.")

    # ---- Export ----
    with tab_export:
        if sessions.empty:
            st.info("No data yet to export.")
        else:
            st.download_button("Download sessions.csv", sessions.to_csv(index=False), "sessions.csv", "text/csv")
            st.download_button("Download item_responses.csv", items_df.to_csv(index=False),
                               "item_responses.csv", "text/csv")
            gb = sessions.pivot_table(index=["student_id", "student_name", "class_section"],
                                      columns="day", values="score_percent", aggfunc="max")
            gb.columns = [f"Day {c}" for c in gb.columns]
            st.download_button("Download gradebook (one row per student)",
                               gb.reset_index().to_csv(index=False), "gradebook.csv", "text/csv")
            st.caption("Gradebook CSV works for PowerSchool score import and manual Classroom entry.")
        if STORAGE_STATUS == "live":
            st.markdown(f"[Open the live results Google Sheet]({storage.sheet_url})")

    with tab_setup:
        setup_status_panel()

# ========================================================= ADMIN VIEW-ONLY =
elif mode == "Admin — View Only":
    st.subheader("Admin — View Only")
    st.caption("Aggregate results only — no student names, roster, export, or settings.")
    require_staff("admin")
    if not LIVE_OK:
        st.error(f"Storage: {STORAGE_MSG}")
        st.stop()
    sessions = pd.DataFrame(cached("sessions"))
    items_df = pd.DataFrame(cached("items"))
    if sessions.empty:
        st.info("No summative check results yet.")
    else:
        s = sessions.copy()
        s["score_percent"] = pd.to_numeric(s["score_percent"], errors="coerce")
        m = st.columns(3)
        m[0].metric("Tests submitted", len(s))
        m[1].metric("Students tested", s["student_id"].nunique())
        m[2].metric("Average score", f"{s['score_percent'].mean():.0f}%")
        by_class = s.groupby("class_section")["score_percent"].agg(["count", "mean"]).round(1)
        by_class.columns = ["tests", "average %"]
        st.dataframe(by_class, width="stretch")
        st.plotly_chart(charts.growth_over_time_chart(s), width="stretch")
        st.plotly_chart(charts.standards_mastery_heatmap(items_df, item_meta()), width="stretch")
        if not items_df.empty and (items_df["research_tag"] == "height_vs_slant_misconception").any():
            st.plotly_chart(charts.misconception_trend_chart(items_df, s), width="stretch")
