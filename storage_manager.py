"""
storage_manager.py — Automatic photo cleanup when disk usage exceeds threshold.

Strategy:
  1. Check disk usage of the configured partition.
  2. If usage >= threshold%, collect all photo paths from checklist_events
     ordered by timestamp ASC (oldest first).
  3. Delete files from disk one by one, nulling photo_path in the DB,
     until usage drops below (threshold - 5)% or no photos remain.
  4. Return a summary dict for logging / Telegram alert.
"""

import os
import shutil
import logging
from typing import Optional

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


# ─── Disk helpers ─────────────────────────────────────────────────────────────

def get_app_partition(app_path: str = None) -> str:
    """
    Return the mount point of the partition where app_path resides.
    Falls back to "/" if detection fails.

    Works by walking up the directory tree until we find a path
    whose device ID differs from its parent — that boundary is the mount point.
    """
    if app_path is None:
        app_path = os.path.abspath(__file__)

    path = os.path.abspath(app_path)
    if os.path.isfile(path):
        path = os.path.dirname(path)

    try:
        prev_dev = os.stat(path).st_dev
        candidate = path
        while True:
            parent = os.path.dirname(candidate)
            if parent == candidate:
                # Reached filesystem root
                return candidate
            parent_dev = os.stat(parent).st_dev
            if parent_dev != prev_dev:
                # candidate is the mount point
                return candidate
            candidate = parent
            prev_dev = parent_dev
    except Exception as e:
        logger.warning(f"[Storage] Could not determine mount point for {path}: {e}. Using '/'.")
        return "/"


def get_disk_usage_pct(partition: str = "/") -> float:
    """Return current disk usage as a percentage (0–100) for the given partition."""
    usage = shutil.disk_usage(partition)
    return (usage.used / usage.total) * 100


def get_disk_usage_info(partition: str = "/") -> dict:
    """Return a dict with total, used, free (bytes) and pct for the partition."""
    usage = shutil.disk_usage(partition)
    pct = (usage.used / usage.total) * 100
    return {
        "total_gb": round(usage.total / 1e9, 2),
        "used_gb":  round(usage.used  / 1e9, 2),
        "free_gb":  round(usage.free  / 1e9, 2),
        "pct":      round(pct, 1),
    }


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


# ─── DB helpers (standalone — no dependency on db.py to avoid circular import) ─

def _get_photos_oldest_first(conn) -> list[dict]:
    """Return all checklist_events rows that have a non-null photo_path, oldest first."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT ce.id, ce.session_id, ce.step_key, ce.photo_path, ce.timestamp,
               ps.wo_id, wo.wo_number, wo.equipment
        FROM checklist_events ce
        JOIN pm_sessions ps ON ps.id = ce.session_id
        JOIN work_orders wo ON wo.id = ps.wo_id
        WHERE ce.photo_path IS NOT NULL
        ORDER BY ce.timestamp ASC
    """)
    rows = cur.fetchall()
    cur.close()
    return [dict(r) for r in rows]


def _null_photo_path(conn, event_id: int) -> None:
    """Set photo_path = NULL for a checklist_event row."""
    cur = conn.cursor()
    cur.execute(
        "UPDATE checklist_events SET photo_path = NULL WHERE id = %s",
        (event_id,)
    )
    cur.close()


# ─── Main purge function ───────────────────────────────────────────────────────

def purge_if_needed(
    upload_folder: str,
    dsn: dict,
    threshold_pct: float = 80.0,
    partition: str = "/",
) -> Optional[dict]:
    """
    Check disk usage and delete oldest photos if over threshold.

    Returns None if no purge was needed, otherwise a summary dict:
    {
        "triggered_at_pct": 85.3,
        "final_pct": 74.1,
        "deleted_count": 7,
        "freed_bytes": 23456789,
        "deleted": [ {"wo_number": ..., "equipment": ..., "photo_path": ..., "timestamp": ...}, ... ],
        "remaining_photos": 42,
        "error": None,
    }
    """
    current_pct = get_disk_usage_pct(partition)

    if current_pct < threshold_pct:
        return None   # All good — nothing to do

    logger.warning(
        f"[Storage] Disk usage {current_pct:.1f}% >= threshold {threshold_pct}%. "
        f"Starting photo purge."
    )

    target_pct = max(threshold_pct - 5.0, 0.0)   # Purge down to threshold−5%
    deleted = []
    freed_bytes = 0
    error = None

    try:
        conn = psycopg2.connect(**dsn)
        conn.autocommit = False

        photos = _get_photos_oldest_first(conn)

        for photo in photos:
            if get_disk_usage_pct(partition) < target_pct:
                break   # Enough freed

            rel_path = photo["photo_path"]
            abs_path = os.path.join(upload_folder, rel_path)

            file_size = 0
            if os.path.isfile(abs_path):
                try:
                    file_size = os.path.getsize(abs_path)
                    os.remove(abs_path)
                    logger.info(f"[Storage] Deleted {abs_path} ({_fmt_bytes(file_size)})")
                except OSError as e:
                    logger.warning(f"[Storage] Could not delete {abs_path}: {e}")
                    continue
            else:
                logger.warning(f"[Storage] File not found on disk (will null DB): {abs_path}")

            _null_photo_path(conn, photo["id"])
            freed_bytes += file_size
            deleted.append({
                "event_id":  photo["id"],
                "wo_number": photo["wo_number"],
                "equipment": photo["equipment"],
                "photo_path": rel_path,
                "timestamp": str(photo["timestamp"]),
                "freed_bytes": file_size,
            })

        conn.commit()
        conn.close()

        # Count remaining photos
        conn2 = psycopg2.connect(**dsn)
        cur2 = conn2.cursor()
        cur2.execute("SELECT COUNT(*) FROM checklist_events WHERE photo_path IS NOT NULL")
        remaining = cur2.fetchone()[0]
        cur2.close()
        conn2.close()

    except Exception as e:
        error = str(e)
        logger.error(f"[Storage] Purge error: {e}")
        remaining = -1

    final_pct = get_disk_usage_pct(partition)

    summary = {
        "triggered_at_pct": round(current_pct, 1),
        "final_pct":        round(final_pct, 1),
        "deleted_count":    len(deleted),
        "freed_bytes":      freed_bytes,
        "freed_human":      _fmt_bytes(freed_bytes),
        "deleted":          deleted,
        "remaining_photos": remaining,
        "error":            error,
    }

    logger.info(
        f"[Storage] Purge complete. Deleted {len(deleted)} photos, "
        f"freed {_fmt_bytes(freed_bytes)}. "
        f"Disk now at {final_pct:.1f}%."
    )

    return summary
