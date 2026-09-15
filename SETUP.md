# Summative Test Sessions — Setup Guide

This app follows the same pattern as your other MathCraft CPA day apps: it's
a standalone Streamlit app you deploy on its own, and the main launcher
(`cpamathlauncher`) just links to it. It does **not** need to live in the
same GitHub repo, though it can (as a subfolder) if that's easier for you to
manage.

## 1. Deploy the app itself

1. Push this folder to a new GitHub repo (e.g. `cpamath-summative-tests`) —
   or add it as a subfolder of `cpamathlauncher` if you'd rather keep
   everything in one place.
2. On [share.streamlit.io](https://share.streamlit.io), deploy a new app
   pointing at this repo/folder's `app.py`.
3. Note the URL Streamlit gives you (e.g.
   `https://cpamath-summative-tests.streamlit.app/`) — you'll need it for
   step 4 below (adding the link to your main launcher).

## 2. Set a teacher PIN

In the deployed app's Settings → Secrets, add:

```toml
teacher_pin = "choose-something-not-guessable"
```

Without this, the app falls back to a default PIN (`6grade`) that is **not**
private — anyone who reads this repo can see it. This PIN is a light
deterrent for a single-classroom tool, not real authentication. Once Google
Classroom's API is wired up (see step 4), swap this for real sign-in.

## 3. Set up private data storage (do this before entering any real student data)

**By default the app runs in DEMO MODE**: results are written to a local CSV
file that (a) is *not* private — anyone with server access could read it —
and (b) is *not* durable — Streamlit Community Cloud can wipe local disk on
any restart or redeploy. It's fine for testing the app yourself, but real
student names, IDs, or scores should never be entered until you've done this
step.

**Recommended: a private Google Sheet.** ~10 minutes, free, keeps data
completely outside GitHub:

1. In [Google Cloud Console](https://console.cloud.google.com/), create a
   project (or reuse one) and enable the **Google Sheets API**.
2. Create a **Service Account** (IAM & Admin → Service Accounts → Create),
   then create a JSON key for it and download it.
3. Create a new Google Sheet (just a blank one) to hold results. Share it
   with the service account's email address (looks like
   `something@your-project.iam.gserviceaccount.com`), giving it **Editor**
   access.
4. Copy the Sheet's ID from its URL:
   `https://docs.google.com/spreadsheets/d/`**`THIS_PART`**`/edit`
5. In the app's Settings → Secrets, add:

```toml
sheet_id = "paste-the-sheet-id-here"

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "...@....iam.gserviceaccount.com"
client_id = "..."
# (copy every field from the downloaded JSON key file into this table)
```

The app auto-detects this and switches out of DEMO MODE — the yellow banner
disappears and `storage.label` shows "Google Sheets (private)" in the
Teacher Portal.

Only you (and anyone you explicitly share the Sheet with) can see this data.
It never touches the public `cpamathlauncher` repo.

## 4. Rosters: Google Classroom & PowerSchool

Both systems' *live* APIs need credentials your district issues — a Google
Cloud OAuth client approved by your Chandler Park Academy Workspace admin,
and a PowerSchool API/plugin key from your SIS admin. Ask your IT
department for these when you're ready to automate roster sync; until then,
**CSV export/import works today with no approvals needed**:

- **Google Classroom:** Classroom → your class → People → the "⋮" menu →
  "Export" (or download the roster from Classroom's export tools) gives a
  CSV with student names/emails.
- **PowerSchool:** PowerSchool Admin → Student Search → select students →
  "Export" lets you choose fields (Student Number, Last/First Name, Grade,
  Section, etc.) and download as CSV.

Upload either export in the Teacher Portal's **Roster Import** tab — the app
recognizes common column-naming variants from both systems automatically.

When live API access does become available, only `roster.py`'s import
function needs to change (add a Classroom/PowerSchool API call that returns
the same canonical student list); nothing else in the app depends on how the
roster got there.

## 5. Representation-variant tracking (for the imagery/misconception research)

In the Teacher Portal's **Representation Variants** tab, map each class or
section to which version of the Day 8 parallelogram image it saw ("Variant
A" / "Variant B"). Every test session submitted by a student in that section
is tagged with that variant automatically. The **Representation Research**
tab then charts the height-vs-slant misconception rate at three checkpoints
(Day 8, Day 9, Day 30 — same diagnostic design, new numbers each time) split
by variant.

Note: this mapping currently resets when the app restarts (it lives in
session memory, not yet in the Sheets/CSV backend). Once Google Sheets
storage is configured, this is an easy follow-up to persist the same way.

## 6. FERPA reminder

- Never commit real student data to the `cpamathlauncher` GitHub repo — it's
  public.
- Don't leave the app in DEMO MODE once real students are using it.
- The teacher PIN is a deterrent, not real access control — don't rely on it
  alone once this holds real student records at scale.
