# Adding the "Summative Test Sessions" link to cpamathlauncher/app.py

This adds one featured button, styled to match your existing day cards,
placed right above the "Lessons by Day" grid so it reads as part of that
section without disrupting the day-by-day layout. Once you've deployed the
Summative Test Sessions app (see SETUP.md) and have its real URL, apply this
patch to `app.py` in the `cpamathlauncher` repo.

## 1. Add a constant near the top, right after the color constants (after `GREEN = "#3C8B5D"`, around line 15)

**Important:** this must go here, *before* the button block in step 2 uses it — not after the `DAYS` list further down, since that block runs earlier in the file than `DAYS` is defined.

```python
# URL of the standalone Summative Test Sessions app (see SETUP.md in that
# app's repo for deployment steps). Update this once it's deployed.
SUMMATIVE_TESTS_URL = "https://cpamath-summative-tests.streamlit.app/"
```

## 2. Insert this block immediately before the `st.markdown("### 📅 Lessons by Day")` line (currently line 171)

```python
st.markdown(
    f"""
    <a href="{SUMMATIVE_TESTS_URL}" target="_blank" rel="noopener noreferrer"
       style="display:block;text-align:center;background-color:{GOLD};color:white;
              font-weight:800;font-size:1.15rem;padding:1rem 1.5rem;border-radius:12px;
              text-decoration:none;margin-bottom:1.2rem;border:2px solid {GOLD};">
        📝 Open Summative Test Sessions →
    </a>
    <p style="text-align:center;color:{MUTED};font-size:0.85rem;margin-top:-0.8rem;margin-bottom:1.5rem;">
        30-day summative checks, autograded instantly, with teacher results dashboards.
    </p>
    """,
    unsafe_allow_html=True,
)
```

That's the whole change — two small additions, no edits to the existing
`DAYS` list or day-card rendering loop. The button uses your existing GOLD /
MUTED color constants so it matches the rest of the page.

## Why a separate app instead of a page inside cpamathlauncher

Every other day in `cpamathlauncher` links out to its *own* Streamlit app
(`cpamath6day5.streamlit.app`, etc.) rather than embedding that day's content
in the launcher itself. Summative Test Sessions follows that same pattern —
its own deploy, own URL, own `requirements.txt` (it needs `plotly`,
`gspread`, etc. that the launcher doesn't). This keeps the launcher itself
simple and unchanged, and means the test-sessions app can be redeployed or
updated on its own schedule without touching `cpamathlauncher` at all.
