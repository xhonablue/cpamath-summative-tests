# Summative Test Sessions — Launch Guide (Live)

The app is **live-only**: there is no demo mode. Until secure storage is
connected, students see "Testing opens as soon as your teacher finishes
setup" and nothing is recorded. Every step below is done once.

Open your app on [share.streamlit.io](https://share.streamlit.io) →
**⋮ → Settings → Secrets**. A full template is in
`secrets_template.toml`.

---

## Step 1 — Private results Google Sheet (REQUIRED, ~10 min)

1. [Google Cloud Console](https://console.cloud.google.com/) → create a project
   (e.g. `cpa-summative`).
2. **APIs & Services → Library** → enable **Google Sheets API**
   (and **Google Classroom API** if you plan to do Step 4).
3. **IAM & Admin → Service Accounts → Create**. Name it `cpa-summative`.
   Open it → **Keys → Add key → JSON**. A file downloads.
4. Create a blank Google Sheet named **CPA Summative Results — PRIVATE**.
   **Share** it with the service account email
   (`…@….iam.gserviceaccount.com`) as **Editor**.
5. Copy the Sheet ID from its URL: `docs.google.com/spreadsheets/d/`**`ID`**`/edit`
6. In Secrets, paste:
   ```toml
   sheet_id = "THE-ID"

   [gcp_service_account]
   # one line per field from the downloaded JSON file
   type = "service_account"
   project_id = "..."
   private_key_id = "..."
   private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
   client_email = "...@....iam.gserviceaccount.com"
   client_id = "..."
   token_uri = "https://oauth2.googleapis.com/token"
   ```
7. Save. The red "Setup required" banner disappears. The app creates the tabs
   `sessions`, `item_responses`, `roster`, `class_variants`, `classroom_links`
   inside the sheet automatically.

## Step 2 — Staff access (REQUIRED)

```toml
teacher_pin = "something-only-you-know"
admin_pin   = "a-different-pin-for-administrators"
app_url     = "https://cpamath-summative-tests.streamlit.app/"
```
Without these the Teacher Portal and Admin view stay locked.

## Step 3 — "Sign in with Google" (RECOMMENDED, ~10 min)

Students sign in with their school account — no typed names, no impersonation,
and their class fills in from the roster.

1. Cloud Console → **APIs & Services → OAuth consent screen** → User type
   **Internal** (keeps sign-in to your school domain) → fill app name and your email.
2. **Credentials → Create credentials → OAuth client ID → Web application**.
   Authorized redirect URI:
   `https://cpamath-summative-tests.streamlit.app/oauth2callback`
3. Add to Secrets:
   ```toml
   teacher_emails = ["you@your-school-domain"]
   admin_emails   = ["principal@your-school-domain"]
   student_email_domain = "your-student-domain"   # optional

   [auth]
   redirect_uri = "https://cpamath-summative-tests.streamlit.app/oauth2callback"
   cookie_secret = "any-long-random-string"
   client_id = "....apps.googleusercontent.com"
   client_secret = "..."
   server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
   ```
When `teacher_emails` / `admin_emails` are set, staff sign in with Google instead of PINs.

## Step 4 — Google Classroom

**Works immediately (no approval):** Teacher Portal → **🏫 Google Classroom**
lists all 30 days. Each has a direct link (`…streamlit.app/?day=8` opens
straight to Day 8) and a **Post to Classroom** button that opens Classroom's
official share window — choose your class and it creates the assignment.

**Full API sync (needs your Workspace admin once):** pull rosters, create
assignments, and push scores into Classroom grades (guardians see them in
their Classroom summaries).
1. Enable **Google Classroom API** in the same Cloud project.
2. Send your Workspace admin the service account's **Client ID** (numeric,
   on the service account page) and ask them to add it at
   **admin.google.com → Security → Access and data control → API controls →
   Domain-wide delegation** with these scopes:
   ```
   https://www.googleapis.com/auth/classroom.courses.readonly,https://www.googleapis.com/auth/classroom.rosters.readonly,https://www.googleapis.com/auth/classroom.profile.emails,https://www.googleapis.com/auth/classroom.coursework.students
   ```
3. Add to Secrets: `classroom_delegated_user = "you@your-school-domain"`
4. Teacher Portal → Google Classroom → pick a course → **Import roster**,
   **Create in Classroom**, then **Sync grades now** after students test.
   (Classroom only allows grade sync on assignments the app created.)

## Step 5 — Launcher link on cpamath.org / cpamathlauncher

The launcher button is in PR #4 of `xhonablue-source/cpamathlauncher`
(see LAUNCHER_PATCH.md). On cpamath.org (GoDaddy), add a button linking to
`https://cpamath-summative-tests.streamlit.app/`.

## Options

| Secret | Effect |
|---|---|
| `allow_retakes = true` | Students may retake a day (default: one attempt; the best score syncs to Classroom). |
| `dev_mode = true` | Local CSV for development only. Never use with real students. |

## Verify the launch

Teacher Portal → **⚙️ Setup & Status** shows a green checklist for storage,
access, sign-in, Classroom, and roster. Take one test yourself using
`?day=1`, confirm the row appears in the Sheet, then share links.

## FERPA

- The GitHub repo is public: code and question bank only. Never commit
  `secrets.toml`, rosters, or results (they're git-ignored).
- The results Sheet is shared only with the service account and staff you choose.
- Admin view shows aggregate data only.
