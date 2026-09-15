"""MathCraft CPA — Summative Test Sessions

A standalone Streamlit app (same deployment pattern as the other MathCraft CPA
day apps) with two modes:
  - Student: take today's summative check, get autograded instantly.
  - Teacher Portal (PIN-gated): roster import, autograded results, and
    i-Ready-"Inform"-style dashboards — score distributions, standards
    mastery, item difficulty, growth over time, plus a dedicated chart for
    the representation/misconception research thread.

See SETUP.md before using this with real students: by default this runs in
DEMO MODE (local CSV, not private, not durable) until Google Sheets storage
is configured.
"""
import os
import sys
import streamlit as st
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from content.loader import load_all_days, available_days  # noqa: E402
from grading import grade_session  # noqa: E402
from storage import get_storage, SessionRecord  # noqa: E402
import roster as roster_mod  # noqa: E402
import charts  # noqa: E402

st.set_page_config(page_title="MathCraft CPA — Summative Test Sessions", page_icon="📝", layout="wide")

NAVY = "#1F3864"
GOLD = "#B08D57"

# ---------------------------------------------------------------- storage ---
storage, is_demo = get_storage(st.secrets if hasattr(st, "secrets") else None)

st.markdown(
    f"""
    <div style="background:linear-gradient(135deg,{NAVY} 0%, #142544 100%);
                color:white;padding:1.6rem 2rem;border-radius:14px;
                border-bottom:6px solid {GOLD};margin-bottom:1rem;">
        <h1 style="margin:0;">📝 MathCraft CPA — Summative Test Sessions</h1>
        <p style="margin:0.3rem 0 0 0;opacity:0.9;">Chandler Park Academy · Grade 6 Mathematics</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if is_demo:
    st.warning(
        "**DEMO MODE** — results are being saved to a temporary local file, not a "
        "private, durable store. Do **not** enter real students' names or IDs until "
        "Google Sheets storage is configured (see SETUP.md). Streamlit Community "
        "Cloud's local disk can be wiped at any time.",
        icon="⚠️",
    )

ALL_DAYS = load_all_days()
DAY_NUMS = available_days()

mode = st.sidebar.radio(
    "Mode",
    ["Study Guide", "Student — Take a Test", "Teacher Portal", "Admin — View Only"],
)

# ========================================================= STUDY GUIDE =====
if mode == "Study Guide":
    st.subheader("📚 Study Guide — What to Practice on IXL, and When")
    st.write(
        "Every summative check below is tied to specific IXL skills. You don't have "
        "to wait for a test to show up — pick any day, click through to IXL, and start "
        "practicing weeks or even months ahead of that test date."
    )

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
            day_data = ALL_DAYS[d]
            prep = day_data.get("ixl_prep") or []
            with st.container(border=True):
                st.markdown(f"**Day {d} — {day_data['title']}**")
                standards = ", ".join(day_data.get("standards", []))
                if standards:
                    st.caption(f"Standards: {standards}")
                if prep:
                    st.markdown("Practice on IXL before this test:")
                    for skill in prep:
                        st.markdown(f"- [{skill['label']}]({skill['url']})")
                else:
                    st.caption(day_data.get("ixl_prep_note", "No single IXL skill maps directly to this day."))
        st.markdown("")

    st.info(
        "This page is intentionally open — no PIN required — so students and "
        "families can plan study time around it without needing to log in.",
        icon="🗓️",
    )

# ============================================================== STUDENT ====
if mode == "Student — Take a Test":
    st.subheader("Start a Summative Check")

    col1, col2, col3 = st.columns(3)
    with col1:
        student_name = st.text_input("Student name")
    with col2:
        student_id = st.text_input("Student ID (optional)")
    with col3:
        class_section = st.text_input("Class / Section", placeholder="e.g., Period 2")

    day = st.selectbox("Which day's summative check?", DAY_NUMS,
                        format_func=lambda d: f"Day {d} — {ALL_DAYS[d]['title']}")

    day_data = ALL_DAYS[day]
    st.caption(f"Standards: {', '.join(day_data.get('standards', []))}")

    if not student_name or not class_section:
        st.info("Enter your name and class/section above to begin.")
    else:
        responses = {}
        with st.form("test_form"):
            for i, item in enumerate(day_data["items"], start=1):
                st.markdown(f"**{i}. {item['prompt']}**")
                if item["type"] == "multiple_choice":
                    labels = [f"{k}. {v}" for k, v in item["choices"].items()]
                    choice = st.radio("Select one:", labels, key=item["id"], index=None, label_visibility="collapsed")
                    responses[item["id"]] = choice.split(".")[0] if choice else None
                elif item["type"] == "numeric_entry":
                    val = st.text_input("Your answer (number):", key=item["id"])
                    responses[item["id"]] = val
                elif item["type"] == "short_answer":
                    val = st.text_input("Your answer:", key=item["id"])
                    responses[item["id"]] = val
                st.markdown("---")

            submitted = st.form_submit_button("Submit Summative Check", type="primary")

        if submitted:
            graded = grade_session(day_data["items"], responses)

            variant = storage.__dict__.get("_class_variant", {}).get(class_section, "Unassigned") \
                if hasattr(storage, "__dict__") else "Unassigned"

            session = SessionRecord(
                student_id=student_id or student_name,
                student_name=student_name,
                class_section=class_section,
                representation_variant=variant,
                day=day,
                day_title=day_data["title"],
                score_correct=graded["score_correct"],
                score_total=graded["score_total"],
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

            st.success(f"Score: {graded['score_correct']} / {graded['score_total']}  ({graded['score_percent']}%)")
            st.progress(min(graded["score_percent"] / 100, 1.0))

            with st.expander("Review your answers"):
                for item in day_data["items"]:
                    r = graded["results"][item["id"]]
                    icon = "✅" if r["correct"] else "❌"
                    st.markdown(f"{icon} **{item['prompt']}**")
                    st.caption(f"Your answer: {r['given']}  |  Correct answer: {r['expected']}")
                    st.caption(item.get("rationale", ""))

# ========================================================= TEACHER PORTAL ==
elif mode == "Teacher Portal":
    st.subheader("Teacher Portal")

    configured_pin = None
    try:
        configured_pin = st.secrets.get("teacher_pin")
    except Exception:
        pass
    configured_pin = configured_pin or "6grade"  # change this in secrets.toml for real use

    pin = st.text_input("Teacher PIN", type="password")
    if pin != configured_pin:
        st.info("Enter the teacher PIN to view rosters and results. "
                 "This PIN is a light deterrent, not real security — set your own in "
                 "`.streamlit/secrets.toml` (`teacher_pin = \"...\"`) and swap in Google "
                 "Classroom sign-in once that integration is live (see SETUP.md).")
        st.stop()

    st.caption(f"Storage backend: **{storage.label}**")

    tab_roster, tab_variants, tab_results, tab_research, tab_export = st.tabs(
        ["📋 Roster Import", "🎨 Representation Variants", "📊 Results Dashboard",
         "🔬 Representation Research", "⬇️ Export Data"]
    )

    # ---- Roster import ----
    with tab_roster:
        st.markdown(
            "Upload a class roster exported as CSV from **Google Classroom** or "
            "**PowerSchool**. Column names don't need to match exactly — common "
            "variants (Student ID / Student_Number, First Name / First_Name, etc.) "
            "are recognized automatically."
        )
        uploaded = st.file_uploader("Roster CSV", type=["csv"])
        if uploaded:
            students = roster_mod.parse_roster_csv(uploaded.getvalue())
            unmapped = roster_mod.unmapped_columns_warning(uploaded.getvalue())
            st.success(f"Parsed {len(students)} students.")
            st.dataframe(pd.DataFrame(students))
            if unmapped:
                st.caption(f"Columns not recognized (ignored): {', '.join(unmapped)}")

    # ---- Representation variant mapping ----
    with tab_variants:
        st.markdown(
            "For the representation-in-imagery research: tell the app which "
            "instructional image variant each class/section saw for the Day 8 "
            "parallelogram lesson. This gets attached to every test session from "
            "that section automatically, so results can be compared by variant "
            "later without re-entering anything per student."
        )
        if "class_variant" not in st.session_state:
            st.session_state.class_variant = {}
        sec = st.text_input("Class / Section name", key="variant_section_input")
        variant = st.selectbox("Image variant shown to this class",
                                ["Variant A", "Variant B", "Unassigned"], key="variant_choice_input")
        if st.button("Save mapping"):
            st.session_state.class_variant[sec] = variant
            storage.__dict__["_class_variant"] = st.session_state.class_variant
            st.success(f"{sec} → {variant}")
        if st.session_state.class_variant:
            st.table(pd.DataFrame(
                [{"Class/Section": k, "Variant": v} for k, v in st.session_state.class_variant.items()]
            ))
        st.caption(
            "Note: this mapping currently lives in the app's session memory and resets "
            "when the app restarts. Once Google Sheets storage is configured (SETUP.md), "
            "this can be persisted the same way test results are."
        )

    # ---- Results dashboard ----
    with tab_results:
        sessions = pd.DataFrame(storage.load_sessions())
        items_df = pd.DataFrame(storage.load_item_responses())

        if sessions.empty:
            st.info("No summative check results yet. Once students submit, results appear here.")
        else:
            day_choice = st.selectbox("Day", sorted(sessions["day"].astype(int).unique()),
                                       format_func=lambda d: f"Day {d} — {ALL_DAYS.get(d, {}).get('title', '')}")
            c1, c2 = st.columns(2)
            with c1:
                st.plotly_chart(charts.score_distribution_chart(sessions, day_choice), use_container_width=True)
            with c2:
                st.plotly_chart(charts.item_difficulty_chart(items_df, day_choice), use_container_width=True)

            st.plotly_chart(charts.growth_over_time_chart(sessions), use_container_width=True)

            item_meta = {}
            for d, day_data in ALL_DAYS.items():
                for item in day_data["items"]:
                    item_meta[item["id"]] = {"standard": ",".join(day_data.get("standards", [])) or "Unassigned"}
            st.plotly_chart(charts.standards_mastery_heatmap(items_df, item_meta), use_container_width=True)

    # ---- Representation research chart ----
    with tab_research:
        st.markdown(
            "Tracks the **height-vs-slant misconception** (Day 8 → Day 9 → Day 30 "
            "diagnostic items, same numbers-different-day design) split by which "
            "representation-image variant each class saw. A falling line means the "
            "misconception is fading for that group; comparing slopes across variants "
            "is the actual research signal for whether representation is a factor in "
            "closing this gap."
        )
        sessions = pd.DataFrame(storage.load_sessions())
        items_df = pd.DataFrame(storage.load_item_responses())
        if items_df.empty or "research_tag" not in items_df.columns or \
           not (items_df["research_tag"] == "height_vs_slant_misconception").any():
            st.info("No data yet for the tagged diagnostic items (d8_q4, d9_q3, d30_q2).")
        else:
            st.plotly_chart(
                charts.misconception_trend_chart(items_df, sessions), use_container_width=True
            )
            st.caption(
                "⚠️ Read this descriptively, not causally: classroom sample sizes are small "
                "and sections aren't randomly assigned to a variant, so treat differences as "
                "a hypothesis to investigate further, not proof."
            )

    # ---- Export ----
    with tab_export:
        sessions = pd.DataFrame(storage.load_sessions())
        items_df = pd.DataFrame(storage.load_item_responses())
        if not sessions.empty:
            st.download_button("Download sessions.csv", sessions.to_csv(index=False),
                                file_name="sessions.csv", mime="text/csv")
        if not items_df.empty:
            st.download_button("Download item_responses.csv", items_df.to_csv(index=False),
                                file_name="item_responses.csv", mime="text/csv")
        if sessions.empty and items_df.empty:
            st.info("No data yet to export.")

# ========================================================= ADMIN VIEW-ONLY =
if mode == "Admin — View Only":
    st.subheader("Admin — View Only")
    st.caption(
        "Aggregate results only (no student names, no roster, no export, no settings) — "
        "for CPA administrators who need visibility into cohort performance without "
        "access to individual student records or the ability to change anything."
    )

    configured_admin_pin = None
    try:
        configured_admin_pin = st.secrets.get("admin_pin")
    except Exception:
        pass
    configured_admin_pin = configured_admin_pin or "cpaview"  # change this in secrets.toml

    admin_pin = st.text_input("Admin PIN", type="password", key="admin_pin_input")
    if admin_pin != configured_admin_pin:
        st.info(
            "Enter the admin PIN to view cohort-level results. Set your own in "
            "`.streamlit/secrets.toml` (`admin_pin = \"...\"`) — use a **different** PIN "
            "from the teacher PIN, since this role is meant to be more restricted, not "
            "just another copy of teacher access."
        )
        st.stop()

    sessions = pd.DataFrame(storage.load_sessions())
    items_df = pd.DataFrame(storage.load_item_responses())

    if sessions.empty:
        st.info("No summative check results yet.")
    else:
        st.plotly_chart(charts.growth_over_time_chart(sessions), use_container_width=True)
        item_meta = {}
        for d, day_data in ALL_DAYS.items():
            for item in day_data["items"]:
                item_meta[item["id"]] = {"standard": ",".join(day_data.get("standards", [])) or "Unassigned"}
        st.plotly_chart(charts.standards_mastery_heatmap(items_df, item_meta), use_container_width=True)

        if not items_df.empty and "research_tag" in items_df.columns and \
           (items_df["research_tag"] == "height_vs_slant_misconception").any():
            st.plotly_chart(charts.misconception_trend_chart(items_df, sessions), use_container_width=True)

    with st.expander("How parents see results (Google Classroom & PowerSchool)"):
        st.markdown(
            "This app is a place to **administer and autograde** the summative checks — "
            "it is not where parents log in. Parents already have accounts in Classroom "
            "and PowerSchool, so the plan is to make scores show up **there**, not to add "
            "a third portal:\n\n"
            "- **Google Classroom:** once a score exists here, it gets entered as a grade "
            "on the matching Classroom assignment. Any parent already registered as a "
            "*Guardian* on that student's Classroom account automatically gets Classroom's "
            "own weekly email summary of grades — nothing new to build for parents "
            "specifically, as long as scores are posted to Classroom.\n"
            "- **PowerSchool:** same idea — once posted to a PowerSchool gradebook "
            "assignment, it shows up in the PowerSchool Parent Portal parents already use.\n\n"
            "**Today:** scores can be exported from the Teacher Portal's Export tab and "
            "entered into Classroom/PowerSchool by hand, or via PowerSchool's bulk score "
            "import if your school's instance supports it (confirm the exact import path "
            "with your SIS admin — it varies by district configuration).\n\n"
            "**Later:** automatic posting needs the same district-issued API credentials "
            "as roster sync (Google Cloud OAuth client + PowerSchool API/plugin key) — "
            "once those exist, this export step goes away and scores post automatically."
        )
