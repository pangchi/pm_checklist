# PM Checklist — Preventive Maintenance System

A production-ready Flask + PostgreSQL application for managing digital preventive maintenance checklists. Supports multiple checklist types, sequential step enforcement, photo attachments, browser-local timestamps, Telegram startup alerts, mobile-responsive UI, full checklist versioning with diff comparison, automatic photo cleanup, and live UI theme switching.

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
10. [Telegram Alerts](#telegram-alerts)
11. [Timezone Handling](#timezone-handling)
12. [Mobile Support](#mobile-support)
13. [Sequential Step Enforcement](#sequential-step-enforcement)
14. [Storage Management](#storage-management)
15. [UI Themes](#ui-themes)
16. [Corrective Action Workflow](#corrective-action-workflow)
17. [Changelog](#changelog)

---

## Features

| Feature | Details |
|---|---|
| **Multiple checklist types** | Weekly, Monthly, Quarterly, Annual — or any custom type |
| **Checklist versioning** | Upload new versions, compare diffs, activate/archive, download |
| **Sequential steps** | Steps must be completed in order; skipping blocked at UI and server level |
| **Three step types** | `STEP` (checkbox), `STEP_VALUE` (checkbox + value input), `PHOTO` (checkbox + photo upload) |
| **Notes** | `NOTE:` lines display as read-only informational banners |
| **DB-gated advancement** | Next Section button only enables after every step confirmed written to DB |
| **Session resume** | Returning to an in-progress session restores all completed steps, values, and photo filenames |
| **Auto WO numbering** | Work order numbers auto-generated as `WO-YYYYMMDD-NNN` |
| **No duplicate sessions** | Only one active session allowed per work order |
| **Browser timezone** | All timestamps displayed in browser's local timezone; DB stores UTC |
| **Telegram startup alert** | Sends hostname, local IP, and public IP to a Telegram chat on startup |
| **Telegram purge alert** | Notifies when photos are auto-deleted due to disk threshold |
| **Auto photo cleanup** | Oldest photos deleted automatically when disk usage exceeds configured threshold |
| **Mobile-first UI** | Hamburger nav, card-list views, fixed bottom footer, camera capture for photos |
| **UI themes** | 8 built-in colour themes, selectable via Settings page, applied instantly without page reload |
| **Printable reports** | Full per-session audit trail with all values, timestamps, photo links |
| **Auto DB creation** | Database and all tables created automatically on first run |
| **Live migrations** | Schema updates applied via `ALTER TABLE … ADD COLUMN IF NOT EXISTS` on every startup |

---

## Project Structure

```
pm_checklist/
├── app.py                          # Flask routes, Jinja filters, startup logic
├── db.py                           # All PostgreSQL logic, auto-DB/table creation
├── checklist_parser.py             # .txt template parser (file and string modes)
├── telegram_alert.py               # Startup and purge Telegram notifications
├── storage_manager.py              # Disk monitoring and photo auto-purge
├── config.ini                      # ← All credentials and settings here
├── requirements.txt
│
├── checklists/                     # Seed .txt templates (auto-imported to DB on startup)
│   ├── weekly_pm.txt
│   ├── monthly_pm.txt
│   ├── quarterly_pm.txt
│   └── annual_pm.txt
│
├── static/
│   ├── css/
│   │   ├── style.css               # Full mobile-first base stylesheet
│   │   └── themes/                 # One CSS file per theme (overrides :root variables)
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
    ├── base.html                   # Nav, hamburger, TZ detection, theme CSS injection
    ├── index.html                  # Dashboard with session list
    ├── personnel.html              # Add/list personnel
    ├── workorders.html             # Create/list work orders
    ├── start_session.html          # Start or resume a PM session
    ├── checklist.html              # Step-by-step checklist execution
    ├── complete.html               # Session completion summary
    ├── report.html                 # Printable audit report
    ├── checklists.html             # Checklist template library
    ├── checklist_versions.html     # Version history, upload, activate
    ├── checklist_compare.html      # Side-by-side unified diff
    ├── storage_status.html         # Disk usage dashboard and manual purge
    └── settings.html               # UI theme picker and app info
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 13+ (local or remote)

### Install

```bash
pip install -r requirements.txt
```

### Configure

Edit `config.ini` (see [Configuration](#configuration) below).

### Run

```bash
python app.py
```

On first run the app will:
1. Connect to the `postgres` system database
2. Create the `pm_checklist` database if it does not exist
3. Create all tables and indexes
4. Run schema migrations (safe to re-run on every start)
5. Seed any `.txt` files from `checklists/` into the versioning table
6. Check disk usage and purge oldest photos if already over threshold
7. Send a Telegram startup alert (if configured)
8. Start the Flask server at `http://0.0.0.0:5000`

---

## Configuration

All settings are in `config.ini`. No credentials or paths appear in code.

```ini
[database]
host     = localhost
port     = 5432
name     = pm_checklist        # Created automatically if missing
user     = postgres
password = yourpassword

[app]
secret_key    = change-this-to-a-random-secret-key
upload_folder = static/uploads
max_upload_mb = 16
debug         = true
port          = 5000
host          = 0.0.0.0
# Default theme (overridden at runtime via Settings page, stored in DB)
# Options: industrial_dark, clean_light, midnight_navy, forest_green,
#          warm_amber, arctic_white, crimson_steel, pastel_studio
theme         = industrial_dark

[checklist]
template_dir = checklists      # Directory scanned for seed .txt files

[telegram]
# Get bot_token from @BotFather on Telegram
# Get chat_id by messaging @userinfobot or getUpdates API
bot_token =
chat_id   =

[storage]
# Disk usage threshold (percentage) above which oldest photos are auto-deleted
disk_threshold_pct = 80
# Partition is auto-detected from the mount point where app.py resides.
# No manual configuration needed.
```

**Getting Telegram credentials:**
1. Message `@BotFather` → `/newbot` → copy the token
2. Message your bot, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates` to find your `chat_id`

---

## Database Schema

### `personnel`
| Column | Type | Description |
|---|---|---|
| `id` | SERIAL PK | |
| `name` | TEXT | Full name |
| `badge` | TEXT UNIQUE | Employee / badge ID |
| `department` | TEXT | Optional department |
| `created_at` | TIMESTAMPTZ | UTC |

### `work_orders`
| Column | Type | Description |
|---|---|---|
| `id` | SERIAL PK | |
| `wo_number` | TEXT UNIQUE | Auto-generated: `WO-YYYYMMDD-NNN` |
| `equipment` | TEXT | Equipment name |
| `description` | TEXT | Optional description |
| `checklist_name` | TEXT | Logical checklist name (e.g. `quarterly_pm`) |
| `status` | TEXT | `open` → `in_progress` → `completed` |
| `created_at` | TIMESTAMPTZ | UTC |
| `updated_at` | TIMESTAMPTZ | UTC |

### `pm_sessions`
| Column | Type | Description |
|---|---|---|
| `id` | SERIAL PK | |
| `wo_id` | FK → work_orders | |
| `personnel_id` | FK → personnel | |
| `template_name` | TEXT | Checklist name at session creation (immutable) |
| `status` | TEXT | `in_progress` \| `completed` |
| `started_at` | TIMESTAMPTZ | UTC |
| `completed_at` | TIMESTAMPTZ | UTC, null until done |

### `checklist_events`
| Column | Type | Description |
|---|---|---|
| `id` | SERIAL PK | |
| `session_id` | FK → pm_sessions | Cascade delete |
| `section_index` | INTEGER | Zero-based section position |
| `step_index` | INTEGER | Zero-based step position within section |
| `step_key` | TEXT | `"{section}_{step}"` composite key |
| `step_type` | TEXT | `STEP` \| `STEP_VALUE` \| `PHOTO` |
| `step_label` | TEXT | Description text from template |
| `checked` | BOOLEAN | Always TRUE (only completed steps recorded) |
| `value_input` | TEXT | Entered measurement (STEP_VALUE only) |
| `photo_path` | TEXT | Relative path under `static/uploads/` — set to NULL after auto-purge |
| `timestamp` | TIMESTAMPTZ | UTC — exact moment the DB write succeeded |

### `checklist_versions`
| Column | Type | Description |
|---|---|---|
| `id` | SERIAL PK | |
| `checklist_name` | TEXT | Logical name, e.g. `weekly_pm` |
| `version` | INTEGER | Auto-incremented per checklist name |
| `filename` | TEXT | Original uploaded filename |
| `content` | TEXT | Full `.txt` file content |
| `checksum` | TEXT | SHA-256 of content (duplicate detection) |
| `notes` | TEXT | Uploader's change notes |
| `uploaded_by` | TEXT | Uploader name |
| `is_active` | BOOLEAN | Only one active version per checklist name |
| `uploaded_at` | TIMESTAMPTZ | UTC |

### `app_settings`
| Column | Type | Description |
|---|---|---|
| `key` | TEXT PK | Setting identifier (e.g. `theme`) |
| `value` | TEXT | Setting value (e.g. `midnight_navy`) |
| `updated_at` | TIMESTAMPTZ | UTC — last changed |

---

## Checklist Template Format

Templates are plain `.txt` files. Any text editor works. Files in `checklists/` are auto-seeded into the DB on startup; subsequent changes must be uploaded via the Templates UI.

### Syntax

| Prefix | Renders as |
|---|---|
| `# comment` | Ignored |
| `SECTION: Title` | Section header (groups steps) |
| `STEP: Description` | Checkbox only |
| `STEP_VALUE: Description` | Checkbox + required text input (measurement, reading, etc.) |
| `PHOTO: Description` | Checkbox + required photo upload (camera on mobile) |
| `NOTE: Text` | Read-only informational banner — not a step, not recorded |

### Example

```text
# Quarterly PM Template

SECTION: Safety & Permit

NOTE: Obtain permit-to-work before proceeding.
STEP: Lock Out / Tag Out (LOTO) applied
STEP_VALUE: Record ambient temperature (°C)
PHOTO: Photograph LOTO tags in place

SECTION: Mechanical Inspection

STEP: Inspect belts and pulleys for wear
STEP_VALUE: Record belt tension (N)
STEP: Lubricate all designated points
```

### Validation Rules (enforced on upload)

- At least one `SECTION:` required
- At least one interactive step (`STEP` / `STEP_VALUE` / `PHOTO`) required
- Every step keyword must have a non-empty description
- Duplicate step labels flagged as warnings
- Unknown line prefixes reported with line numbers
- File must be valid UTF-8

---

## Workflow

### Setup (one-time)

1. **Add Personnel** → `/personnel` — name, badge ID, department
2. **Create Work Order** → `/workorders` — equipment name, select checklist type

### Per PM Run

1. **Start Session** → `/session/start` — select work order and technician
   - If the WO already has an active session, you are redirected to resume it (no duplicates)
2. **Execute Checklist** — one section at a time:
   - `STEP` → tap the circle checkbox
   - `STEP_VALUE` → enter a value, then tap the checkbox
   - `PHOTO` → tap "Attach Photo" (opens camera on mobile), then tap the checkbox
   - Each successful checkbox tap writes a timestamped row to `checklist_events`
   - Steps must be completed **in sequence** — skipping is blocked in the UI and on the server
   - The **Next Section** button only activates after all steps in the section are DB-confirmed
3. **Complete** → review the summary page
4. **Report** → `/session/<id>/report` — full audit trail, printable

### Returning to an In-Progress Session

Navigating to `/session/<id>/checklist` (no `?section=`) automatically resumes at the first incomplete section. All previously completed steps, entered values, and uploaded photo filenames are restored from the database.

---

## URL Reference

| URL | Method | Description |
|---|---|---|
| `/` | GET | Dashboard — recent sessions |
| `/personnel` | GET | List personnel |
| `/personnel/add` | POST | Add a new person |
| `/workorders` | GET | List work orders |
| `/workorders/add` | POST | Create work order (WO number auto-generated) |
| `/session/start` | GET, POST | Start or resume a PM session |
| `/session/<id>/checklist` | GET | Execute checklist (auto-resumes) |
| `/session/<id>/step/check` | POST (JSON) | Record a step to DB |
| `/session/<id>/upload_photo` | POST (multipart) | Upload a step photo |
| `/session/<id>/complete` | GET | Mark session complete |
| `/session/<id>/report` | GET | Printable audit report |
| `/checklists` | GET | Checklist template library |
| `/checklists/<name>` | GET | Version history for one checklist |
| `/checklists/<name>/upload` | POST | Upload new version |
| `/checklists/new` | POST | Upload a brand-new checklist type |
| `/checklists/version/<id>/activate` | POST | Promote version to active |
| `/checklists/version/<id>/download` | GET | Download version as `.txt` |
| `/checklists/validate` | POST (multipart) | AJAX validate before upload |
| `/checklists/compare` | GET | Unified diff between two versions |
| `/uploads/<path>` | GET | Serve uploaded photos |
| `/admin/storage` | GET | Disk usage dashboard |
| `/admin/storage/purge` | POST | Manually trigger photo purge |
| `/settings` | GET, POST | UI theme selection |
| `/settings/theme/<id>` | POST (AJAX) | Instant theme switch |
| `/api/tz` | POST (JSON) | Register browser UTC offset (cookie) |

---

## Checklist Versioning

Templates are stored in the `checklist_versions` table with full version history.

### How it works

- On startup, any `.txt` files in `checklists/` are **seeded** as v1 of their respective checklist (skipped if identical content already exists, detected via SHA-256)
- Each upload increments the version counter for that checklist name
- Uploading identical content (same SHA-256) is rejected — no no-op versions
- Exactly one version per checklist name is marked `is_active = TRUE`
- All new sessions use the **active version** at session creation time
- Existing in-progress sessions are unaffected by version changes (the `template_name` is immutable per session)

### Activate a version

Go to **Templates → `<checklist name>`** → click **Activate** on any archived version. The previous active version is immediately demoted.

### Compare versions

1. From the version history page, click **⇄ Compare** on any version
2. Select Version A (from) and Version B (to)
3. A colour-coded unified diff is rendered: 🟢 added, 🔴 removed, blue chunk headers
4. Download either version directly from the comparison page

---

## Telegram Alerts

The app sends two types of Telegram messages using `parse_mode="HTML"` with `<a href>` clickable links.

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
  • WO-20260301-001 / Compressor A — session_3/...
```

Both alerts are silently skipped if `bot_token` or `chat_id` is blank in `config.ini`.

---

## Timezone Handling

**Rule: store in UTC, display in browser local time.**

- All timestamp columns are `TIMESTAMPTZ` (UTC-aware)
- On every page load, JS reads `new Date().getTimezoneOffset()` and POSTs the browser's UTC offset in minutes to `/api/tz`, stored in a 1-year cookie (`tz_offset`)
- If the offset changes (DST, different device), the page reloads once
- Server-side: Jinja filter `| localdt` converts UTC datetimes to browser-local before rendering
- Client-side: live AJAX timestamps returned as ISO 8601 strings (`2026-05-16T10:30:00Z`), converted with `window.fmtUTC()`

---

## Mobile Support

| Feature | Implementation |
|---|---|
| **Hamburger menu** | Replaces desktop nav links below 640 px; closes on backdrop tap |
| **Card-list views** | Tables replaced by stacked cards on mobile |
| **Fixed bottom footer** | Previous/Next buttons fixed above browser chrome on checklist page |
| **44 px touch targets** | All buttons and checkboxes meet minimum touch target size |
| **Camera capture** | `PHOTO` steps use `capture="environment"` — opens rear camera on mobile |
| **No iOS zoom** | All inputs use `font-size: 1rem` to prevent iOS auto-zoom on focus |
| **Scroll to next step** | After completing a step, the newly unlocked step scrolls into view |

---

## Sequential Step Enforcement

Steps within a section must be completed strictly in order. Skipping is blocked at two independent layers:

### UI layer
- Only the **next incomplete step** is `step-active` (cyan left border, pulsing ring)
- All subsequent steps are `step-locked`: dimmed, all inputs `disabled`, `pointer-events: none`
- After DB confirmation, `unlockNextStep()` activates the next step and scrolls it into view

### Server layer
`/session/<id>/step/check` walks all interactive steps in order before accepting any write. If any prior step is incomplete, the request is rejected with HTTP 400.

### Section navigation
Future incomplete section breadcrumb crumbs are `crumb-locked` (dashed, non-clickable).

---

## Storage Management

### Auto-purge behaviour

1. After every photo upload and on server startup, `shutil.disk_usage()` checks the partition where `app.py` resides
2. **Partition is auto-detected** — `get_app_partition()` walks up the directory tree comparing `os.stat().st_dev` until the mount point boundary is found. Works correctly with SD cards, external drives, separate `/home` partitions, etc.
3. If usage ≥ `disk_threshold_pct` (default 80%), the oldest photos (by `timestamp ASC`) are deleted from disk and `photo_path` is set to `NULL` in the DB
4. Purging continues until disk usage drops below `threshold − 5%` or no photos remain
5. A Telegram alert is sent with details of what was deleted

### Storage status page (`/admin/storage`)

- Visual disk usage bar (colour: green → amber → red approaching threshold)
- Total / used / free GB, auto-detected partition path
- Photo file count on disk vs DB record count
- Manual purge button (with confirmation dialog)

### Key design decisions

- Purge is **atomic per file**: DB is only updated after the file is confirmed deleted from disk
- If the file is missing from disk (already deleted), the DB record is still nulled
- The `photo_path` field is set to `NULL` (not the row deleted) so the session event history is preserved
- Up to 10 deleted file paths are included in the Telegram alert; excess count shown as "… and N more"

---

## UI Themes

Eight built-in colour themes, selectable via **Settings** in the navigation.

| Theme | Style | Accent |
|---|---|---|
| **Industrial Dark** | Dark background, cyan accent | `#00c8ff` |
| **Clean Light** | Light grey background, blue accent | `#2563eb` |
| **Midnight Navy** | Deep navy, purple accent | `#7c6af7` |
| **Forest Green** | Dark green, lime accent | `#4ade80` |
| **Warm Amber** | Dark brown, amber accent | `#f59e0b` |
| **Arctic White** | Cool white, sky blue accent | `#0ea5e9` |
| **Crimson Steel** | Near-black, red accent | `#ef4444` |
| **Pastel Studio** | Dark purple, lavender accent | `#c084fc` |

### How it works

- Each theme is a standalone CSS file in `static/css/themes/` that overrides only the `:root` CSS variables
- The base `style.css` contains all layout and component rules — themes require no duplication
- The active theme is stored in the `app_settings` DB table under key `theme`
- On every page, `base.html` injects `<link id="theme-css" href="...themes/<active>.css">` after the base stylesheet
- **Switching is instant**: clicking a theme card calls `POST /settings/theme/<id>` via AJAX, then updates the `<link>` `href` in-place — no page reload needed
- The `config.ini` `[app] theme =` setting provides the fallback default before any DB setting exists
- Adding a new theme: create `static/css/themes/mytheme.css` with the `:root` block, add an entry to the `THEMES` dict in `app.py`

---

## Corrective Action Workflow

An out-of-control situation — a cracked component, an out-of-spec reading, a safety concern — can be raised at any point during a planned PM session without losing progress on the main checklist.

### Raising a corrective action

1. Tap **⚠ Corrective Action** in the section title bar during any planned PM session
2. Fill in the modal:
   - **Issue Description** *(required)* — describe exactly what was found; stored permanently in the DB
   - **Corrective Checklist** — select any available template (the dedicated `Corrective Action` template is recommended)
   - **Assigned To** — defaults to the current technician; optionally reassign
3. Tap **Start Corrective Action** — a new linked session opens immediately

### During the corrective session

- An **amber banner** at the top shows the recorded issue description
- All standard rules apply: sequential steps, DB-gated section advancement, photo capture
- **← Return to Main** link is always visible to navigate back to the parent session
- Both sessions can be worked in any order; neither is blocked by the other

### Tracking from the parent session

- An **amber chip bar** appears below the checklist header listing every linked corrective session
- Chips show the checklist name and status dot; completed sessions turn green (✓)
- Clicking a chip navigates directly to that corrective session

### In reports

- **Completion summary** — lists all corrective sessions with status, Resume, and Report buttons
- **Audit report** — "Corrective Actions Raised" table with issue text, technician, start time, and link to each corrective report
- **Corrective session report** — shows the issue description and a back-link to the parent PM report

### Corrective Action checklist template (`checklists/corrective_action.txt`)

A dedicated 7-section template is included, covering the complete corrective action lifecycle:

| Section | Purpose |
|---|---|
| **Immediate Response & Containment** | Stop operations, isolate equipment, LOTO, photograph the defect as found |
| **Situation Assessment** | Record failure mode, time of discovery, units affected, severity classification |
| **Root Cause Investigation** | 5-Why / fishbone analysis, evidence collection, root cause confirmation |
| **Corrective Repair** | Parts list, repair procedure, torque values, foreign object clearance, LOTO removal |
| **Verification & Testing** | Full operating cycle, parameter readings, defect confirmed resolved |
| **Affected Product / Output Disposition** | Conformance review, non-conforming unit count, disposition decision, QA sign-off |
| **Preventive Measures & Documentation** | Recurrence prevention, PM schedule review, CMMS update, supervisor sign-off |

Any other checklist can also be used for a corrective action — the template selection is made at the point of raising, so custom corrective checklists can be added to the `checklists/` directory and uploaded via the Templates page.

---

## Changelog

### v1.0 — Initial Release
- Flask application with PostgreSQL backend
- Single editable `.txt` checklist template
- Three step types: `STEP`, `STEP_VALUE`, `PHOTO`
- Personnel and work order management
- PM session tracking with section-by-section execution
- DB-gated Next Section button
- Photo uploads stored to `static/uploads/`
- Printable per-session audit report
- Auto database and table creation on first startup
- Separate `config.ini` for all credentials and settings

### v1.1 — Auto WO Number & Duplicate Session Guard
- WO numbers auto-generated: `WO-YYYYMMDD-NNN`, daily sequence resets
- Blocks starting a new session if WO already has one `in_progress`
- Start Session page shows inline warning and Resume option for active WOs
- Work Orders list shows pulsing **LIVE** badge and Resume button
- `get_all_work_orders_enriched()` — single query joining active/latest session IDs

### v1.2 — Multiple Checklist Types
- `config.ini` `[checklist]` changed from `template_file` to `template_dir`
- Any `.txt` in `checklists/` available as a checklist type
- Four built-in templates: weekly, monthly, quarterly, annual
- `work_orders` gains `checklist_name` column (with `ADD COLUMN IF NOT EXISTS` migration)
- WO creation includes checklist type dropdown
- Session's checklist name frozen at creation time

### v1.3 — Browser Timezone
- All timestamps stored as `TIMESTAMPTZ` (UTC)
- Browser UTC offset detected via JS, POSTed to `/api/tz`, stored in cookie
- Jinja filter `| localdt` converts UTC to browser-local for all server-rendered timestamps
- Live AJAX timestamps returned as ISO 8601 strings, converted client-side with `window.fmtUTC()`

### v1.4 — Telegram Startup Alert
- New `telegram_alert.py` module (stdlib only)
- `config.ini` gains `[telegram]` section
- Startup message includes hostname, local IP, public IP, clickable links
- Uses `parse_mode="HTML"` with `<a href>` for reliable link rendering
- Silently skipped if credentials are blank

### v1.5 — Mobile-Friendly UI
- Full CSS rewrite: mobile-first, 640 px and 380 px breakpoints
- Hamburger navigation with slide-down drawer
- Data tables replaced by card-list views on mobile
- Fixed bottom footer on checklist page
- 44 × 44 px minimum touch targets
- `capture="environment"` for direct camera access on PHOTO steps
- `font-size: 1rem` on inputs to prevent iOS auto-zoom

### v1.6 — Sequential Step Enforcement
- Steps must be completed in strict order; no skipping allowed
- Three CSS states: `step-done`, `step-active` (pulsing), `step-locked` (dimmed)
- `unlockNextStep()` activates next step after DB confirmation
- Server-side guard in `step_check` rejects out-of-order submissions with HTTP 400
- Future section breadcrumb crumbs rendered as `crumb-locked`

### v1.7 — Session Resume / Progress Restore
- `get_session_events_dict()` returns all completed events keyed by `step_key`
- `get_resume_section()` finds the first section with incomplete steps
- Auto-redirect to resume section when no `?section=` in URL
- Completed inputs rendered with stored values; photo steps show original filename
- `uploadedPhotos` JS dict pre-populated from DB events

### v1.8 — Checklist Versioning
- New `checklist_versions` DB table: content, SHA-256 checksum, version, uploader, active flag
- `parse_template_from_string()` — parses from DB content, no file I/O
- `validate_template()` — returns errors/warnings before upload
- Startup seeds disk `.txt` files into versions table (idempotent)
- AJAX validation endpoint with summary (sections, steps, photos, values)
- Unified diff via `difflib.unified_diff` with colour-coded rendering
- Version activation: promote any archived version; previous active demoted atomically
- **Bugfix:** `RealDictCursor.fetchone()[0]` `KeyError` fixed — scalar queries use plain cursor

### v1.9 — Automatic Photo Cleanup
- New `storage_manager.py` — disk monitoring and photo purge (stdlib + psycopg2)
- `config.ini` gains `[storage]` section with `disk_threshold_pct`
- Purge triggered after every photo upload and at startup
- Oldest photos (by `timestamp ASC`) deleted until disk drops below `threshold − 5%`
- `photo_path` set to `NULL` in DB after each file deletion (event row preserved)
- Telegram purge alert via new `send_telegram_message()` helper
- `/admin/storage` status page with visual disk bar and manual purge button

### v1.10 — UI Themes & Settings Page
- 8 built-in colour themes in `static/css/themes/`: Industrial Dark, Clean Light, Midnight Navy, Forest Green, Warm Amber, Arctic White, Crimson Steel, Pastel Studio
- Each theme is a standalone CSS file overriding only `:root` variables — no duplication of layout rules
- New `app_settings` DB table (key/value) for runtime-changeable settings persisted across restarts
- `db.get_setting()`, `db.set_setting()`, `db.get_all_settings()` helpers
- `app.context_processor` injects `active_theme`, `theme_meta`, `theme_css` into all templates
- `base.html` dynamically injects `<link id="theme-css">` after base stylesheet
- **Instant switching**: `POST /settings/theme/<id>` updates `<link>` `href` in-place via AJAX — no page reload
- `config.ini` `[app] theme =` provides default before any DB setting exists
- `/settings` page shows 8 visual swatch cards with mini app preview (nav, stat cards, checklist step)
- Each swatch rendered using the target theme's own colours; active swatch highlighted with glow ring
- Toast notification on theme change
- **Settings** link added to desktop nav and mobile drawer
- Adding a new theme: create CSS file in `themes/`, add entry to `THEMES` dict in `app.py`

### v1.11 — Corrective Action Sessions

Out-of-control situations discovered during a PM can now trigger a linked corrective action checklist without abandoning the main session.

**How to use:**
1. During any active PM checklist, tap **⚠ Corrective Action** in the section header
2. Describe the issue found (e.g. "Belt cracked — replacement required")
3. Select the corrective checklist to follow (any available template)
4. Optionally assign a different technician
5. The corrective session opens immediately — complete it fully
6. Return to the parent PM session via the **← Return to Main** button and continue

**DB changes:**
- `pm_sessions` gains three new columns (all added via `ADD COLUMN IF NOT EXISTS` migration):
  - `session_type TEXT DEFAULT 'planned'` — `'planned'` for normal PM, `'corrective'` for corrective actions
  - `parent_session_id INTEGER` — FK back to the parent session (corrective sessions only)
  - `issue_description TEXT` — description of the out-of-control situation
- `create_session()` updated to accept the new parameters
- `get_corrective_sessions(parent_id)` — returns all corrective sessions for a given parent
- Dashboard `get_recent_sessions()` filters to `session_type = 'planned'` only

**UI features:**
- **⚠ Corrective Action** button shown in the section header bar of every planned session
- Clicking opens a modal with: issue description textarea, checklist selector, technician selector
- Corrective sessions show an amber banner at the top with the issue description and a "← Return to Main" link
- Active corrective sessions from the parent are shown in an amber chip bar below the header
- Chips turn green when the corrective session is completed
- Completion summary page lists all linked corrective sessions with status and report links
- Audit report includes a **Corrective Actions Raised** table with issue, technician, timestamps
- Corrective session reports show the issue and a link back to the parent report
- Dashboard flags sessions with a ⚠ corrective indicator in the equipment column

**New routes:**
- `POST /session/<id>/corrective/start` — creates and redirects to a new corrective session
- `GET /session/<id>/corrective/modal` — AJAX endpoint for modal data (checklists + personnel)

**New template file (`checklists/corrective_action.txt`):**
- 7 sections covering the complete corrective action lifecycle: Immediate Response & Containment, Situation Assessment, Root Cause Investigation, Corrective Repair, Verification & Testing, Affected Product Disposition, Preventive Measures & Documentation
- Mix of `STEP`, `STEP_VALUE`, and `PHOTO` types throughout — evidence photos required at key stages
- Auto-seeded into `checklist_versions` on next startup alongside other seed templates
- Selectable as a corrective checklist from the modal, or used standalone as any other PM type
