# PM Checklist — Preventive Maintenance System

A production-ready Flask + PostgreSQL application for managing digital preventive maintenance checklists. Features include multiple checklist types with full versioning, sequential step enforcement with minimum dwell times, photo attachments with EXIF age validation, browser-local ISO 8601 timestamps, Telegram alerts with test tooling, mobile-responsive UI with theme selection, automatic photo cleanup, and corrective action sessions.

---

## Table of Contents

1. [Features](#features)
2. [Project Structure](#project-structure)
3. [Quick Start](#quick-start)
4. [Configuration](#configuration)
5. [Database Schema](#database-schema)
6. [Checklist Template Format](#checklist-template-format)
7. [Workflow](#workflow)
8. [URL Reference](#url-reference)
9. [Checklist Versioning](#checklist-versioning)
10. [Corrective Action Workflow](#corrective-action-workflow)
11. [Telegram Alerts](#telegram-alerts)
12. [Timezone Handling](#timezone-handling)
13. [Mobile Support](#mobile-support)
14. [Sequential Step Enforcement](#sequential-step-enforcement)
15. [Step Minimum Dwell Time](#step-minimum-dwell-time)
16. [Photo EXIF Validation](#photo-exif-validation)
17. [Storage Management](#storage-management)
18. [UI Themes](#ui-themes)
19. [Changelog](#changelog)

---

## Features

| Feature | Details |
|---|---|
| **Multiple checklist types** | Weekly, Monthly, Quarterly, Annual, Corrective Action — or any custom type |
| **Checklist versioning** | Upload, compare diffs, activate/archive, download any version |
| **Sequential steps** | Steps must be completed in order; skipping blocked at UI and server level |
| **Minimum dwell time** | Per-step `[min=N]` modifier enforces minimum seconds before completion |
| **Click timestamp logging** | Every tap recorded with ISO 8601 local time including UTC offset |
| **Three step types** | `STEP` (checkbox), `STEP_VALUE` (checkbox + value input), `PHOTO` (checkbox + photo) |
| **EXIF photo validation** | Photos rejected if EXIF timestamp is older than configured limit |
| **Notes** | `NOTE:` lines show as read-only informational banners |
| **DB-gated advancement** | Next Section button only enables after every step confirmed written to DB |
| **Session resume** | Returning to a session restores all completed steps, values, and photos |
| **Corrective actions** | Raise a linked corrective session mid-PM without losing main checklist progress |
| **Auto WO numbering** | Work orders auto-numbered `WO-YYYYMMDD-NNN` |
| **No duplicate sessions** | One active session per work order enforced |
| **Browser timezone** | Timestamps displayed in browser's local timezone; DB stores UTC |
| **Telegram alerts** | Startup notification, purge alerts, in-app test tool |
| **Auto photo cleanup** | Oldest photos deleted when disk usage exceeds threshold |
| **Mobile-first UI** | Hamburger nav, card-list views, fixed footer, camera capture |
| **UI themes** | 8 built-in colour themes, switched instantly without page reload |
| **Printable reports** | Full per-session audit trail |
| **Auto DB creation** | Database and all tables created on first run |
| **Live migrations** | Schema updates applied on every startup via `ADD COLUMN IF NOT EXISTS` |

---

## Project Structure

```
pm_checklist/
├── app.py                          # Flask routes, Jinja filters, startup logic
├── db.py                           # PostgreSQL — all queries, auto-create, migrations
├── checklist_parser.py             # .txt template parser (file + string modes)
├── exif_checker.py                 # EXIF timestamp extraction and age validation
├── telegram_alert.py               # Startup and purge Telegram notifications
├── storage_manager.py              # Disk monitoring and photo auto-purge
├── config.ini                      # ← All credentials and settings
├── requirements.txt                # Flask, psycopg2-binary, Werkzeug, Pillow
│
├── checklists/                     # Seed templates (auto-imported to DB on startup)
│   ├── weekly_pm.txt
│   ├── monthly_pm.txt
│   ├── quarterly_pm.txt
│   ├── annual_pm.txt
│   └── corrective_action.txt
│
├── static/
│   ├── css/
│   │   ├── style.css               # Mobile-first base stylesheet
│   │   └── themes/                 # One CSS file per theme (:root overrides only)
│   │       ├── industrial_dark.css
│   │       ├── clean_light.css
│   │       ├── midnight_navy.css
│   │       ├── forest_green.css
│   │       ├── warm_amber.css
│   │       ├── arctic_white.css
│   │       ├── crimson_steel.css
│   │       └── pastel_studio.css
│   ├── js/main.js                  # Flash auto-dismiss
│   └── uploads/                    # Photo files — session_<id>/<filename>
│
└── templates/
    ├── base.html                   # Nav, hamburger, TZ detection, theme injection
    ├── index.html                  # Dashboard
    ├── personnel.html              # Personnel management
    ├── workorders.html             # Work order management
    ├── start_session.html          # Start or resume a session
    ├── checklist.html              # Step execution, dwell timers, corrective modal
    ├── complete.html               # Session completion summary
    ├── report.html                 # Printable audit report
    ├── checklists.html             # Template library
    ├── checklist_versions.html     # Version history, upload, activate
    ├── checklist_compare.html      # Unified diff between versions
    ├── storage_status.html         # Disk usage and manual purge
    └── settings.html               # Theme picker and Telegram test tool
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 13+

### Install

```bash
pip install -r requirements.txt
```

### Configure

Edit `config.ini` — set the database password and a random `secret_key` at minimum.

### Run

```bash
python app.py
```

On first run the app will:

1. Create the `pm_checklist` database if it does not exist
2. Create all tables and indexes
3. Apply schema migrations (safe on every restart)
4. Seed `.txt` files from `checklists/` into the versioning table
5. Check disk usage and purge oldest photos if already over threshold
6. Send a Telegram startup alert (if configured)
7. Start the Flask server at `http://0.0.0.0:5000`

> **Note:** `* Restarting with stat` on startup is normal — it is Werkzeug's development server file-watcher. Set `debug = false` in `config.ini` to suppress it in production.

---

## Configuration

All settings live in `config.ini`. No credentials appear in code.

```ini
[database]
host     = localhost
port     = 5432
name     = pm_checklist        # auto-created on first run
user     = postgres
password = yourpassword

[app]
secret_key            = change-this-to-a-random-secret-key
upload_folder         = static/uploads
max_upload_mb         = 16
debug                 = true       # set false in production
port                  = 5000
host                  = 0.0.0.0
# Photos with EXIF older than this are rejected. 0 = disabled.
photo_max_age_minutes = 60
# Default theme — overridden at runtime via Settings page (stored in DB)
# Options: industrial_dark, clean_light, midnight_navy, forest_green,
#          warm_amber, arctic_white, crimson_steel, pastel_studio
theme                 = industrial_dark

[checklist]
template_dir = checklists

[telegram]
# 1. Message @BotFather on Telegram -> /newbot -> paste token below
bot_token =
# 2. Send a message to your bot, then visit:
#    https://api.telegram.org/bot<TOKEN>/getUpdates
#    Find "chat":{"id":...} and paste that number below.
#    For groups: add bot to group first. For channels: id starts with -100.
# 3. Use Settings -> Telegram in the web UI to test without restarting.
chat_id =

[storage]
disk_threshold_pct = 80
# Partition is auto-detected from the mount point where app.py resides.
```

---

## Database Schema

### `personnel`
| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | |
| `name` | TEXT | Full name |
| `badge` | TEXT UNIQUE | Employee / badge ID |
| `department` | TEXT | Optional |
| `created_at` | TIMESTAMPTZ | UTC |

### `work_orders`
| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | |
| `wo_number` | TEXT UNIQUE | Auto-generated: `WO-YYYYMMDD-NNN` |
| `equipment` | TEXT | Equipment name |
| `description` | TEXT | Optional |
| `checklist_name` | TEXT | Logical name, e.g. `quarterly_pm` |
| `status` | TEXT | `open` → `in_progress` → `completed` |
| `created_at` | TIMESTAMPTZ | UTC |
| `updated_at` | TIMESTAMPTZ | UTC |

### `pm_sessions`
| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | |
| `wo_id` | FK → work_orders | |
| `personnel_id` | FK → personnel | |
| `template_name` | TEXT | Frozen at session creation |
| `session_type` | TEXT | `planned` or `corrective` |
| `parent_session_id` | FK → pm_sessions | Set for corrective sessions |
| `issue_description` | TEXT | Out-of-control situation (corrective only) |
| `status` | TEXT | `in_progress` or `completed` |
| `started_at` | TIMESTAMPTZ | UTC |
| `completed_at` | TIMESTAMPTZ | UTC — null until done |

### `checklist_events`
| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | |
| `session_id` | FK → pm_sessions | Cascade delete |
| `section_index` | INTEGER | Zero-based |
| `step_index` | INTEGER | Zero-based within section |
| `step_key` | TEXT | `"{section}_{step}"` |
| `step_type` | TEXT | `STEP`, `STEP_VALUE`, or `PHOTO` |
| `step_label` | TEXT | Description from template |
| `checked` | BOOLEAN | Always TRUE |
| `value_input` | TEXT | Entered measurement (STEP_VALUE only) |
| `photo_path` | TEXT | Path under `static/uploads/`; NULL after auto-purge |
| `clicked_at_local` | TEXT | ISO 8601 with UTC offset from browser, e.g. `2026-05-22T14:35:07+08:00` |
| `timestamp` | TIMESTAMPTZ | UTC — exact DB write time |

### `checklist_versions`
| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | |
| `checklist_name` | TEXT | Logical name, e.g. `weekly_pm` |
| `version` | INTEGER | Auto-incremented per checklist name |
| `filename` | TEXT | Original uploaded filename |
| `content` | TEXT | Full `.txt` file content |
| `checksum` | TEXT | SHA-256 for duplicate detection |
| `notes` | TEXT | Uploader change notes |
| `uploaded_by` | TEXT | Uploader name |
| `is_active` | BOOLEAN | One active version per checklist name |
| `uploaded_at` | TIMESTAMPTZ | UTC |

### `step_dwell_events`
| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | |
| `session_id` | FK → pm_sessions | Cascade delete |
| `personnel_id` | FK → personnel | |
| `wo_id` | FK → work_orders | |
| `wo_number` | TEXT | Denormalised for analytics |
| `step_key` | TEXT | `"{section}_{step}"` |
| `section_index` | INTEGER | |
| `step_index` | INTEGER | |
| `step_label` | TEXT | Clean label (without `[min=N]`) |
| `min_seconds` | INTEGER | Configured minimum |
| `elapsed_seconds` | FLOAT | Seconds since step became active |
| `was_early` | BOOLEAN | TRUE if tapped before minimum elapsed |
| `clicked_at_local` | TEXT | ISO 8601 with UTC offset from browser |
| `tapped_at` | TIMESTAMPTZ | UTC |

### `app_settings`
| Column | Type | Notes |
|---|---|---|
| `key` | TEXT PK | e.g. `theme` |
| `value` | TEXT | e.g. `midnight_navy` |
| `updated_at` | TIMESTAMPTZ | UTC |

---

## Checklist Template Format

Templates are plain `.txt` files. Files in `checklists/` are auto-seeded into the DB on startup. Changes to existing templates must be uploaded via the Templates UI to create a new version.

### Syntax

| Prefix | Renders as |
|---|---|
| `# comment` | Ignored |
| `SECTION: Title` | Section header |
| `STEP: Description` | Checkbox only |
| `STEP: Description [min=N]` | Checkbox — locked for N seconds after becoming active |
| `STEP_VALUE: Description` | Checkbox + required text/number input |
| `STEP_VALUE: Description [min=N]` | As above, with minimum dwell time |
| `PHOTO: Description` | Checkbox + required photo upload (EXIF validated) |
| `PHOTO: Description [min=N]` | As above, with minimum dwell time |
| `NOTE: Text` | Read-only informational banner — not a step, not recorded |

The `[min=N]` modifier (N = seconds) is stripped from the displayed label. It can be added to any interactive step type.

### Example

```text
# Quarterly PM Template

SECTION: Safety & Permit

NOTE: Obtain permit-to-work before proceeding.
STEP: Lock Out / Tag Out (LOTO) applied
STEP_VALUE: Record ambient temperature (°C)
PHOTO: Photograph LOTO tags in place

SECTION: Functional Test

STEP: Power on and observe startup sequence [min=60]
STEP: Run equipment through full operating cycle [min=120]
STEP_VALUE: Record operating current at full load (A) [min=45]
```

### Validation rules (enforced on upload)

- At least one `SECTION:` required
- At least one interactive step required
- Every step keyword must have a non-empty description
- Duplicate step labels warned
- Unknown line prefixes reported with line number
- File must be valid UTF-8

---

## Workflow

### Setup

1. **Personnel** → `/personnel` — add name, badge ID, department
2. **Work Order** → `/workorders` — add equipment name, select checklist type

### Per PM run

1. **Start Session** → `/session/start` — select WO and technician
   - If the WO already has an active session, redirected to resume it
2. **Execute checklist** — one section at a time, steps in strict order:
   - `STEP` → tap the circle checkbox
   - `STEP_VALUE` → enter a value, then tap
   - `PHOTO` → capture photo (camera opens on mobile), then tap — EXIF age checked on upload
   - Steps with `[min=N]` stay locked until the countdown reaches zero
   - Every tap records an ISO 8601 local timestamp in the DB before the UI responds
   - The **Next Section** button only activates after all steps are DB-confirmed
3. **Corrective action** → tap **⚠ Corrective Action** if an issue is found mid-PM
4. **Complete** → review the summary page
5. **Report** → `/session/<id>/report` — full printable audit trail

### Returning to an in-progress session

Navigating to `/session/<id>/checklist` (no `?section=`) auto-resumes at the first incomplete section. All completed steps, values, and photo filenames are restored from the DB.

---

## URL Reference

| URL | Method | Description |
|---|---|---|
| `/` | GET | Dashboard |
| `/personnel` | GET | List personnel |
| `/personnel/add` | POST | Add a person |
| `/workorders` | GET | List work orders |
| `/workorders/add` | POST | Create WO (auto-numbered) |
| `/session/start` | GET, POST | Start or resume a session |
| `/session/<id>/checklist` | GET | Execute checklist (auto-resumes) |
| `/session/<id>/step/tap` | POST JSON | Log a tap attempt for analytics |
| `/session/<id>/step/check` | POST JSON | Record a completed step to DB |
| `/session/<id>/upload_photo` | POST multipart | Upload + EXIF-validate a photo |
| `/session/<id>/complete` | GET | Mark session complete |
| `/session/<id>/report` | GET | Printable audit report |
| `/session/<id>/corrective/start` | POST | Create linked corrective session |
| `/session/<id>/corrective/modal` | GET | AJAX data for corrective modal |
| `/checklists` | GET | Template library |
| `/checklists/<name>` | GET | Version history |
| `/checklists/<name>/upload` | POST | Upload new version |
| `/checklists/new` | POST | Upload a new checklist type |
| `/checklists/version/<id>/activate` | POST | Promote version to active |
| `/checklists/version/<id>/download` | GET | Download as `.txt` |
| `/checklists/validate` | POST multipart | AJAX validate before upload |
| `/checklists/compare` | GET | Unified diff between two versions |
| `/uploads/<path>` | GET | Serve uploaded photos |
| `/admin/storage` | GET | Disk usage dashboard |
| `/admin/storage/purge` | POST | Manual photo purge |
| `/settings` | GET, POST | Theme selection |
| `/settings/theme/<id>` | POST AJAX | Instant theme switch |
| `/settings/telegram/test` | POST | Send test message + return diagnostics |
| `/api/tz` | POST JSON | Register browser UTC offset |

---

## Checklist Versioning

- On startup, `.txt` files in `checklists/` are seeded as v1 of each checklist (idempotent via SHA-256)
- Each upload increments the version counter; duplicate content is rejected
- One version per checklist name is `is_active = TRUE`
- New sessions use the active version at creation time; existing sessions are unaffected
- Any archived version can be re-activated, downloaded, or compared

### Compare versions

Select any two versions for a colour-coded unified diff — 🟢 added, 🔴 removed, blue chunk headers.

---

## Corrective Action Workflow

An out-of-control situation found during a planned PM can be escalated into a linked corrective session without losing progress.

### Raising a corrective action

1. Tap **⚠ Corrective Action** in the section header during any planned session
2. Fill the modal: issue description (required), corrective checklist, optional technician
3. Corrective session opens immediately; main session stays `in_progress`

### During the corrective session

- Amber banner shows the issue description
- All rules apply: sequential steps, dwell timers, photo capture
- **← Return to Main** link always visible

### Built-in corrective action template (`corrective_action.txt`)

7 sections covering the complete corrective lifecycle:

| Section | Purpose |
|---|---|
| Immediate Response & Containment | LOTO, isolation, photo of defect as found |
| Situation Assessment | Failure mode, time, units affected, severity |
| Root Cause Investigation | Root cause, contributing factors, evidence |
| Corrective Repair | Parts list, repair procedure, torque values |
| Verification & Testing | Full cycle, parameters, defect confirmed resolved |
| Affected Product / Output Disposition | Conformance review, disposition, QA sign-off |
| Preventive Measures & Documentation | Recurrence prevention, CMMS update, sign-off |

---

## Telegram Alerts

Uses `parse_mode="HTML"` with HTML-escaped dynamic values. All dynamic fields (`hostname`, `equipment names`, `file paths`) are escaped with Python's `html.escape()` before sending, preventing HTTP 400 errors from special characters.

### Startup alert
```
🟢 PM Checklist — Server Started

🖥 Hostname:  myserver
🔌 Local IP:  192.168.1.50:5000
🌐 Public IP: 203.x.x.x

🔗 Access: http://192.168.1.50:5000   ← tappable
🌍 Public: http://203.x.x.x:5000     ← tappable
```

### Photo purge alert
```
🗑 PM Checklist — Auto Photo Purge

📊 Disk was at 84.2% (threshold 80%)
✅ Disk now at 71.5%
🗑 Deleted 12 photo(s) — freed 187.4 MB
📷 Remaining photos in DB: 38
```

### In-app test tool (`/settings` → Telegram section)

Enter a bot token and chat ID and click **📨 Send Test Message**. The tool:
1. Calls `getMe` to validate the token — catches typos before attempting to send
2. Sends a test message — if it fails, returns Telegram's exact error description plus a contextual hint

**Common errors and hints:**

| Error | Cause | Fix |
|---|---|---|
| `chat not found` | Bot has never received a message from that chat | Send any message to your bot in Telegram first, then get the `chat_id` from `getUpdates` |
| `bot was blocked` | User blocked the bot | Unblock in Telegram |
| `forbidden` | Bot not a member of that group/channel | Add bot to the chat |
| `unauthorized` | Invalid token | Copy exactly from @BotFather |

### Getting the correct `chat_id`

1. Message `@BotFather` → `/newbot` → copy the token
2. Send **any message** to your bot (bots cannot initiate conversations)
3. Visit `https://api.telegram.org/bot<TOKEN>/getUpdates`
4. Find `"chat":{"id": 123456789}` — that number is your `chat_id`
5. For groups: add the bot to the group, then send a message there
6. For channels: the `chat_id` starts with `-100` (e.g. `-1001234567890`)

---

## Timezone Handling

**Rule: store UTC, display browser-local.**

- All timestamp columns are `TIMESTAMPTZ` (UTC-aware)
- On every page load, JS reads `new Date().getTimezoneOffset()` and POSTs to `/api/tz`, stored in a 1-year `tz_offset` cookie
- Jinja filter `| localdt` converts UTC datetimes to browser-local for all server-rendered timestamps
- Live AJAX timestamps returned as ISO 8601 UTC strings; `window.fmtUTC()` converts client-side

### Click timestamps

The `clicked_at_local` field stores the **exact moment the technician's finger lifted** as a full ISO 8601 string with the device's UTC offset:

```
2026-05-22T14:35:07+08:00
```

This is generated by `nowLocalISO()` in the browser as the **very first line** of the click handler — before any validation, before the async fetch — ensuring it reflects the true tap time, not the server response time. Stored in both `checklist_events` and `step_dwell_events`. Displayed on the step's timestamp line after completion.

---

## Mobile Support

| Feature | Implementation |
|---|---|
| Hamburger menu | Replaces desktop nav below 640 px; closes on backdrop tap |
| Card-list views | Tables replaced by stacked cards on mobile |
| Fixed bottom footer | Prev/Next buttons anchored above browser chrome on checklist page |
| 44 px touch targets | All buttons and checkboxes meet minimum size |
| Camera capture | `PHOTO` steps use `capture="environment"` — rear camera opens directly |
| No iOS zoom | All inputs use `font-size: 1rem` |
| Scroll to next step | Newly unlocked step scrolls into view after completion |

---

## Sequential Step Enforcement

Steps within a section must be completed in strict order. Enforced at two independent layers:

**UI:** Only the next incomplete step is `step-active` (pulsing cyan ring). All subsequent steps are `step-locked` (dimmed, `disabled`, `pointer-events: none`). After DB confirmation, `unlockNextStep()` activates the next step. Tapping a locked step shakes the icon and logs the attempt to `step_dwell_events`.

**Server:** `/session/<id>/step/check` walks all steps in order. Any missing prior step causes HTTP 400 rejection.

**Breadcrumb:** Future incomplete sections are `crumb-locked` (dashed, non-clickable).

---

## Step Minimum Dwell Time

Steps can require a minimum number of seconds before the technician can complete them.

### Syntax

```text
STEP: Run equipment through full operating cycle [min=120]
STEP: Test emergency stop (E-Stop) functionality [min=30]
STEP_VALUE: Record operating current at full load (A) [min=45]
```

### Behaviour

- When a step becomes active, a countdown timer starts immediately
- The checkbox is locked until the minimum time elapses
- A live `⏱ Min. time: 47s remaining` counter pulses amber below the step
- At zero, the counter turns green and the checkbox unlocks automatically
- **Every tap is logged** regardless of timer state — early taps are recorded with `was_early = TRUE` in `step_dwell_events`
- Server enforces the minimum: `step_check` rejects submissions where `elapsed_seconds < min_seconds`

### Analytics queries

The `step_dwell_events` table enables questions such as:

- Which steps are consistently completed too quickly?
- Which technicians routinely tap before the minimum time?
- What is the average actual dwell time per step across all sessions?
- How often are locked steps tapped (sequential impatience)?

---

## Photo EXIF Validation

Every photo uploaded to a `PHOTO` step is validated against its EXIF capture timestamp to prevent submission of old or stock images.

### Decision table

| Situation | Result |
|---|---|
| EXIF found, age ≤ `photo_max_age_minutes` | ✅ Accepted |
| EXIF found, age > `photo_max_age_minutes` | ❌ Rejected with exact timestamp and age |
| EXIF timestamp in the future (clock skew) | ✅ Accepted — server warning logged |
| No EXIF (metadata stripped) | ✅ Accepted — cannot penalise legitimate devices |
| PDF file | ✅ Accepted — no EXIF concept |

### Error message

> *"Photo was taken 143 minutes ago (2026-05-17 08:22:11) — only photos taken within the last 60 minutes are accepted. Please take a new photo now."*

### Configuration

```ini
[app]
photo_max_age_minutes = 60   # 0 = disable entirely
```

---

## Storage Management

### Auto-purge

1. After every photo upload and on startup, `shutil.disk_usage()` checks the partition where `app.py` resides
2. **Partition auto-detected** — `get_app_partition()` walks the directory tree comparing `os.stat().st_dev` until the mount-point boundary is found; works correctly with SD cards, external drives, separate `/home` partitions
3. If usage ≥ `disk_threshold_pct`, oldest photos (by `timestamp ASC`) are deleted from disk; `photo_path` set to `NULL` in the DB
4. Purging continues until usage drops below `threshold − 5%` or no photos remain
5. Telegram purge alert sent with per-file detail (up to 10 paths listed)

### `/admin/storage` status page

- Visual disk usage bar (green → amber → red)
- Total / used / free GB, detected partition path
- Photo file count vs DB record count
- Manual purge button (confirmation required)

### Key design decisions

- Atomic per file: DB only updated after the file is confirmed deleted
- `photo_path` set to `NULL`, not the row deleted — event history preserved
- `freed_human` and all dynamic values HTML-escaped before Telegram message

---

## UI Themes

8 built-in themes, selectable from **Settings** in the navigation. Switches instantly — no page reload.

| Theme | Style | Accent |
|---|---|---|
| Industrial Dark | Default — dark, utilitarian | `#00c8ff` |
| Clean Light | White background, professional | `#2563eb` |
| Midnight Navy | Deep navy | `#7c6af7` |
| Forest Green | Dark green | `#4ade80` |
| Warm Amber | Brown tones | `#f59e0b` |
| Arctic White | Cool white | `#0ea5e9` |
| Crimson Steel | Near-black, red | `#ef4444` |
| Pastel Studio | Dark purple, lavender | `#c084fc` |

### How it works

- Each theme is a single CSS file in `static/css/themes/` overriding only `:root` variables
- Active theme stored in `app_settings` DB table; survives restarts
- `base.html` injects `<link id="theme-css">` dynamically on every page
- Clicking a swatch POSTs to `/settings/theme/<id>` via AJAX; `<link>` href swapped in-place

### Adding a custom theme

1. Create `static/css/themes/mytheme.css` with a `:root { }` block
2. Add one entry to the `THEMES` dict in `app.py`
3. Restart — it appears immediately on the Settings page

---

## Changelog

### v1.0 — Initial Release
- Flask + PostgreSQL with auto DB/table creation
- Single `.txt` checklist template; three step types: `STEP`, `STEP_VALUE`, `PHOTO`
- Personnel and work order management
- PM session tracking, section-by-section execution with DB-gated Next button
- Photo uploads to `static/uploads/`; printable per-session audit report
- Separate `config.ini` for all settings

### v1.1 — Auto WO Number & Duplicate Session Guard
- WO numbers auto-generated: `WO-YYYYMMDD-NNN` (daily sequence)
- Blocks duplicate active sessions per WO
- Start Session page shows inline warning and Resume when WO has active session
- Work Orders list shows pulsing **LIVE** badge

### v1.2 — Multiple Checklist Types
- `config.ini` `[checklist]` changed from `template_file` to `template_dir`
- Four built-in templates: weekly, monthly, quarterly, annual
- `work_orders` gains `checklist_name` column (auto-migrated)
- WO creation includes checklist type dropdown
- Checklist name frozen on each session at creation time

### v1.3 — Browser Timezone
- All timestamps stored as `TIMESTAMPTZ` (UTC)
- Browser UTC offset detected on every page load, stored in `tz_offset` cookie
- Jinja filter `| localdt` converts UTC to browser-local for all server-rendered timestamps
- Live AJAX timestamps returned as ISO 8601 strings, converted client-side with `window.fmtUTC()`

### v1.4 — Telegram Startup Alert
- New `telegram_alert.py` (stdlib only)
- Startup message: hostname, local IP, public IP, clickable HTML links
- `parse_mode="HTML"` for reliable link rendering
- Silently skipped if credentials blank

### v1.5 — Mobile-Friendly UI
- Full CSS rewrite: mobile-first, 640 px and 380 px breakpoints
- Hamburger nav, card-list views replacing tables, fixed bottom footer on checklist page
- 44 × 44 px minimum touch targets; `capture="environment"` for direct camera access
- `font-size: 1rem` on all inputs to prevent iOS auto-zoom

### v1.6 — Sequential Step Enforcement
- Steps must be completed in strict order
- CSS states: `step-done`, `step-active` (pulsing), `step-locked` (dimmed, disabled)
- Server-side guard in `step_check` rejects out-of-order submissions with HTTP 400
- Future section breadcrumb crumbs rendered non-clickable

### v1.7 — Session Resume / Progress Restore
- Auto-redirect to first incomplete section when no `?section=` in URL
- Completed `STEP_VALUE` inputs re-rendered with stored values
- Photo steps show original filename; timestamps show exact recorded time
- `uploadedPhotos` JS dict pre-populated from DB events

### v1.8 — Checklist Versioning
- New `checklist_versions` DB table: full content, SHA-256, version number, active flag
- `parse_template_from_string()` — parses from DB content
- `validate_template()` — returns errors before upload; AJAX validation with live preview
- Unified diff with colour-coded rendering
- Version activation: atomic promotion; previous demoted immediately
- **Bugfix:** `RealDictCursor.fetchone()[0]` `KeyError` — scalar queries use plain cursor

### v1.9 — Automatic Photo Cleanup
- New `storage_manager.py` — disk monitoring and purge
- `config.ini` gains `[storage]` section
- Purge triggered after every upload and at startup
- `photo_path` set to `NULL` in DB (event row preserved)
- Telegram purge alert; `/admin/storage` page with manual purge button

### v1.10 — UI Themes & Settings Page
- 8 built-in themes in `static/css/themes/`
- New `app_settings` DB table for runtime settings
- Instant theme switching via AJAX — no page reload
- Settings page with 8 visual swatch cards
- **Bugfix:** context processor wrapped in `try/except` for DB-not-ready resilience

### v1.11 — Corrective Action Sessions
- `pm_sessions` gains `session_type`, `parent_session_id`, `issue_description` (all auto-migrated)
- **⚠ Corrective Action** button in section header opens a modal
- Corrective session runs independently; parent stays `in_progress`
- Amber banner, chip bar, completion summary, audit report integration
- New seed template `corrective_action.txt` — 7 sections, full corrective lifecycle

### v1.12 — EXIF Photo Age Validation
- New `exif_checker.py` — Pillow-based EXIF extraction
- `Pillow>=10.0.0` added to `requirements.txt`
- Photos with EXIF older than `photo_max_age_minutes` rejected before saving
- No-EXIF and PDF files allowed through; future timestamps (clock skew) allowed
- `photo_max_age_minutes = 0` disables check entirely

### v1.13 — Step Minimum Dwell Time
- `[min=N]` modifier on any step type (N = seconds)
- Parser strips modifier from displayed label; adds `min_seconds` to step dict
- Client-side countdown timer; button locked until zero; auto-unlocks
- Server-side enforcement in `step_check`
- New `step_dwell_events` DB table: every tap logged with session, personnel, WO, step, elapsed time, `was_early`, `clicked_at_local`
- Tapping a sequentially locked step also logged (shakes icon, silently POSTs to `step/tap`)

### v1.14 — ISO 8601 Local Click Timestamps
- `nowLocalISO()` JS function: `new Date()` with `getTimezoneOffset()` → full ISO 8601 with UTC offset, e.g. `2026-05-22T14:35:07+08:00`
- Captured as the **first line** of every click handler — reflects exact finger-lift moment
- Sent in both `step/tap` and `step/check` JSON bodies as `clicked_at_local`
- Stored in `checklist_events.clicked_at_local` and `step_dwell_events.clicked_at_local` (both columns auto-migrated)
- Displayed on the step timestamp line after completion — preferred over server-derived UTC
- Telegram HTML-escaping fixed: all dynamic values escaped with `html.escape()` preventing HTTP 400 from special characters in hostnames, equipment names, or file paths
- Telegram error logging improved: `HTTPError.read()` parsed for Telegram's exact `description` field
- In-app Telegram test tool on Settings page: validates token via `getMe`, sends test message, returns exact error + contextual hint (chat not found, blocked, forbidden, bad token)
