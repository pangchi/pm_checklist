# PM Checklist — Preventive Maintenance Flask App

A Flask-based digital preventive maintenance checklist system with PostgreSQL persistence, photo attachments, timestamped step recording, and editable checklist templates.

---

## Features

- **Editable checklist template** — plain `.txt` file, no code changes needed
- **Three step types**: plain checkbox (`STEP`), checkbox with value input (`STEP_VALUE`), photo attachment (`PHOTO`)
- **Timestamped DB writes** — every checkbox click is recorded in PostgreSQL; user can only advance to the next section after all steps are inserted
- **Photo attachments** — upload images per step, stored on disk, path stored in DB
- **Work Orders & Personnel** stored in PostgreSQL
- **Session tracking** — each PM run tied to a WO + technician
- **Printable reports** — full audit trail per session
- **Auto DB creation** — database and all tables created on first startup
- **Separate config file** — `config.ini` for DB credentials, app settings

---

## Project Structure

```
pm_checklist/
├── app.py                        # Main Flask application
├── db.py                         # Database layer (auto-creates DB/tables)
├── checklist_parser.py           # .txt template parser
├── config.ini                    # ← Edit DB credentials here
├── requirements.txt
├── checklists/
│   └── checklist_template.txt    # ← Edit your checklist here
├── static/
│   ├── css/style.css
│   ├── js/main.js
│   └── uploads/                  # Photo uploads stored here
└── templates/
    ├── base.html
    ├── index.html
    ├── checklist.html
    ├── personnel.html
    ├── workorders.html
    ├── start_session.html
    ├── complete.html
    └── report.html
```

---

## Setup

### 1. Prerequisites

- Python 3.10+
- PostgreSQL 13+ running locally (or remote)

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure

Edit `config.ini`:

```ini
[database]
host = localhost
port = 5432
name = pm_checklist      ; DB will be auto-created if it doesn't exist
user = postgres
password = yourpassword

[app]
secret_key = change-this-to-a-random-string
port = 5000
debug = true
```

### 4. Run

```bash
python app.py
```

The app will:
1. Connect to PostgreSQL using the `postgres` maintenance DB
2. Create the `pm_checklist` database if it doesn't exist
3. Create all required tables
4. Start the Flask server at `http://localhost:5000`

---

## Editing the Checklist Template

Open `checklists/checklist_template.txt` in any text editor. The template is reloaded on every request — no restart needed.

**Syntax:**

| Line prefix | Meaning |
|---|---|
| `# comment` | Ignored |
| `SECTION: Title` | Creates a new section header |
| `STEP: Description` | Checkbox only |
| `STEP_VALUE: Description` | Checkbox + required text/number input |
| `PHOTO: Description` | Checkbox + required photo upload |
| `NOTE: Text` | Read-only informational note |

All interactive steps in a section must be completed (written to DB) before the user can advance to the next section.

---

## Workflow

1. Add **Personnel** (name + badge)
2. Create a **Work Order** (WO number + equipment)
3. **Start a PM Session** — select WO and technician
4. Work through **sections** — check each step:
   - `STEP` → click to complete
   - `STEP_VALUE` → enter a value, then click
   - `PHOTO` → upload a photo, then click
5. Each click calls `/session/<id>/step/check` → writes to DB with UTC timestamp
6. **Next Section** button only enables after all steps are DB-confirmed
7. On completion, a full **audit report** is available (printable)

---

## Database Schema

| Table | Purpose |
|---|---|
| `personnel` | Technicians / staff |
| `work_orders` | PM work orders |
| `pm_sessions` | Each PM run (WO + personnel) |
| `checklist_events` | Every checkbox click with timestamp, value, photo path |
