"""
db.py — Database layer for PM Checklist application.
Auto-creates all required tables on first run.
"""

import psycopg2
import psycopg2.extras
from contextlib import contextmanager
import configparser
import os
from datetime import datetime
import hashlib

_config = None

def load_config(config_path="config.ini"):
    global _config
    _config = configparser.ConfigParser()
    _config.read(config_path)
    return _config


def get_dsn():
    db = _config["database"]
    return {
        "host": db["host"],
        "port": int(db["port"]),
        "dbname": db["name"],
        "user": db["user"],
        "password": db["password"],
    }


@contextmanager
def get_conn():
    """All timestamps stored as TIMESTAMPTZ (UTC). Display conversion is browser-side."""
    conn = psycopg2.connect(**get_dsn())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create database and all tables if they don't exist."""
    # First connect to 'postgres' default db to create our db if needed
    db = _config["database"]
    try:
        conn = psycopg2.connect(
            host=db["host"],
            port=int(db["port"]),
            dbname="postgres",
            user=db["user"],
            password=db["password"],
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (db["name"],)
        )
        if not cur.fetchone():
            cur.execute(f'CREATE DATABASE "{db["name"]}"')
            print(f"[DB] Created database: {db['name']}")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"[DB] Warning during DB creation check: {e}")

    # Now create tables
    ddl = """
    CREATE TABLE IF NOT EXISTS personnel (
        id          SERIAL PRIMARY KEY,
        name        TEXT NOT NULL,
        badge       TEXT UNIQUE NOT NULL,
        department  TEXT,
        created_at  TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS work_orders (
        id             SERIAL PRIMARY KEY,
        wo_number      TEXT UNIQUE NOT NULL,
        equipment      TEXT NOT NULL,
        description    TEXT,
        checklist_name TEXT NOT NULL DEFAULT 'weekly_pm.txt',
        status         TEXT DEFAULT 'open',   -- open, in_progress, completed
        created_at     TIMESTAMPTZ DEFAULT NOW(),
        updated_at     TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS pm_sessions (
        id                SERIAL PRIMARY KEY,
        wo_id             INTEGER REFERENCES work_orders(id),
        personnel_id      INTEGER REFERENCES personnel(id),
        template_name     TEXT NOT NULL,
        session_type      TEXT DEFAULT 'planned',   -- planned, corrective
        parent_session_id INTEGER REFERENCES pm_sessions(id) ON DELETE SET NULL,
        issue_description TEXT,                     -- reason corrective was raised
        status            TEXT DEFAULT 'in_progress',  -- in_progress, completed
        started_at        TIMESTAMPTZ DEFAULT NOW(),
        completed_at      TIMESTAMPTZ
    );

    CREATE TABLE IF NOT EXISTS checklist_events (
        id            SERIAL PRIMARY KEY,
        session_id    INTEGER REFERENCES pm_sessions(id) ON DELETE CASCADE,
        section_index INTEGER NOT NULL,
        step_index    INTEGER NOT NULL,
        step_key      TEXT NOT NULL,
        step_type     TEXT NOT NULL,      -- STEP, STEP_VALUE, PHOTO
        step_label    TEXT NOT NULL,
        checked       BOOLEAN DEFAULT TRUE,
        value_input   TEXT,
        photo_path    TEXT,
        timestamp     TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_events_session ON checklist_events(session_id);
    CREATE INDEX IF NOT EXISTS idx_sessions_wo    ON pm_sessions(wo_id);

    CREATE TABLE IF NOT EXISTS checklist_versions (
        id            SERIAL PRIMARY KEY,
        checklist_name TEXT NOT NULL,       -- logical name, e.g. "weekly_pm"
        version       INTEGER NOT NULL,
        filename      TEXT NOT NULL,        -- original uploaded filename
        content       TEXT NOT NULL,        -- full .txt file content
        checksum      TEXT NOT NULL,        -- sha256 of content
        notes         TEXT,                 -- uploader's change notes
        uploaded_by   TEXT,
        is_active     BOOLEAN DEFAULT FALSE,
        uploaded_at   TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE (checklist_name, version)
    );
    CREATE INDEX IF NOT EXISTS idx_cv_name ON checklist_versions(checklist_name);

    CREATE TABLE IF NOT EXISTS app_settings (
        key         TEXT PRIMARY KEY,
        value       TEXT NOT NULL,
        updated_at  TIMESTAMPTZ DEFAULT NOW()
    );
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(ddl)
        # Migration: add checklist_name column if missing
        cur.execute("""
            ALTER TABLE work_orders
            ADD COLUMN IF NOT EXISTS checklist_name TEXT NOT NULL DEFAULT 'weekly_pm.txt'
        """)
        # Migration: ensure timestamp columns are TIMESTAMPTZ (UTC-aware)
        for tbl_col in [
            ("personnel",        "created_at"),
            ("work_orders",      "created_at"),
            ("work_orders",      "updated_at"),
            ("pm_sessions",      "started_at"),
            ("pm_sessions",      "completed_at"),
            ("checklist_events", "timestamp"),
        ]:
            cur.execute(f"""
                ALTER TABLE {tbl_col[0]}
                ALTER COLUMN {tbl_col[1]} TYPE TIMESTAMPTZ
                USING {tbl_col[1]} AT TIME ZONE 'UTC'
            """)
        # Migration: add corrective action columns to pm_sessions
        for col_def in [
            ("session_type",      "TEXT DEFAULT 'planned'"),
            ("parent_session_id", "INTEGER REFERENCES pm_sessions(id) ON DELETE SET NULL"),
            ("issue_description", "TEXT"),
        ]:
            cur.execute(f"""
                ALTER TABLE pm_sessions
                ADD COLUMN IF NOT EXISTS {col_def[0]} {col_def[1]}
            """)
        cur.close()
    print("[DB] Tables verified/created. All timestamps stored in UTC (TIMESTAMPTZ).")


# ─── Personnel ────────────────────────────────────────────────────────────────

def get_all_personnel():
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM personnel ORDER BY name")
        return cur.fetchall()


def add_personnel(name, badge, department=""):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "INSERT INTO personnel (name, badge, department) VALUES (%s,%s,%s) RETURNING *",
            (name, badge, department),
        )
        return cur.fetchone()


def get_personnel(pid):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM personnel WHERE id=%s", (pid,))
        return cur.fetchone()


# ─── Work Orders ──────────────────────────────────────────────────────────────

def get_all_work_orders():
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM work_orders ORDER BY created_at DESC")
        return cur.fetchall()


def get_all_work_orders_enriched():
    """Work orders joined with their active/latest session IDs."""
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT
                w.*,
                active.id            AS active_session_id,
                active.personnel_name AS active_session_personnel,
                latest.id            AS latest_session_id
            FROM work_orders w
            LEFT JOIN LATERAL (
                SELECT s.id, p.name AS personnel_name
                FROM pm_sessions s
                JOIN personnel p ON p.id = s.personnel_id
                WHERE s.wo_id = w.id AND s.status = 'in_progress'
                ORDER BY s.started_at DESC LIMIT 1
            ) active ON TRUE
            LEFT JOIN LATERAL (
                SELECT id FROM pm_sessions
                WHERE wo_id = w.id
                ORDER BY started_at DESC LIMIT 1
            ) latest ON TRUE
            ORDER BY w.created_at DESC
        """)
        return cur.fetchall()


