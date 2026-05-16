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
from checklist_parser import parse_template, get_interactive_steps
from telegram_alert import send_startup_alert

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

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), config["app"]["upload_folder"])
MAX_MB = int(config["app"].get("max_upload_mb", 16))
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_MB * 1024 * 1024

ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "bmp", "webp", "pdf"}

CHECKLIST_DIR = os.path.join(os.path.dirname(__file__), config["checklist"]["template_dir"])


def get_available_checklists():
    """Scan CHECKLIST_DIR for .txt files and return list of (filename, display_name)."""
    checklists = []
    if not os.path.isdir(CHECKLIST_DIR):
        return checklists
    for fname in sorted(os.listdir(CHECKLIST_DIR)):
        if fname.lower().endswith(".txt") and not fname.startswith("#"):
            # Convert filename to display name: "quarterly_pm.txt" -> "Quarterly PM"
            display = os.path.splitext(fname)[0].replace("_", " ").title()
            checklists.append({"filename": fname, "display": display})
    return checklists


def load_checklist_by_name(template_name):
    """Load and parse a checklist by filename."""
    path = os.path.join(CHECKLIST_DIR, template_name)
    if not os.path.isfile(path):
        # Fallback: first available checklist
        files = [f for f in os.listdir(CHECKLIST_DIR) if f.endswith(".txt")]
        if not files:
            return []
        path = os.path.join(CHECKLIST_DIR, sorted(files)[0])
    return parse_template(path)

# ─── DB Init ──────────────────────────────────────────────────────────────────

db.load_config(CONFIG_PATH)
db.init_db()

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
    return render_template(
        "complete.html",
        pm_session=pm_session,
        events=events,
        sections=sections,
    )


@app.route("/session/<int:session_id>/report")
def session_report(session_id):
    pm_session = db.get_session(session_id)
    events = db.get_session_events(session_id)
    sections = load_checklist_by_name(pm_session["template_name"])
    return render_template(
        "report.html",
        pm_session=pm_session,
        events=events,
        sections=sections,
    )


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
