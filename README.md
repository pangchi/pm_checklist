# PM Checklist — Preventive Maintenance System

A production-ready Flask + PostgreSQL application for managing digital preventive maintenance checklists. Supports multiple checklist types, sequential step enforcement, photo attachments, browser-local timestamps, Telegram startup alerts, mobile-responsive UI, and full checklist versioning with diff comparison.

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
14. [Changelog](#changelog)

---

## Features

| Feature | Details |
|---|---|
| **Multiple checklist types** | Weekly, Monthly, Quarterly, Annual — or any custom type |
| **Checklist versioning** | Upload new versions, compare diffs, activate/archive, download |
| **Sequential steps** | Steps must be completed in order; skipping is blocked at UI and server level |
| **Three step types** | `STEP` (checkbox), `STEP_VALUE` (checkbox + value input), `PHOTO` (checkbox + photo upload) |
| **Notes** | `NOTE:` lines display as read-only informational banners |
| **DB-gated advancement** | Next Section button only enables after every step in the section is confirmed written to DB |
| **Session resume** | Returning to an in-progress session restores all completed steps, values, and photo filenames |
| **Auto WO numbering** | Work order numbers auto-generated as `WO-YYYYMMDD-NNN` |
| **No duplicate sessions** | Only one active session allowed per work order |
| **Browser timezone** | All timestamps displayed in the browser's local timezone; DB stores UTC |
| **Telegram startup alert** | Sends hostname, local IP, and public IP to a Telegram chat on startup |
| **Mobile-first UI** | Hamburger nav, card-list views, fixed bottom footer, camera capture for photos |
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
├── telegram_alert.py               # Startup Telegram notification
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
│   ├── css/style.css               # Full mobile-first stylesheet
│   ├── js/main.js                  # Flash auto-dismiss
│   └── uploads/                    # Photo files (session_<id>/<filename>)
│
└── templates/
    ├── base.html                   # Nav, hamburger, TZ detection, fmtUTC helper
    ├── index.html                  # Dashboard with session list
    ├── personnel.html              # Add/list personnel
    ├── workorders.html             # Create/list work orders
    ├── start_session.html          # Start or resume a PM session
    ├── checklist.html              # Step-by-step checklist execution
    ├── complete.html               # Session completion summary
    ├── report.html                 # Printable audit report
    ├── checklists.html             # Checklist template library
    ├── checklist_versions.html     # Version history, upload, activate
    └── checklist_compare.html      # Side-by-side unified diff
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
4. Run schema migrations (safe to re-run)
5. Seed any `.txt` files from `checklists/` into the versioning table
6. Send a Telegram startup alert (if configured)
7. Start the Flask server at `http://0.0.0.0:5000`

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

[checklist]
template_dir = checklists      # Directory scanned for seed .txt files

[telegram]
bot_token =                    # From @BotFather on Telegram
chat_id   =                    # From @userinfobot or getUpdates API
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
| `checked` | BOOLEAN | Always TRUE (only completed steps are recorded) |
| `value_input` | TEXT | Entered measurement (STEP_VALUE only) |
| `photo_path` | TEXT | Relative path under `static/uploads/` (PHOTO only) |
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
| `/api/tz` | POST (JSON) | Register browser UTC offset (cookie) |

---

## Checklist Versioning

Templates are stored in the `checklist_versions` table with full version history.

### How it works

- On startup, any `.txt` files in `checklists/` are **seeded** as v1 of their respective checklist (skipped if identical content already exists, detected via SHA-256)
- Each upload increments the version counter for that checklist name
- Uploading identical content (same SHA-256) is rejected with an error — no no-op versions
- Exactly one version per checklist name is marked `is_active = TRUE`
- All new sessions use the **active version** at session creation time
- Existing in-progress sessions are unaffected by version changes (the `template_name` is immutable per session)

### Activate a version

Go to **Templates → `<checklist name>`** → click **Activate** on any archived version. The previous active version is immediately demoted.

### Compare versions

1. From the version history page, click **⇄ Compare** on any version, or navigate directly to **⇄ Compare** at the top
2. Select Version A (from) and Version B (to)
3. A colour-coded unified diff is rendered:
   - 🟢 Green lines — added in Version B
   - 🔴 Red lines — removed from Version A
   - Blue lines — chunk headers (`@@`)
4. Download either version directly from the comparison page

### Archive

Old versions are never deleted. They remain in the database and can be downloaded, viewed, compared, or re-activated at any time.

---

## Telegram Alerts

On startup, the app sends a message to a configured Telegram chat:

```
🟢 PM Checklist — Server Started

🖥 Hostname:  myserver
🔌 Local IP:  192.168.1.50:5000
🌐 Public IP: 203.x.x.x

🔗 Access: http://192.168.1.50:5000  ← tappable link
🌍 Public: http://203.x.x.x:5000    ← tappable link (if public IP detected)
```

- Uses `parse_mode="HTML"` with `<a href="...">` links for reliable tap-to-open behaviour
- `disable_web_page_preview: true` prevents Telegram from unfulring the URL into a card
- Public IP fetched from `api.ipify.org` (5-second timeout, silently skipped if offline)
- If `bot_token` or `chat_id` is blank in `config.ini`, the alert is silently skipped — no crash

---

## Timezone Handling

**Rule: store in UTC, display in browser local time.**

- All `TIMESTAMP` columns in PostgreSQL are `TIMESTAMPTZ` (timezone-aware, always UTC)
- On every page load, a small JavaScript snippet reads `new Date().getTimezoneOffset()` and POSTs the browser's UTC offset in minutes to `/api/tz`, which stores it in a 1-year cookie named `tz_offset`
- If the offset changes (e.g. DST transition, different device), the page reloads once to re-render with the correct offset
- Server-side: the Jinja filter `| localdt` reads the `tz_offset` cookie and converts any UTC datetime to local before rendering
- Client-side: live AJAX timestamps (recorded during checklist execution) are returned as ISO 8601 strings (`2026-05-16T10:30:00Z`) and converted to local time in the browser using `window.fmtUTC(isoStr)` via `Intl.DateTimeFormat`

---

## Mobile Support

The UI is designed mobile-first and tested at 360 px viewport width.

| Feature | Implementation |
|---|---|
| **Hamburger menu** | Replaces desktop nav links below 640 px; closes on backdrop tap or link tap |
| **Card-list views** | Tables replaced by stacked cards on mobile (personnel, work orders, sessions, version history) |
| **Fixed bottom footer** | On the checklist execution page, the Previous / Next buttons are in a fixed bar above the browser chrome |
| **44 px touch targets** | All buttons and checkboxes meet minimum touch target size |
| **Camera capture** | `PHOTO` step file inputs include `capture="environment"` — opens the rear camera directly on Android and iOS |
| **No iOS zoom on input focus** | All `<input>` and `<select>` elements use `font-size: 1rem` to prevent iOS auto-zoom |
| **Scroll to next step** | After completing a step, the newly unlocked step scrolls into view automatically |
| **Safe area insets** | `viewport-fit=cover` meta tag with `env(safe-area-inset-*)` support for notched phones |

---

## Sequential Step Enforcement

Steps within a section must be completed in strict order. Skipping is blocked at two independent layers:

### UI layer
- Only the **next incomplete step** receives the `step-active` class (cyan left border, pulsing ring)
- All subsequent steps have the `step-locked` class: 45% opacity, `pointer-events: none`, all inputs `disabled`
- After a step is confirmed saved, `unlockNextStep()` activates the next one and scrolls it into view

### Server layer
The `/session/<id>/step/check` endpoint walks all interactive steps in order before accepting any write. If any step before the submitted one is missing from `checklist_events`, the request is rejected with HTTP 400 and an error message — bypassing the UI via API calls or browser devtools is blocked.

### Section navigation
Breadcrumb crumbs for future incomplete sections are rendered with `crumb-locked` (dashed border, `cursor: not-allowed`) and have no click handler. Only completed sections and the current section are navigable.

---

## Changelog

### v1.0 — Initial Release
- Flask application with PostgreSQL backend
- Single editable `.txt` checklist template (`checklists/checklist_template.txt`)
- Three step types: `STEP`, `STEP_VALUE`, `PHOTO`
- Personnel and work order management
- PM session tracking with section-by-section execution
- DB-gated Next Section button — advances only after all steps confirmed written
- Photo uploads stored to `static/uploads/`
- Printable per-session audit report
- Auto database and table creation on first startup
- Separate `config.ini` for all credentials and settings

### v1.1 — Auto WO Number & Duplicate Session Guard
- Work order numbers auto-generated: `WO-YYYYMMDD-NNN`, daily sequence resets
- WO number input removed from the create form
- `get_active_session_for_wo()` — blocks starting a new session if the WO already has one `in_progress`
- Start Session page shows inline warning and "Resume" option when an active session exists
- Work Orders list shows a pulsing **LIVE** badge and Resume button for WOs with active sessions
- `get_all_work_orders_enriched()` — single query joining active and latest session IDs

### v1.2 — Multiple Checklist Types
- `config.ini` `[checklist]` section changed from `template_file` to `template_dir`
- `checklists/` directory scanned; any `.txt` file is available as a checklist type
- Display name derived from filename: `quarterly_pm.txt` → "Quarterly PM"
- Four built-in templates: `weekly_pm.txt`, `monthly_pm.txt`, `quarterly_pm.txt`, `annual_pm.txt`
- `work_orders` table gains `checklist_name` column (with `ADD COLUMN IF NOT EXISTS` migration)
- Work order creation includes a checklist type dropdown
- Session creation uses the WO's assigned checklist; the checklist name is frozen on the session record
- Removed all equipment-specific placeholder text (generic "Equipment Name" used throughout)

### v1.3 — Server Timezone → Browser Timezone
- Reverted from server-local `TIMESTAMP` to `TIMESTAMPTZ` (UTC) for all timestamp columns
- Removed `SET TIME ZONE` hack from PostgreSQL connections
- Added `ALTER TABLE … TYPE TIMESTAMPTZ USING … AT TIME ZONE 'UTC'` migration for existing columns
- `base.html` injects browser UTC offset detection on page load, POSTed to `/api/tz` cookie
- Jinja filter `| localdt` converts UTC datetimes to browser-local for all server-rendered timestamps
- Live AJAX timestamps returned as ISO 8601 strings; `window.fmtUTC()` converts client-side
- All template `strftime` calls replaced with `| localdt` filter

### v1.4 — Telegram Startup Alert
- New module `telegram_alert.py` (stdlib only — no third-party libraries)
- `config.ini` gains `[telegram]` section: `bot_token`, `chat_id`
- On startup: collects hostname, local IP (UDP probe), public IP (`api.ipify.org`)
- Message uses `parse_mode="HTML"` with `<a href>` links — guaranteed clickable in Telegram
- `disable_web_page_preview: true` prevents link unfurling
- Silently skipped if `bot_token` or `chat_id` is blank

### v1.5 — Mobile-Friendly UI
- Full CSS rewrite: mobile-first, 640 px and 380 px breakpoints
- Hamburger navigation with slide-down drawer, closes on backdrop tap
- All data tables replaced by card-list views on mobile (`display:none` / `display:flex` swap)
- `data-table` wrapped in `.table-wrap` for horizontal scroll on narrow screens
- Checklist page: fixed bottom footer bar on mobile (Previous ← / Next →)
- `check-btn` enlarged to 44 × 44 px minimum touch target
- `PHOTO` steps use `capture="environment"` for direct rear-camera access on mobile
- All form inputs set to `font-size: 1rem` to prevent iOS auto-zoom on focus
- Custom `<select>` chevron via SVG background image
- `scrollIntoView({behavior:'smooth'})` on step unlock
- `viewport-fit=cover` and Apple mobile web app meta tags

### v1.6 — Sequential Step Enforcement
- Steps within a section must be completed strictly in order
- Three CSS states: `step-done` (✓), `step-active` (pulsing ring, cyan border), `step-locked` (dimmed, non-interactive)
- `next_step_key` computed server-side and passed to template
- `step-locked` steps: `disabled` on checkbox, value input, and photo input; `pointer-events: none` via CSS
- `unlockNextStep()` JS function: after DB confirmation, activates the next locked step and scrolls it into view
- Server-side guard in `/session/<id>/step/check`: walks all steps in order, rejects with HTTP 400 if any prior step is incomplete
- Breadcrumb crumbs for future sections rendered as `crumb-locked` (dashed, non-clickable)

### v1.7 — Session Resume / Progress Restore
- `get_session_events_dict()` — returns all completed events keyed by `step_key`
- `get_resume_section()` — finds the first section with any incomplete step
- `checklist_view` without `?section=` auto-redirects to the resume section
- Completed `STEP_VALUE` inputs rendered with `value="..."` restored from DB
- Completed `PHOTO` steps show the original filename in the upload label
- Timestamps on already-completed steps show the exact recorded UTC time (converted to browser local)
- `uploadedPhotos` JS dict pre-populated from DB events so re-checking photo steps finds the existing path
- Breadcrumb crumbs coloured by actual DB completion, not just section position

### v1.8 — Checklist Versioning
- New DB table `checklist_versions`: stores full content, SHA-256 checksum, version number, uploader, notes, active flag
- New module function `parse_template_from_string()` — parses from DB content string, no file I/O
- New function `validate_template()` — returns list of errors/warnings (sections, steps, duplicates, unknown prefixes)
- Startup seeds all `.txt` files from `checklists/` into the versions table (idempotent via checksum)
- `load_checklist_by_name()` reads the active version from DB (falls back to disk)
- `get_available_checklists()` reads from DB (falls back to disk scan)
- Duplicate content detection: SHA-256 comparison rejects identical uploads
- New pages: `/checklists` (library), `/checklists/<name>` (version history), `/checklists/compare` (diff)
- AJAX validation endpoint `/checklists/validate`: returns errors + summary (sections, steps, photos, values) before upload
- Submit button disabled until validation passes
- Inline content viewer (modal) for any version
- Unified diff via `difflib.unified_diff` with colour-coded rendering
- Version activation: one-click promote any archived version; previous active demoted atomically
- Download any version as a `.txt` file with version number in filename
- **Templates** link added to desktop nav and mobile drawer
- **Bugfix:** `RealDictCursor.fetchone()[0]` `KeyError` fixed — scalar `COALESCE(MAX(version))` queries now use a plain cursor
