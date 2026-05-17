"""
app.py — Main Flask application for Preventive Maintenance Checklist.
"""

import os
import configparser
from datetime import datetime, timezone, timedelta
from flask import (
    Flask, render_template, request, jsonify, redirect, url_for,
    session, flash, send_from_directory
)
from werkzeug.utils import secure_filename

import db
from checklist_parser import parse_template, get_interactive_steps, parse_template_from_string, validate_template
from telegram_alert import send_startup_alert, send_telegram_message
from storage_manager import purge_if_needed, get_disk_usage_info, get_app_partition

# ─── Config ───────────────────────────────────────────────────────────────────

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.ini")
config = configparser.ConfigParser()
config.read(CONFIG_PATH)

app = Flask(__name__)
app.secret_key = config["app"]["secret_key"]


# ─── Jinja filter: format UTC datetime → browser-local time ──────────────────
# The browser stores its UTC offset (minutes) in a cookie "tz_offset".
# We apply it here so all server-rendered timestamps respect the client's TZ.

def _browser_offset_minutes():
    """Return the browser's UTC offset in minutes from cookie, or 0 (UTC)."""
    try:
        return int(request.cookies.get("tz_offset", "0"))
    except (ValueError, TypeError):
        return 0


def format_dt(value, fmt="%Y-%m-%d %H:%M:%S"):
    """Convert a UTC-aware (or naive-UTC) datetime to browser local time."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    # Ensure UTC-aware
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    offset_min = _browser_offset_minutes()
    local_dt = value.astimezone(timezone(timedelta(minutes=offset_min)))
    return local_dt.strftime(fmt)


app.jinja_env.filters["localdt"] = format_dt


@app.context_processor
def inject_theme():
    """Make active theme available in all templates.
    Fully defensive — never raises, always returns valid values."""
    _fallback = "industrial_dark"
    try:
        active = db.get_setting("theme", DEFAULT_THEME)
    except Exception:
        active = _fallback

    # Ensure active is actually in THEMES dict
    if not active or active not in THEMES:
        active = DEFAULT_THEME if DEFAULT_THEME in THEMES else _fallback

    # Final safety: if THEMES is somehow empty, return bare defaults
    meta = THEMES.get(active) or {"name": "Default", "dark": True,
                                   "accent": "#00c8ff", "bg": "#0f1117"}
    return {
        "active_theme": active,
        "theme_meta":   meta,
        "theme_css":    f"css/themes/{active}.css",
    }

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), config["app"]["upload_folder"])
MAX_MB = int(config["app"].get("max_upload_mb", 16))
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_MB * 1024 * 1024

ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "bmp", "webp", "pdf"}

CHECKLIST_DIR = os.path.join(os.path.dirname(__file__), config["checklist"]["template_dir"])
THEMES_DIR    = os.path.join(os.path.dirname(__file__), "static", "css", "themes")

# Theme metadata: filename stem → display info
THEMES = {
    "industrial_dark": {"name": "Industrial Dark", "accent": "#00c8ff", "bg": "#0f1117", "dark": True},
    "clean_light":     {"name": "Clean Light",     "accent": "#2563eb", "bg": "#f4f5f7", "dark": False},
    "midnight_navy":   {"name": "Midnight Navy",   "accent": "#7c6af7", "bg": "#060b18", "dark": True},
    "forest_green":    {"name": "Forest Green",    "accent": "#4ade80", "bg": "#0c1a0e", "dark": True},
    "warm_amber":      {"name": "Warm Amber",      "accent": "#f59e0b", "bg": "#1a1208", "dark": True},
    "arctic_white":    {"name": "Arctic White",    "accent": "#0ea5e9", "bg": "#f8fafc", "dark": False},
    "crimson_steel":   {"name": "Crimson Steel",   "accent": "#ef4444", "bg": "#0e0a0a", "dark": True},
    "pastel_studio":   {"name": "Pastel Studio",   "accent": "#c084fc", "bg": "#1e1a2e", "dark": True},
}
DEFAULT_THEME = config["app"].get("theme", "industrial_dark")


def _seed_checklists():
    """Seed all .txt files from CHECKLIST_DIR into the DB on startup."""
    if not os.path.isdir(CHECKLIST_DIR):
        return
    for fname in sorted(os.listdir(CHECKLIST_DIR)):
        if fname.lower().endswith(".txt") and not fname.startswith(("#", ".")):
            db.seed_checklist_from_file(os.path.join(CHECKLIST_DIR, fname))


def get_available_checklists():
    """Return active checklist versions from DB."""
    rows = db.get_available_checklists_from_db()
    if rows:
        return rows
    # Fallback: scan disk (e.g. before first seed)
    checklists = []
    if os.path.isdir(CHECKLIST_DIR):
        for fname in sorted(os.listdir(CHECKLIST_DIR)):
            if fname.lower().endswith(".txt") and not fname.startswith("#"):
                display = os.path.splitext(fname)[0].replace("_", " ").title()
                checklists.append({"filename": fname, "display": display,
                                   "checklist_name": os.path.splitext(fname)[0]})
    return checklists


def load_checklist_by_name(template_name):
    """Load and parse the active version of a checklist from DB."""
    # template_name may be "weekly_pm.txt" or "weekly_pm"
    name = os.path.splitext(template_name)[0]
    row = db.get_active_version(name)
    if row:
        return parse_template_from_string(row["content"])
    # Fallback to disk
    path = os.path.join(CHECKLIST_DIR, template_name)
    if not os.path.isfile(path):
        files = [f for f in os.listdir(CHECKLIST_DIR) if f.endswith(".txt")]
        if not files:
            return []
        path = os.path.join(CHECKLIST_DIR, sorted(files)[0])
    return parse_template(path)

# ─── DB Init ──────────────────────────────────────────────────────────────────

db.load_config(CONFIG_PATH)
db.init_db()


# ─── Storage management ───────────────────────────────────────────────────────

def _storage_dsn() -> dict:
    """Return psycopg2 DSN dict from config."""
    sec = config["database"]
    return {
        "host":     sec["host"],
        "port":     int(sec["port"]),
        "dbname":   sec["name"],
        "user":     sec["user"],
        "password": sec["password"],
    }


def _run_storage_check():
    """Check disk usage and purge oldest photos if over threshold. Sends Telegram alert."""
    stor = config["storage"] if "storage" in config else {}
    threshold = float(stor.get("disk_threshold_pct", 80))
    partition  = APP_PARTITION

    summary = purge_if_needed(
        upload_folder=UPLOAD_FOLDER,
        dsn=_storage_dsn(),
        threshold_pct=threshold,
        partition=partition,
    )

    if summary is None:
        return   # Under threshold — nothing to report

    # Build Telegram alert
    tg = config["telegram"] if "telegram" in config else {}
    bot_token = tg.get("bot_token", "").strip()
    chat_id   = tg.get("chat_id",   "").strip()

    if bot_token and chat_id:
        status_icon = "⚠" if summary["error"] else "🗑"
        lines = [
            f"{status_icon} <b>PM Checklist — Auto Photo Purge</b>",
            "",
            f"📊 Disk was at <b>{summary['triggered_at_pct']}%</b> (threshold {threshold:.0f}%)",
            f"✅ Disk now at <b>{summary['final_pct']}%</b>",
            f"🗑 Deleted <b>{summary['deleted_count']}</b> photo(s) — freed <b>{summary['freed_human']}</b>",
            f"📷 Remaining photos in DB: {summary['remaining_photos']}",
        ]
        if summary["deleted"]:
            lines.append("")
            lines.append("<b>Deleted files:</b>")
            for d in summary["deleted"][:10]:   # cap at 10 to avoid huge messages
                lines.append(
                    f"  • {d['wo_number']} / {d['equipment']} — "
                    f"<code>{d['photo_path']}</code>"
                )
            if len(summary["deleted"]) > 10:
                lines.append(f"  … and {len(summary['deleted']) - 10} more")
        if summary["error"]:
            lines += ["", f"❌ Error: <code>{summary['error']}</code>"]

        send_telegram_message(bot_token, chat_id, "\n".join(lines))

# Detect the partition where this app resides — used for all disk checks
APP_PARTITION = get_app_partition(os.path.abspath(__file__))


# ─── Helpers ──────────────────────────────────────────────────────────────────

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


# ─── Routes: Home / Dashboard ─────────────────────────────────────────────────

@app.route("/")
def index():
    sessions = db.get_recent_sessions(30)
    return render_template("index.html", sessions=sessions)


# ─── Routes: Personnel ────────────────────────────────────────────────────────

@app.route("/personnel")
def personnel_list():
    people = db.get_all_personnel()
    return render_template("personnel.html", people=people)


@app.route("/personnel/add", methods=["POST"])
def personnel_add():
    name = request.form.get("name", "").strip()
    badge = request.form.get("badge", "").strip()
    dept = request.form.get("department", "").strip()
    if not name or not badge:
        flash("Name and badge number are required.", "error")
    else:
        try:
            db.add_personnel(name, badge, dept)
            flash(f"Personnel '{name}' added.", "success")
        except Exception as e:
            flash(f"Error: {e}", "error")
    return redirect(url_for("personnel_list"))


# ─── Routes: Work Orders ──────────────────────────────────────────────────────

@app.route("/workorders")
def wo_list():
    wos = db.get_all_work_orders_enriched()
    today = datetime.now().strftime("%Y%m%d")
    checklists = get_available_checklists()
    return render_template("workorders.html", wos=wos, today=today, checklists=checklists)


@app.route("/workorders/add", methods=["POST"])
def wo_add():
    equipment = request.form.get("equipment", "").strip()
    description = request.form.get("description", "").strip()
    checklist_name = request.form.get("checklist_name", "").strip()
    if not equipment:
        flash("Equipment name is required.", "error")
    elif not checklist_name:
        flash("Please select a checklist type.", "error")
    else:
        available = [c["filename"] for c in get_available_checklists()]
        if checklist_name not in available:
            flash("Invalid checklist selected.", "error")
        else:
            try:
                wo = db.add_work_order(equipment, description, checklist_name)
                flash(f"Work Order '{wo['wo_number']}' created.", "success")
            except Exception as e:
                flash(f"Error: {e}", "error")
    return redirect(url_for("wo_list"))


# ─── Routes: Start a PM Session ───────────────────────────────────────────────

@app.route("/session/start", methods=["GET", "POST"])
def session_start():
    people = db.get_all_personnel()
    wos = [w for w in db.get_all_work_orders_enriched() if w["status"] in ("open", "in_progress")]

    if request.method == "POST":
        wo_id = request.form.get("wo_id")
        personnel_id = request.form.get("personnel_id")
        if not wo_id or not personnel_id:
            flash("Work order and personnel are required.", "error")
            return render_template("start_session.html", people=people, wos=wos)

        wo_id = int(wo_id)

        # Block multiple active sessions for the same WO
        existing = db.get_active_session_for_wo(wo_id)
        if existing:
            flash(
                f"Work Order already has an active session started by "
                f"{existing['personnel_name']}. Resuming existing session.",
                "error",
            )
            return redirect(url_for("checklist_view", session_id=existing["id"]))

        wo = db.get_work_order(wo_id)
        sess = db.create_session(wo_id, int(personnel_id), wo["checklist_name"])
        return redirect(url_for("checklist_view", session_id=sess["id"]))

    return render_template("start_session.html", people=people, wos=wos)


# ─── Routes: Checklist Execution ──────────────────────────────────────────────

@app.route("/session/<int:session_id>/checklist")
def checklist_view(session_id):
    pm_session = db.get_session(session_id)
    if not pm_session:
        flash("Session not found.", "error")
        return redirect(url_for("index"))

    # Completed session -> go straight to summary
    if pm_session["status"] == "completed":
        return redirect(url_for("session_complete", session_id=session_id))

    sections = load_checklist_by_name(pm_session["template_name"])

    # No explicit section -> auto-resume at first incomplete section
    if "section" not in request.args:
        resume_idx = db.get_resume_section(session_id, sections)
        if resume_idx >= len(sections):
            return redirect(url_for("session_complete", session_id=session_id))
        return redirect(url_for("checklist_view", session_id=session_id, section=resume_idx))

    section_idx = int(request.args.get("section", 0))
    if section_idx >= len(sections):
        return redirect(url_for("session_complete", session_id=session_id))

    section = sections[section_idx]
    # Full event detail keyed by step_key -- restores values & photos on reload
    events_dict = db.get_session_events_dict(session_id)
    completed_keys = set(events_dict.keys())
    interactive_steps = get_interactive_steps(section)
    total_sections = len(sections)

    section_done = all(s["key"] in completed_keys for s in interactive_steps)

    # First incomplete interactive step — all steps after it are locked
    next_step_key = None
    for s in interactive_steps:
        if s["key"] not in completed_keys:
            next_step_key = s["key"]
            break

    corrective_sessions = db.get_corrective_sessions(session_id)

    return render_template(
        "checklist.html",
        pm_session=pm_session,
        section=section,
        section_idx=section_idx,
        total_sections=total_sections,
        all_sections=sections,
        completed_keys=completed_keys,
        events_dict=events_dict,
        section_done=section_done,
        interactive_steps=interactive_steps,
        next_step_key=next_step_key,
        corrective_sessions=corrective_sessions,
        available_checklists=get_available_checklists(),
        all_personnel=db.get_all_personnel(),
    )


@app.route("/session/<int:session_id>/step/check", methods=["POST"])
def step_check(session_id):
    """AJAX endpoint: record a step checkbox event to DB."""
    data = request.get_json(force=True)

    section_index = data.get("section_index")
    step_index = data.get("step_index")
    step_key = data.get("step_key")
    step_type = data.get("step_type")
    step_label = data.get("step_label")
    value_input = data.get("value_input") or None
    photo_path = data.get("photo_path") or None

    # Enforce sequential order — reject if a previous step is still incomplete
    from checklist_parser import get_interactive_steps as _gis
    _sections = load_checklist_by_name(
        db.get_session(session_id)["template_name"]
    )
    _completed = db.get_completed_steps(session_id)
    for _sec in _sections:
        for _st in _gis(_sec):
            if _st["key"] == step_key:
                break  # reached the step being submitted — all prior done
            if _st["key"] not in _completed:
                return jsonify({
                    "success": False,
                    "error": "Steps must be completed in order. Please complete the previous step first."
                }), 400
        else:
            continue
        break

    # Validate required value
    if step_type == "STEP_VALUE" and not value_input:
        return jsonify({"success": False, "error": "A value is required for this step."}), 400

    # Photo must be uploaded before checking
    if step_type == "PHOTO" and not photo_path:
        return jsonify({"success": False, "error": "A photo must be attached before completing this step."}), 400

    try:
        row = db.record_step(
            session_id=session_id,
            section_index=section_index,
            step_index=step_index,
            step_key=step_key,
            step_type=step_type,
            step_label=step_label,
            value_input=value_input,
            photo_path=photo_path,
        )
        if row is None:
            # Already exists — still OK
            return jsonify({"success": True, "already_done": True, "utc_ts": None})

        # Return as UTC ISO string; browser converts to local time via fmtUTC()
        ts = row["timestamp"]
        if ts is not None:
            # psycopg2 returns timezone-aware datetime for TIMESTAMPTZ
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            utc_ts = ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            utc_ts = None
        return jsonify({"success": True, "utc_ts": utc_ts})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/session/<int:session_id>/upload_photo", methods=["POST"])
def upload_photo(session_id):
    """Upload a photo for a step, return the stored path."""
    if "photo" not in request.files:
        return jsonify({"success": False, "error": "No file part"}), 400

    file = request.files["photo"]
    if file.filename == "":
        return jsonify({"success": False, "error": "No file selected"}), 400

    if file and allowed_file(file.filename):
        step_key = request.form.get("step_key", "unknown")
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        ext = file.filename.rsplit(".", 1)[1].lower()
        filename = secure_filename(f"session{session_id}_{step_key}_{timestamp}.{ext}")
        save_dir = os.path.join(app.config["UPLOAD_FOLDER"], f"session_{session_id}")
        os.makedirs(save_dir, exist_ok=True)
        filepath = os.path.join(save_dir, filename)
        file.save(filepath)
        # Return web-accessible relative path
        rel_path = f"session_{session_id}/{filename}"

        # Check disk usage and purge oldest photos if threshold exceeded
        _run_storage_check()

        return jsonify({"success": True, "photo_path": rel_path, "filename": filename})

    return jsonify({"success": False, "error": "File type not allowed"}), 400


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/session/<int:session_id>/complete")
def session_complete(session_id):
    pm_session = db.get_session(session_id)
    if pm_session and pm_session["status"] != "completed":
        db.complete_session(session_id)
        pm_session = db.get_session(session_id)
    events = db.get_session_events(session_id)
    sections = load_checklist_by_name(pm_session["template_name"])
    corrective_sessions = db.get_corrective_sessions(session_id)
    return render_template(
        "complete.html",
        pm_session=pm_session,
        events=events,
        sections=sections,
        corrective_sessions=corrective_sessions,
    )


@app.route("/session/<int:session_id>/report")
def session_report(session_id):
    pm_session = db.get_session(session_id)
    events = db.get_session_events(session_id)
    sections = load_checklist_by_name(pm_session["template_name"])
    corrective_sessions = db.get_corrective_sessions(session_id)
    return render_template(
        "report.html",
        pm_session=pm_session,
        events=events,
        sections=sections,
        corrective_sessions=corrective_sessions,
    )


# ─── Storage Status ──────────────────────────────────────────────────────────

@app.route("/admin/storage")
def storage_status():
    stor = config["storage"] if "storage" in config else {}
    threshold = float(stor.get("disk_threshold_pct", 80))
    disk = get_disk_usage_info(APP_PARTITION)

    # Count photos and total size on disk
    photo_count = 0
    photo_size  = 0
    for root, dirs, files in os.walk(UPLOAD_FOLDER):
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                sz = os.path.getsize(fpath)
                photo_size  += sz
                photo_count += 1
            except OSError:
                pass

    # DB photo count
    import psycopg2
    conn = psycopg2.connect(**_storage_dsn())
    cur  = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM checklist_events WHERE photo_path IS NOT NULL")
    db_photo_count = cur.fetchone()[0]
    cur.close()
    conn.close()

    return render_template(
        "storage_status.html",
        disk=disk,
        threshold=threshold,
        partition=APP_PARTITION,
        photo_count=photo_count,
        photo_size_human=f"{photo_size/1e6:.1f} MB" if photo_size < 1e9 else f"{photo_size/1e9:.2f} GB",
        db_photo_count=db_photo_count,
    )


@app.route("/admin/storage/purge", methods=["POST"])
def storage_purge_manual():
    """Manually trigger a purge run regardless of current disk usage."""
    stor = config["storage"] if "storage" in config else {}
    partition = APP_PARTITION
    # Force purge by temporarily setting threshold to 0
    from storage_manager import get_disk_usage_pct
    summary = purge_if_needed(
        upload_folder=UPLOAD_FOLDER,
        dsn=_storage_dsn(),
        threshold_pct=0.0,   # always trigger
        partition=partition,
    )
    if summary and summary["deleted_count"] > 0:
        flash(f"Purged {summary['deleted_count']} photo(s), freed {summary['freed_human']}.", "success")
    else:
        flash("No photos to purge or purge had no effect.", "error")
    return redirect(url_for("storage_status"))


# ─── Checklist Version Management ────────────────────────────────────────────

@app.route("/checklists")
def checklist_list():
    names = db.get_all_checklist_names()
    return render_template("checklists.html", names=names)


@app.route("/checklists/<checklist_name>")
def checklist_detail(checklist_name):
    versions = db.get_checklist_versions(checklist_name)
    if not versions:
        flash(f"No versions found for '{checklist_name}'.", "error")
        return redirect(url_for("checklist_list"))
    active = next((v for v in versions if v["is_active"]), None)
    return render_template("checklist_versions.html",
                           checklist_name=checklist_name,
                           versions=versions,
                           active=active)


@app.route("/checklists/<checklist_name>/upload", methods=["POST"])
def checklist_upload(checklist_name):
    if "file" not in request.files:
        flash("No file selected.", "error")
        return redirect(url_for("checklist_detail", checklist_name=checklist_name))

    f = request.files["file"]
    notes = request.form.get("notes", "").strip()
    uploader = request.form.get("uploader", "").strip()

    if not f.filename or not f.filename.lower().endswith(".txt"):
        flash("Only .txt files are accepted.", "error")
        return redirect(url_for("checklist_detail", checklist_name=checklist_name))

    content_bytes = f.read()
    try:
        text = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        flash("File must be UTF-8 encoded.", "error")
        return redirect(url_for("checklist_detail", checklist_name=checklist_name))

    errors = validate_template(text)
    if errors:
        flash("Validation failed: " + " | ".join(errors[:5]), "error")
        return redirect(url_for("checklist_detail", checklist_name=checklist_name))

    row, err = db.upload_checklist_version(
        checklist_name, f.filename, text, notes, uploader
    )
    if err:
        flash(err, "error")
    else:
        flash(f"Version {row['version']} uploaded successfully.", "success")
    return redirect(url_for("checklist_detail", checklist_name=checklist_name))


@app.route("/checklists/new", methods=["POST"])
def checklist_new():
    """Upload a brand-new checklist type."""
    if "file" not in request.files:
        flash("No file selected.", "error")
        return redirect(url_for("checklist_list"))

    f = request.files["file"]
    checklist_name = request.form.get("checklist_name", "").strip().lower().replace(" ", "_")
    notes = request.form.get("notes", "").strip()
    uploader = request.form.get("uploader", "").strip()

    if not checklist_name:
        flash("Checklist name is required.", "error")
        return redirect(url_for("checklist_list"))
    if not f.filename or not f.filename.lower().endswith(".txt"):
        flash("Only .txt files are accepted.", "error")
        return redirect(url_for("checklist_list"))

    text = f.read().decode("utf-8", errors="replace")
    errors = validate_template(text)
    if errors:
        flash("Validation failed: " + " | ".join(errors[:5]), "error")
        return redirect(url_for("checklist_list"))

    row, err = db.upload_checklist_version(checklist_name, f.filename, text, notes, uploader)
    if err:
        flash(err, "error")
    else:
        db.set_active_version(row["id"])
        flash(f"New checklist '{checklist_name}' created (v1).", "success")
    return redirect(url_for("checklist_detail", checklist_name=checklist_name))


@app.route("/checklists/version/<int:version_id>/activate", methods=["POST"])
def checklist_activate(version_id):
    row = db.get_checklist_version(version_id)
    if not row:
        flash("Version not found.", "error")
        return redirect(url_for("checklist_list"))
    db.set_active_version(version_id)
    flash(f"Version {row['version']} of '{row['checklist_name']}' is now active.", "success")
    return redirect(url_for("checklist_detail", checklist_name=row["checklist_name"]))


@app.route("/checklists/version/<int:version_id>/download")
def checklist_download(version_id):
    from flask import Response
    row = db.get_checklist_version(version_id)
    if not row:
        flash("Version not found.", "error")
        return redirect(url_for("checklist_list"))
    fname = f"{row['checklist_name']}_v{row['version']}.txt"
    return Response(
        row["content"],
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment; filename={fname}"}
    )


@app.route("/checklists/validate", methods=["POST"])
def checklist_validate():
    """AJAX: validate uploaded .txt content and return preview + errors."""
    f = request.files.get("file")
    if not f:
        return jsonify({"ok": False, "errors": ["No file received."]})
    try:
        text = f.read().decode("utf-8")
    except Exception:
        return jsonify({"ok": False, "errors": ["Could not decode file as UTF-8."]})

    errors = validate_template(text)
    sections = parse_template_from_string(text) if not errors else []
    summary = {
        "sections": len(sections),
        "steps": sum(
            sum(1 for s in sec["steps"] if s["type"] == "STEP") for sec in sections
        ),
        "step_values": sum(
            sum(1 for s in sec["steps"] if s["type"] == "STEP_VALUE") for sec in sections
        ),
        "photos": sum(
            sum(1 for s in sec["steps"] if s["type"] == "PHOTO") for sec in sections
        ),
        "notes": sum(
            sum(1 for s in sec["steps"] if s["type"] == "NOTE") for sec in sections
        ),
    }
    return jsonify({"ok": len(errors) == 0, "errors": errors, "summary": summary})


@app.route("/checklists/compare")
def checklist_compare():
    v1_id = request.args.get("v1", type=int)
    v2_id = request.args.get("v2", type=int)
    checklist_name = request.args.get("name", "")

    versions = db.get_checklist_versions(checklist_name) if checklist_name else []
    v1 = db.get_checklist_version(v1_id) if v1_id else None
    v2 = db.get_checklist_version(v2_id) if v2_id else None

    diff_lines = []
    if v1 and v2:
        import difflib
        a = v1["content"].splitlines(keepends=True)
        b = v2["content"].splitlines(keepends=True)
        diff_lines = list(difflib.unified_diff(
            a, b,
            fromfile=f"v{v1['version']} ({v1['filename']})",
            tofile=f"v{v2['version']} ({v2['filename']})",
            lineterm=""
        ))

    return render_template("checklist_compare.html",
                           checklist_name=checklist_name,
                           versions=versions,
                           v1=v1, v2=v2,
                           diff_lines=diff_lines)


# ─── Corrective Actions ───────────────────────────────────────────────────────

@app.route("/session/<int:session_id>/corrective/start", methods=["POST"])
def corrective_start(session_id):
    """Start a corrective action session linked to a parent session."""
    parent = db.get_session(session_id)
    if not parent:
        return jsonify({"success": False, "error": "Parent session not found."}), 404

    checklist_name  = request.form.get("checklist_name", "").strip()
    issue_desc      = request.form.get("issue_description", "").strip()
    personnel_id    = request.form.get("personnel_id", parent["id"]).strip()

    if not checklist_name:
        flash("Please select a checklist for the corrective action.", "error")
        return redirect(url_for("checklist_view", session_id=session_id))

    if not issue_desc:
        flash("Please describe the issue that triggered this corrective action.", "error")
        return redirect(url_for("checklist_view", session_id=session_id))

    # Use parent's personnel if not specified
    if not personnel_id or not personnel_id.isdigit():
        personnel_id = parent["personnel_id"]

    corrective = db.create_session(
        wo_id=parent["wo_id"],
        personnel_id=int(personnel_id),
        template_name=checklist_name,
        session_type="corrective",
        parent_session_id=session_id,
        issue_description=issue_desc,
    )
    flash(f"Corrective action session started. Complete it and return to the main checklist.", "success")
    return redirect(url_for("checklist_view", session_id=corrective["id"]))


@app.route("/session/<int:session_id>/corrective/modal")
def corrective_modal_data(session_id):
    """AJAX: return data needed to populate the corrective action modal."""
    checklists = get_available_checklists()
    people     = db.get_all_personnel()
    session    = db.get_session(session_id)
    return jsonify({
        "checklists": [{"name": c["checklist_name"], "display": c["display"]} for c in checklists],
        "personnel":  [{"id": p["id"], "name": p["name"], "badge": p["badge"]} for p in people],
        "current_personnel_id": session["personnel_id"] if session else None,
    })


# ─── Settings ─────────────────────────────────────────────────────────────────

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        theme = request.form.get("theme", DEFAULT_THEME).strip()
        if theme in THEMES:
            db.set_setting("theme", theme)
            flash(f"Theme changed to '{THEMES[theme]['name']}'.", "success")
        else:
            flash("Invalid theme selection.", "error")
        return redirect(url_for("settings"))

    active = db.get_setting("theme", DEFAULT_THEME)
    return render_template("settings.html", themes=THEMES, active_theme=active)


@app.route("/settings/theme/<theme_id>", methods=["POST"])
def set_theme(theme_id):
    """Quick-set theme via AJAX."""
    if theme_id not in THEMES:
        return jsonify({"ok": False, "error": "Unknown theme"}), 400
    db.set_setting("theme", theme_id)
    return jsonify({"ok": True, "theme": theme_id})


# ─── API: browser timezone registration ──────────────────────────────────────

@app.route("/api/tz", methods=["POST"])
def api_tz():
    """Browser posts its UTC offset (minutes) once on page load; stored in cookie."""
    data = request.get_json(force=True) or {}
    offset = data.get("offset", 0)
    resp = jsonify({"ok": True})
    resp.set_cookie("tz_offset", str(int(offset)), max_age=86400 * 365, samesite="Lax")
    return resp


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    port = int(config["app"].get("port", 5000))
    _seed_checklists()  # Seed any disk .txt files into DB versions table
    _run_storage_check()  # Purge old photos if disk already over threshold

    # Send Telegram startup alert
    tg = config["telegram"] if "telegram" in config else {}
    bot_token = tg.get("bot_token", "").strip()
    chat_id   = tg.get("chat_id",   "").strip()
    send_startup_alert(bot_token, chat_id, app_port=port)

    app.run(
        host=config["app"].get("host", "0.0.0.0"),
        port=port,
        debug=config["app"].getboolean("debug", True),
    )