def generate_wo_number():
    """Generate WO number: WO-YYYYMMDD-NNN, incrementing daily sequence."""
    with get_conn() as conn:
        cur = conn.cursor()
        prefix = datetime.now().strftime("WO-%Y%m%d-")
        cur.execute(
            "SELECT wo_number FROM work_orders WHERE wo_number LIKE %s ORDER BY wo_number DESC LIMIT 1",
            (prefix + "%",),
        )
        row = cur.fetchone()
        if row:
            try:
                seq = int(row[0].split("-")[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:03d}"


def add_work_order(equipment, description="", checklist_name="weekly_pm.txt"):
    """Create a new work order with an auto-generated WO number."""
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # Generate number inside the same connection to avoid races
        prefix = datetime.now().strftime("WO-%Y%m%d-")
        cur.execute(
            "SELECT wo_number FROM work_orders WHERE wo_number LIKE %s ORDER BY wo_number DESC LIMIT 1",
            (prefix + "%",),
        )
        row = cur.fetchone()
        if row:
            try:
                seq = int(row["wo_number"].split("-")[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1
        wo_number = f"{prefix}{seq:03d}"
        cur.execute(
            """INSERT INTO work_orders (wo_number, equipment, description, checklist_name)
               VALUES (%s,%s,%s,%s) RETURNING *""",
            (wo_number, equipment, description, checklist_name),
        )
        return cur.fetchone()


def get_work_order(wid):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM work_orders WHERE id=%s", (wid,))
        return cur.fetchone()


def update_wo_status(wid, status):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE work_orders SET status=%s, updated_at=NOW() WHERE id=%s",
            (status, wid),
        )


# ─── PM Sessions ──────────────────────────────────────────────────────────────

def get_active_session_for_wo(wo_id):
    """Return the in_progress session for a WO, or None."""
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """SELECT s.*, w.wo_number, w.equipment, p.name AS personnel_name, p.badge
               FROM pm_sessions s
               JOIN work_orders w ON w.id = s.wo_id
               JOIN personnel   p ON p.id = s.personnel_id
               WHERE s.wo_id = %s AND s.status = 'in_progress'
               ORDER BY s.started_at DESC LIMIT 1""",
            (wo_id,),
        )
        return cur.fetchone()


def create_session(wo_id, personnel_id, template_name,
                   session_type="planned", parent_session_id=None, issue_description=None):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """INSERT INTO pm_sessions
               (wo_id, personnel_id, template_name, session_type, parent_session_id, issue_description)
               VALUES (%s,%s,%s,%s,%s,%s) RETURNING *""",
            (wo_id, personnel_id, template_name, session_type, parent_session_id, issue_description),
        )
        if session_type == "planned":
            update_wo_status(wo_id, "in_progress")
        return cur.fetchone()


