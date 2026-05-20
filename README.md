# PM Checklist — Preventive Maintenance System

A production-ready Flask + PostgreSQL application for managing digital preventive maintenance checklists. Supports multiple checklist types with full versioning, sequential step enforcement, photo attachments with EXIF age validation, browser-local timestamps, Telegram alerts, mobile-responsive UI with theme selection, automatic photo cleanup, and corrective action sessions.

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
15. [Photo EXIF Validation](#photo-exif-validation)
16. [Storage Management](#storage-management)
17. [UI Themes](#ui-themes)
18. [Changelog](#changelog)

---

## Features

| Feature | Details |
|---|---|
| **Multiple checklist types** | Weekly, Monthly, Quarterly, Annual, Corrective Action — or any custom type |
| **Checklist versioning** | Upload new versions, compare diffs, activate/archive, download |
| **Sequential steps** | Steps must be completed in order; skipping blocked at UI and server level |
| **Three step types** | `STEP` (checkbox), `STEP_VALUE` (checkbox + value input), `PHOTO` (checkbox + photo upload) |
| **EXIF photo validation** | Photos rejected if EXIF timestamp is older than configured limit (default 60 min) |
| **Notes** | `NOTE:` lines display as read-only informational banners |
| **DB-gated advancement** | Next Section button only enables after every step confirmed written to DB |
| **Session resume** | Returning to an in-progress session restores all completed steps, values, and photo filenames |
| **Corrective actions** | Raise a linked corrective session mid-PM without losing progress on the main checklist |
| **Auto WO numbering** | Work order numbers auto-generated as `WO-YYYYMMDD-NNN` |
| **No duplicate sessions** | Only one active session allowed per work order |
| **Browser timezone** | All timestamps displayed in browser's local timezone; DB stores UTC |
| **Telegram alerts** | Startup notification and auto-purge alerts with clickable links |
| **Auto photo cleanup** | Oldest photos deleted automatically when disk usage exceeds configured threshold |
| **Mobile-first UI** | Hamburger nav, card-list views, fixed bottom footer, camera capture for photos |
| **UI themes** | 8 built-in colour themes, selectable live without page reload |
| **Printable reports** | Full per-session audit trail with values, timestamps, photo links, corrective actions |
| **Auto DB creation** | Database and all tables created automatically on first run |
| **Live migrations** | Schema updates applied via `ALTER TABLE … ADD COLUMN IF NOT EXISTS` on every startup |

---

## Project Structure

```
pm_checklist/
├── app.py                          # Flask routes, Jinja filters, startup logic
├── db.py                           # All PostgreSQL logic, auto-DB/table creation
├── checklist_parser.py             # .txt template parser (file and string modes)
├── exif_checker.py                 # EXIF timestamp extraction and age validation
├── telegram_alert.py               # Startup and purge Telegram notifications
├── storage_manager.py              # Disk monitoring and photo auto-purge
├── config.ini                      # ← All credentials and settings here
├── requirements.txt                # Flask, psycopg2-binary, Werkzeug, Pillow
│
├── checklists/                     # Seed .txt templates (auto-imported to DB on startup)
│   ├── weekly_pm.txt
│   ├── monthly_pm.txt
│   ├── quarterly_pm.txt
│   ├── annual_pm.txt
│   └── corrective_action.txt
│
├── static/
│   ├── css/
│   │   ├── style.css               # Full mobile-first base stylesheet
│   │   └── themes/                 # One CSS file per theme (overrides :root variables only)
│   │       ├── industrial_dark.css
│   │       ├── clean_light.css
│   │       ├── midnight_navy.css
│   │       ├── forest_green.css
│   │       ├── warm_amber.css
│   │       ├── arctic_white.css
│   │       ├── crimson_steel.css
│   │       └── pastel_studio.css
│   ├── js/main.js                  # Flash auto-dismiss
│   └── uploads/                    # Photo files (session_<id>/<filename>)
│
└── templates/
    ├── base.html                   # Nav, hamburger, TZ detection, theme injection
    ├── index.html                  # Dashboard
    ├── personnel.html              # Personnel management
    ├── workorders.html             # Work order management
    ├── start_session.html          # Start or resume a PM session
    ├── checklist.html              # Step-by-step execution + corrective action modal
    ├── complete.html               # Session completion summary
    ├── report.html                 # Printable audit report
    ├── checklists.html             # Checklist template library
    ├── checklist_versions.html     # Version history, upload, activate
    ├── checklist_compare.html      # Unified diff between versions
    ├── storage_status.html         # Disk usage dashboard
    └── settings.html               # UI theme picker
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

Edit `config.ini` — at minimum set the database password and a random `secret_key`.

### Run

```bash
python app.py
```

On first run the app will:
1. Create the `pm_checklist` database if it does not exist
2. Create all tables and indexes
3. Run schema migrations (safe to re-run on every start)
4. Seed `.txt` files from `checklists/` into the versioning table
5. Check disk usage and purge oldest photos if already over threshold
6. Send a Telegram startup alert (if configured)
7. Start the Flask server at `http://0.0.0.0:5000`

---

## Configuration

All settings live in `config.ini`. No credentials appear in code.

```ini
[database]
host     = localhost
port     = 5432
name     = pm_checklist        # auto-created if missing
user     = postgres
password = yourpassword

[app]
secret_key            = change-this-to-a-random-secret-key
upload_folder         = static/uploads
max_upload_mb         = 16
debug                 = true
port                  = 5000
host                  = 0.0.0.0
# Photos with EXIF older than this are rejected. 0 = disabled.
photo_max_age_minutes = 60
# Default theme — overridden at runtime via Settings page, stored in DB
# Options: industrial_dark, clean_light, midnight_navy, forest_green,
#          warm_amber, arctic_white, crimson_steel, pastel_studio
theme                 = industrial_dark

[checklist]
template_dir = checklists

[telegram]
bot_token =    # from @BotFather
chat_id   =    # from @userinfobot or getUpdates

[storage]
disk_threshold_pct = 80
# Partition auto-detected from mount point where app.py resides — no config needed
```

**Getting Telegram credentials:**
1. Message `@BotFather` → `/newbot` → copy the token
2. Message your bot, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates` for the `chat_id`

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
| `checklist_name` | TEXT | Logical checklist name, e.g. `quarterly_pm` |
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
| `issue_description` | TEXT | Out-of-control situation description (corrective only) |
| `status` | TEXT | `in_progress` or `completed` |
| `started_at` | TIMESTAMPTZ | UTC |
| `completed_at` | TIMESTAMPTZ | UTC, null until done |

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
| `photo_path` | TEXT | Relative path under `static/uploads/`; NULL after auto-purge |
| `timestamp` | TIMESTAMPTZ | UTC — exact DB write time |

### `checklist_versions`
| Column | Type | Notes |
|---|---|---|
| `id` | SERIAL PK | |
| `checklist_name` | TEXT | Logical name, e.g. `weekly_pm` |
| `version` | INTEGER | Auto-incremented per checklist name |
| `filename` | TEXT | Original uploaded filename |
| `content` | TEXT | Full `.txt` file content |
| `checksum` | TEXT | SHA-256 (duplicate detection) |
| `notes` | TEXT | Uploader change notes |
| `uploaded_by` | TEXT | Uploader name |
| `is_active` | BOOLEAN | One active version per checklist name |
| `uploaded_at` | TIMESTAMPTZ | UTC |

### `app_settings`
| Column | Type | Notes |
|---|---|---|
| `key` | TEXT PK | Setting identifier, e.g. `theme` |
| `value` | TEXT | Setting value, e.g. `midnight_navy` |
| `updated_at` | TIMESTAMPTZ | UTC |

---

## Checklist Template Format

Templates are plain `.txt` files editable in any text editor. Files in `checklists/` are auto-seeded into the DB on startup. Subsequent changes must be uploaded via the Templates UI.

### Syntax

| Prefix | Renders as |
|---|---|
| `# comment` | Ignored |
| `SECTION: Title` | Section header |
| `STEP: Description` | Checkbox only |
| `STEP_VALUE: Description` | Checkbox + required text input |
| `PHOTO: Description` | Checkbox + required photo (EXIF validated) |
| `NOTE: Text` | Read-only informational banner — not recorded |

### Example

```text
SECTION: Safety & Permit

NOTE: Obtain permit-to-work before proceeding.
STEP: Lock Out / Tag Out (LOTO) applied
STEP_VALUE: Record ambient temperature (°C)
PHOTO: Photograph LOTO tags in place
```

### Validation rules (enforced on every upload)

- At least one `SECTION:` required
- At least one interactive step required
- Every step keyword must have a non-empty description
- Duplicate step labels warned
- Unknown line prefixes reported with line numbers
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
   - `STEP_VALUE` → enter a value first, then tap
   - `PHOTO` → capture photo (camera opens on mobile), then tap — EXIF age is checked on upload
   - Each tap writes a UTC timestamped row to `checklist_events` before the UI advances
3. **Corrective action** → tap **⚠ Corrective Action** if an issue is found mid-PM (see [Corrective Action Workflow](#corrective-action-workflow))
4. **Complete** → review the summary page
5. **Report** → `/session/<id>/report` — full printable audit trail

### Returning to an in-progress session

Navigating to `/session/<id>/checklist` (no `?section=`) auto-resumes at the first incomplete section. All completed steps, entered values, and photo filenames are restored from the DB.

---

## URL Reference

| URL | Method | Description |
|---|---|---|
| `/` | GET | Dashboard |
| `/personnel` | GET | List personnel |
| `/personnel/add` | POST | Add a person |
| `/workorders` | GET | List work orders |
| `/workorders/add` | POST | Create WO (auto-numbered) |
| `/session/start` | GET, POST | Start or resume a PM session |
| `/session/<id>/checklist` | GET | Execute checklist (auto-resumes) |
| `/session/<id>/step/check` | POST JSON | Record a step to DB |
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
| `/settings` | GET, POST | UI theme selection |
| `/settings/theme/<id>` | POST AJAX | Instant theme switch |
| `/api/tz` | POST JSON | Register browser UTC offset |

---

## Checklist Versioning

- On startup, `.txt` files in `checklists/` are seeded as v1 of each checklist (idempotent via SHA-256)
- Each new upload increments the version counter; duplicate content (same SHA-256) is rejected
- Exactly one version per checklist name is `is_active = TRUE` at any time
- New sessions use the active version; existing sessions are unaffected
- Any archived version can be re-activated, downloaded, or compared at any time

### Compare versions

Select any two versions on the compare page for a colour-coded unified diff: 🟢 added, 🔴 removed, blue chunk headers (`@@`).

---

## Corrective Action Workflow

An out-of-control situation found during a PM can be escalated into a linked corrective session without losing progress on the main checklist.

### Raising a corrective action

1. Tap **⚠ Corrective Action** in the section title bar
2. Complete the modal — issue description (required), corrective checklist, optional technician reassignment
3. The corrective session opens immediately; the main session stays `in_progress`

### During the corrective session

- An amber banner shows the recorded issue description
- All standard rules apply: sequential steps, DB-gated advancement, photo capture
- **← Return to Main** link is always visible

### Tracking from the parent session

- Amber chip bar lists all linked corrective sessions; completed ones turn green (✓)

### In reports

- Completion summary lists all corrective sessions with status and links
- Audit report includes a full "Corrective Actions Raised" table
- Corrective session report links back to the parent PM report

### Built-in corrective action template (`corrective_action.txt`)

7-section template covering the complete corrective lifecycle:

| Section | Purpose |
|---|---|
| Immediate Response & Containment | LOTO, isolation, cordoning, photo of defect as found |
| Situation Assessment | Failure mode, time of discovery, units affected, severity classification |
| Root Cause Investigation | Root cause statement, contributing factors, evidence collection |
| Corrective Repair | Parts list, repair procedure, torque values, LOTO removal |
| Verification & Testing | Full operating cycle, parameters recorded, defect confirmed resolved |
| Affected Product / Output Disposition | Conformance review, disposition decision, QA sign-off |
| Preventive Measures & Documentation | Recurrence prevention, CMMS update, supervisor sign-off |

---

## Telegram Alerts

Uses `parse_mode="HTML"` with `<a href>` clickable links. Silently skipped if credentials are blank.

### Startup alert
```
🟢 PM Checklist — Server Started

🖥 Hostname:  myserver
🔌 Local IP:  192.168.1.50:5000
🌐 Public IP: 203.x.x.x

🔗 Access: http://192.168.1.50:5000
🌍 Public: http://203.x.x.x:5000
```

### Photo purge alert
```
🗑 PM Checklist — Auto Photo Purge

📊 Disk was at 84.2% (threshold 80%)
✅ Disk now at 71.5%
🗑 Deleted 12 photo(s) — freed 187.4 MB
📷 Remaining photos in DB: 38

Deleted files:
  • WO-20260301-001 / Compressor A — session_3/photo.jpg
```

---

## Timezone Handling

**Rule: store UTC, display browser-local.**

- All `TIMESTAMP` columns are `TIMESTAMPTZ` (UTC-aware)
- JS reads `new Date().getTimezoneOffset()` on every page load, POSTs to `/api/tz`, stored in a 1-year cookie
- If offset changes (DST, different device), page reloads once to re-render
- Jinja filter `| localdt` converts UTC datetimes to browser-local for all server-rendered timestamps
- Live AJAX timestamps returned as ISO 8601 strings; `window.fmtUTC()` converts client-side

---

## Mobile Support

| Feature | Implementation |
|---|---|
| Hamburger menu | Replaces desktop nav below 640 px; closes on backdrop tap |
| Card-list views | Tables replaced by stacked cards on mobile |
| Fixed bottom footer | Prev/Next buttons fixed above browser chrome on checklist page |
| 44 px touch targets | All interactive elements meet minimum size |
| Camera capture | `PHOTO` steps use `capture="environment"` — opens rear camera directly |
| No iOS zoom | All inputs use `font-size: 1rem` |
| Scroll to next step | Newly unlocked step scrolls into view automatically |

---

## Sequential Step Enforcement

Steps within a section must be completed strictly in order. Enforced at two independent layers:

**UI:** Only the next incomplete step is `step-active` (pulsing cyan ring). All subsequent steps are `step-locked` (dimmed, all inputs `disabled`). After DB confirmation, `unlockNextStep()` activates the next step.

**Server:** `/session/<id>/step/check` walks all interactive steps in order. If any prior step is missing from `checklist_events`, the request is rejected with HTTP 400.

**Breadcrumb:** Future incomplete sections are `crumb-locked` (dashed, non-clickable).

---

## Photo EXIF Validation

Every photo uploaded to a `PHOTO` step is validated against its EXIF capture timestamp.

### How it works

1. File bytes are read into memory (not saved yet)
2. Pillow reads EXIF tags in priority order: `DateTimeOriginal` → `DateTimeDigitized` → `DateTime`
3. The EXIF local time is converted to UTC using the browser's stored `tz_offset` cookie
4. Age is compared against `photo_max_age_minutes` (default: 60)

### Decision table

| Situation | Result |
|---|---|
| EXIF found, age ≤ 60 min | ✅ Accepted |
| EXIF found, age > 60 min | ❌ Rejected — error includes timestamp and age in minutes |
| EXIF in the future (clock skew) | ✅ Accepted with server-side warning log |
| No EXIF found | ✅ Accepted — cannot penalise phones that strip metadata |
| PDF file | ✅ Accepted — no EXIF concept |

### Configuration

```ini
[app]
photo_max_age_minutes = 60   # 0 = disable check entirely
```

### Error message shown to technician

> *"Photo was taken 143 minutes ago (2026-05-17 08:22:11) — only photos taken within the last 60 minutes are accepted. Please take a new photo now."*

---

## Storage Management

### Auto-purge

1. After every photo upload and on startup, `shutil.disk_usage()` checks the partition where `app.py` resides
2. **Partition auto-detected** — `get_app_partition()` walks the directory tree comparing `os.stat().st_dev` until the mount point boundary is found; works with SD cards, external drives, separate `/home` partitions
3. If usage ≥ `disk_threshold_pct`, oldest photos (by `timestamp ASC`) are deleted from disk and `photo_path` is set to `NULL` in the DB
4. Purging continues until usage drops below `threshold − 5%` or no photos remain
5. Telegram purge alert sent with per-file detail

### `/admin/storage` status page

- Visual disk usage bar (green → amber → red)
- Total / used / free GB, detected partition path
- Photo file count on disk vs DB record count
- Manual purge button with confirmation dialog

### Key design decisions

- Purge is atomic per file: DB updated only after file is confirmed deleted
- `photo_path` is set to `NULL`, not the row deleted — session event history preserved
- Up to 10 file paths included in Telegram alert; excess shown as "… and N more"

---

## UI Themes

8 built-in themes selectable from **Settings** in the navigation. Changes apply instantly — no page reload.

| Theme | Style | Accent |
|---|---|---|
| Industrial Dark | Default — dark, utilitarian | `#00c8ff` |
| Clean Light | Light grey, professional | `#2563eb` |
| Midnight Navy | Deep navy | `#7c6af7` |
| Forest Green | Dark green | `#4ade80` |
| Warm Amber | Brown tones | `#f59e0b` |
| Arctic White | Cool white | `#0ea5e9` |
| Crimson Steel | Near-black, red | `#ef4444` |
| Pastel Studio | Dark purple, lavender | `#c084fc` |

### How it works

- Each theme is a single CSS file in `static/css/themes/` that overrides only `:root` variables
- Active theme stored in `app_settings` DB table under key `theme`
- `base.html` injects `<link id="theme-css">` after the base stylesheet on every page
- Switching calls `POST /settings/theme/<id>` via AJAX, updates the `<link>` href in-place
- `config.ini` `theme =` provides the fallback default before any DB setting exists

### Adding a custom theme

1. Create `static/css/themes/mytheme.css` with a `:root { }` block
2. Add an entry to the `THEMES` dict in `app.py`
3. Restart — it appears immediately on the Settings page

---

## Changelog

### v1.0 — Initial Release
- Flask + PostgreSQL backend with auto DB/table creation
- Single editable `.txt` checklist template
- Three step types: `STEP`, `STEP_VALUE`, `PHOTO`
- Personnel and work order management
- PM session tracking, section-by-section execution
- DB-gated Next Section button
- Photo uploads stored to `static/uploads/`
- Printable per-session audit report
- Separate `config.ini`

### v1.1 — Auto WO Number & Duplicate Session Guard
- WO numbers auto-generated: `WO-YYYYMMDD-NNN`, daily sequence
- Blocks duplicate active sessions per WO
- Start Session page warns and offers Resume when WO has an active session
- Work Orders list shows pulsing **LIVE** badge and Resume button
- `get_all_work_orders_enriched()` single query for active/latest session IDs

### v1.2 — Multiple Checklist Types
- `config.ini` `[checklist]` changed from `template_file` to `template_dir`
- Any `.txt` in `checklists/` available as a checklist type
- Four built-in templates: weekly, monthly, quarterly, annual
- `work_orders` gains `checklist_name` column (migrated automatically)
- WO creation includes checklist type dropdown
- Checklist name frozen on each session at creation time

### v1.3 — Browser Timezone
- All timestamps stored as `TIMESTAMPTZ` (UTC)
- Browser UTC offset detected on page load, stored in `tz_offset` cookie
- Jinja filter `| localdt` converts UTC to browser-local for all server-rendered timestamps
- Live AJAX timestamps returned as ISO 8601 strings, converted client-side with `window.fmtUTC()`
- Page reloads once if offset changes (DST transition, different device)

### v1.4 — Telegram Startup Alert
- New `telegram_alert.py` (stdlib only — no extra dependencies)
- `config.ini` gains `[telegram]` section
- Startup message: hostname, local IP, public IP, clickable HTML links
- `parse_mode="HTML"` + `disable_web_page_preview` for reliable rendering
- Silently skipped if credentials blank

### v1.5 — Mobile-Friendly UI
- Full CSS rewrite: mobile-first, 640 px and 380 px breakpoints
- Hamburger navigation with slide-down drawer
- Data tables replaced by card-list views on mobile
- Fixed bottom footer bar on checklist page
- 44 × 44 px minimum touch targets on all interactive elements
- `capture="environment"` on PHOTO file inputs for direct camera access
- `font-size: 1rem` on all inputs to prevent iOS auto-zoom

### v1.6 — Sequential Step Enforcement
- Steps must be completed in strict order; skipping blocked
- CSS states: `step-done` (✓), `step-active` (pulsing), `step-locked` (dimmed)
- `unlockNextStep()` activates next step after DB confirmation and scrolls it into view
- Server-side guard in `step_check` rejects out-of-order submissions with HTTP 400
- Future section breadcrumb crumbs rendered as `crumb-locked` (dashed, non-clickable)

### v1.7 — Session Resume / Progress Restore
- `get_session_events_dict()` returns all completed events keyed by `step_key`
- `get_resume_section()` finds the first section with any incomplete step
- Auto-redirect to resume section when no `?section=` in URL
- Completed `STEP_VALUE` inputs re-rendered with stored values
- Completed `PHOTO` steps show original filename in upload label
- Timestamps on already-completed steps show exact recorded UTC time (browser-local)
- `uploadedPhotos` JS dict pre-populated from DB events

### v1.8 — Checklist Versioning
- New `checklist_versions` DB table: full content, SHA-256, version number, uploader, active flag
- `parse_template_from_string()` — parses from DB content string
- `validate_template()` — returns errors and warnings before upload
- Startup seeds disk `.txt` files into versions table (idempotent)
- AJAX validation with summary (sections, steps, photos, values) before submit button enables
- Unified diff via `difflib.unified_diff` with colour-coded rendering
- Version activation: atomic promotion with previous version demoted
- **Bugfix:** `RealDictCursor.fetchone()[0]` `KeyError` — scalar queries use plain cursor

### v1.9 — Automatic Photo Cleanup
- New `storage_manager.py` — disk monitoring and purge (stdlib + psycopg2)
- `config.ini` gains `[storage]` section with `disk_threshold_pct`
- Purge triggered after every photo upload and at startup
- Oldest photos (by `timestamp ASC`) deleted until disk drops below `threshold − 5%`
- `photo_path` set to `NULL` in DB after each deletion (event row preserved)
- Telegram purge alert via `send_telegram_message()` helper
- `/admin/storage` status page with visual disk bar and manual purge button

### v1.10 — UI Themes & Settings Page
- 8 built-in themes in `static/css/themes/` — each overrides only `:root` CSS variables
- New `app_settings` DB table for runtime-changeable settings persisted across restarts
- `app.context_processor` injects `active_theme`, `theme_meta`, `theme_css` into all templates
- Instant theme switching via AJAX — `<link>` `href` swapped in-place, no page reload
- `/settings` page with 8 visual swatch cards, each rendered in that theme's own colours
- Active swatch highlighted with glow ring; toast notification on change
- `config.ini` `theme =` provides default before any DB setting exists
- **Bugfix:** context processor wrapped in `try/except` — never raises even if DB not ready

### v1.11 — Corrective Action Sessions
- `pm_sessions` gains three new columns (migrated automatically):
  - `session_type` (`planned` / `corrective`)
  - `parent_session_id` (FK to parent session)
  - `issue_description` (out-of-control situation description)
- **⚠ Corrective Action** button in section header opens a modal during any planned PM
- Modal captures: issue description, corrective checklist selection, optional technician reassignment
- Corrective session runs independently; parent session remains `in_progress`
- Amber banner at top of corrective session shows issue description and Return to Main link
- Amber chip bar on parent session tracks all linked corrective sessions (turns green when done)
- Completion summary and audit report include full corrective action details and links
- New seed template `checklists/corrective_action.txt` — 7 sections covering the complete corrective lifecycle
- Dashboard filters to planned sessions only; corrective sessions flagged with ⚠ indicator
- New routes: `POST /session/<id>/corrective/start`, `GET /session/<id>/corrective/modal`

### v1.12 — EXIF Photo Age Validation
- New `exif_checker.py` module — Pillow-based EXIF extraction and age validation
- `Pillow>=10.0.0` added to `requirements.txt`
- Every `PHOTO` step upload checked against EXIF `DateTimeOriginal` / `DateTimeDigitized` / `DateTime`
- Photos with EXIF older than `photo_max_age_minutes` (default 60) are rejected before saving
- Error message includes exact EXIF timestamp and age: *"Photo was taken 143 minutes ago…"*
- Photos with no EXIF (metadata stripped) allowed through — cannot penalise legitimate devices
- PDF uploads bypass EXIF check (no EXIF concept)
- EXIF local time converted to UTC using the browser's stored `tz_offset` cookie for accurate comparison
- Future EXIF timestamps (device clock skew) allowed through with server-side warning log
- `photo_max_age_minutes = 0` in `config.ini` disables the check entirely

### v1.13 — Step Minimum Dwell Time

Steps can now specify a minimum time the technician must spend on them before they can be completed. Every tap is logged regardless of timing for full analytics.

**Template syntax:**

Add `[min=N]` to any step type (N = seconds):

```text
STEP: Power on equipment and observe startup sequence [min=60]
STEP: Run equipment through full operating cycle [min=120]
STEP: Test emergency stop (E-Stop) functionality [min=30]
STEP_VALUE: Record operating current at full load (A) [min=45]
PHOTO: Photograph equipment in operating condition [min=0]
```

The parser strips `[min=N]` from the displayed label — technicians see the clean description.

**Behaviour:**

- When a step becomes active, its countdown timer starts immediately
- The checkbox button stays **locked** until the minimum time elapses
- A live `⏱ Min. time: 47s remaining` counter pulses amber below the step
- When time elapses, the counter turns green (`Min. time elapsed ✓`) and the button unlocks automatically
- **Every tap is logged** to `step_dwell_events` regardless of whether the timer has expired — early taps are recorded with `was_early = TRUE` for analytics
- Server also enforces minimum time: `step_check` rejects early submissions with HTTP 400 even if the UI is bypassed

**New DB table — `step_dwell_events`:**

| Column | Type | Description |
|---|---|---|
| `id` | SERIAL PK | |
| `session_id` | FK → pm_sessions | |
| `personnel_id` | FK → personnel | |
| `wo_id` | FK → work_orders | |
| `wo_number` | TEXT | Denormalised for easy analytics |
| `step_key` | TEXT | `"{section}_{step}"` |
| `section_index` | INTEGER | |
| `step_index` | INTEGER | |
| `step_label` | TEXT | Clean label (without `[min=N]`) |
| `min_seconds` | INTEGER | Configured minimum |
| `elapsed_seconds` | FLOAT | How long since step activated |
| `was_early` | BOOLEAN | TRUE if tapped before minimum elapsed |
| `tapped_at` | TIMESTAMPTZ | UTC |

**New routes:**
- `POST /session/<id>/step/tap` — logs a tap attempt and returns `was_early` + `remaining_seconds`

**Updated templates** (`checklists/weekly_pm.txt`, `checklists/corrective_action.txt`) — demonstrate the syntax with realistic minimum times (E-Stop 30 s, startup observation 60 s, full operating cycle 120 s).