def get_session(sid):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """SELECT s.*, w.wo_number, w.equipment, p.name AS personnel_name, p.badge,
                      ps_parent.id AS parent_id
               FROM pm_sessions s
               JOIN work_orders w ON w.id = s.wo_id
               JOIN personnel   p ON p.id = s.personnel_id
               LEFT JOIN pm_sessions ps_parent ON ps_parent.id = s.parent_session_id
               WHERE s.id=%s""",
            (sid,),
        )
        return cur.fetchone()


def get_corrective_sessions(parent_session_id: int):
    """Return all corrective sessions spawned from a given parent session."""
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """SELECT s.*, w.wo_number, w.equipment, p.name AS personnel_name,
                      p.badge, s.issue_description
               FROM pm_sessions s
               JOIN work_orders w ON w.id = s.wo_id
               JOIN personnel   p ON p.id = s.personnel_id
               WHERE s.parent_session_id = %s
               ORDER BY s.started_at ASC""",
            (parent_session_id,),
        )
        return cur.fetchall()


def complete_session(sid):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "UPDATE pm_sessions SET status='completed', completed_at=NOW() WHERE id=%s RETURNING wo_id",
            (sid,),
        )
        row = cur.fetchone()
        if row:
            update_wo_status(row["wo_id"], "completed")


def get_recent_sessions(limit=20):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """SELECT s.*, w.wo_number, w.equipment, p.name AS personnel_name
               FROM pm_sessions s
               JOIN work_orders w ON w.id = s.wo_id
               JOIN personnel   p ON p.id = s.personnel_id
               WHERE s.session_type = 'planned'
               ORDER BY s.started_at DESC LIMIT %s""",
            (limit,),
        )
        return cur.fetchall()


# ─── Checklist Events ─────────────────────────────────────────────────────────

def record_step(session_id, section_index, step_index, step_key, step_type,
                step_label, value_input=None, photo_path=None):
    """Insert a checklist event. Returns the inserted row."""
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """INSERT INTO checklist_events
               (session_id, section_index, step_index, step_key, step_type,
                step_label, checked, value_input, photo_path)
               VALUES (%s,%s,%s,%s,%s,%s,TRUE,%s,%s)
               ON CONFLICT DO NOTHING
               RETURNING *""",
            (session_id, section_index, step_index, step_key, step_type,
             step_label, value_input, photo_path),
        )
        return cur.fetchone()


def get_session_events(session_id):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """SELECT * FROM checklist_events
               WHERE session_id=%s ORDER BY section_index, step_index""",
            (session_id,),
        )
        return cur.fetchall()


def get_completed_steps(session_id):
    """Return set of step_keys already completed for this session."""
    events = get_session_events(session_id)
    return {e["step_key"] for e in events}


def get_session_events_dict(session_id):
    """Return dict keyed by step_key -> event row, for progress restoration."""
    events = get_session_events(session_id)
    return {e["step_key"]: dict(e) for e in events}


def get_resume_section(session_id, sections):
    """
    Return the index of the first section that still has incomplete steps.
    Returns len(sections) if everything is done.
    """
    from checklist_parser import get_interactive_steps
    completed = get_completed_steps(session_id)
    for section in sections:
        interactive = get_interactive_steps(section)
        if not interactive:
            continue
        if not all(s["key"] in completed for s in interactive):
            return section["index"]
    return len(sections)


# ─── Checklist Versions ───────────────────────────────────────────────────────

def _checksum(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def seed_checklist_from_file(filepath: str, uploaded_by: str = "system"):
    """Seed a .txt file into checklist_versions if not already present."""
    import os
    checklist_name = os.path.splitext(os.path.basename(filepath))[0]
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    cs = _checksum(content)
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # Skip if identical checksum already exists for this name
        cur.execute(
            "SELECT id FROM checklist_versions WHERE checklist_name=%s AND checksum=%s",
            (checklist_name, cs)
        )
        if cur.fetchone():
            return None
        # Use plain cursor for scalar fetch
        pcur = conn.cursor()
        pcur.execute(
            "SELECT COALESCE(MAX(version),0)+1 FROM checklist_versions WHERE checklist_name=%s",
            (checklist_name,)
        )
        version = pcur.fetchone()[0]
        cur.execute(
            """INSERT INTO checklist_versions
               (checklist_name, version, filename, content, checksum, notes, uploaded_by, is_active)
               VALUES (%s,%s,%s,%s,%s,%s,%s,
                 NOT EXISTS (SELECT 1 FROM checklist_versions WHERE checklist_name=%s AND is_active))
               RETURNING *""",
            (checklist_name, version, os.path.basename(filepath),
             content, cs, "Initial import from file", uploaded_by,
             checklist_name)
        )
        row = cur.fetchone()
        # If this is the first version, make it active
        if version == 1:
            cur.execute(
                "UPDATE checklist_versions SET is_active=TRUE WHERE id=%s",
                (row["id"],)
            )
        return row


def get_all_checklist_names():
    """Return distinct checklist names that have at least one active version."""
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT checklist_name,
                   MAX(version) AS latest_version,
                   COUNT(*) AS total_versions,
                   MAX(uploaded_at) AS last_updated,
                   (SELECT filename FROM checklist_versions cv2
                    WHERE cv2.checklist_name=cv.checklist_name AND cv2.is_active
                    LIMIT 1) AS active_filename,
                   (SELECT version FROM checklist_versions cv2
                    WHERE cv2.checklist_name=cv.checklist_name AND cv2.is_active
                    LIMIT 1) AS active_version
            FROM checklist_versions cv
            GROUP BY checklist_name
            ORDER BY checklist_name
        """)
        return cur.fetchall()


def get_checklist_versions(checklist_name: str):
    """All versions for a checklist, newest first."""
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT * FROM checklist_versions
            WHERE checklist_name=%s ORDER BY version DESC
        """, (checklist_name,))
        return cur.fetchall()


def get_checklist_version(version_id: int):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM checklist_versions WHERE id=%s", (version_id,))
        return cur.fetchone()


def get_active_version(checklist_name: str):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM checklist_versions WHERE checklist_name=%s AND is_active ORDER BY version DESC LIMIT 1",
            (checklist_name,)
        )
        return cur.fetchone()


def upload_checklist_version(checklist_name: str, filename: str,
                              content: str, notes: str = "", uploaded_by: str = ""):
    """Insert a new version. Returns (row, error_str)."""
    cs = _checksum(content)
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # Reject identical content
        cur.execute(
            "SELECT version FROM checklist_versions WHERE checklist_name=%s AND checksum=%s",
            (checklist_name, cs)
        )
        dup = cur.fetchone()
        if dup:
            return None, f"Content identical to existing version {dup['version']} — no change."
        # Use plain cursor for scalar fetch
        pcur = conn.cursor()
        pcur.execute(
            "SELECT COALESCE(MAX(version),0)+1 FROM checklist_versions WHERE checklist_name=%s",
            (checklist_name,)
        )
        version = pcur.fetchone()[0]
        cur.execute(
            """INSERT INTO checklist_versions
               (checklist_name, version, filename, content, checksum, notes, uploaded_by, is_active)
               VALUES (%s,%s,%s,%s,%s,%s,%s,FALSE) RETURNING *""",
            (checklist_name, version, filename, content, cs, notes, uploaded_by)
        )
        return cur.fetchone(), None


def set_active_version(version_id: int):
    """Promote a version to active; deactivate all others for same name."""
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT checklist_name FROM checklist_versions WHERE id=%s", (version_id,))
        row = cur.fetchone()
        if not row:
            return False
        name = row["checklist_name"]
        cur.execute("UPDATE checklist_versions SET is_active=FALSE WHERE checklist_name=%s", (name,))
        cur.execute("UPDATE checklist_versions SET is_active=TRUE  WHERE id=%s", (version_id,))
        return True


def get_available_checklists_from_db():
    """Return list of {filename, display, checklist_name} for active versions."""
    names = get_all_checklist_names()
    result = []
    for row in names:
        name = row["checklist_name"]
        display = name.replace("_", " ").title()
        active_fn = row["active_filename"] or (name + ".txt")
        result.append({"filename": active_fn, "display": display,
                        "checklist_name": name})
    return result


# ─── App Settings ─────────────────────────────────────────────────────────────

def get_setting(key: str, default: str = "") -> str:
    """Return a setting value by key, or default if not set."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT value FROM app_settings WHERE key=%s", (key,))
        row = cur.fetchone()
        return row[0] if row else default


def set_setting(key: str, value: str) -> None:
    """Upsert a setting value."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW()
        """, (key, value))


def get_all_settings() -> dict:
    """Return all settings as a dict."""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM app_settings")
        return {row[0]: row[1] for row in cur.fetchall()}
