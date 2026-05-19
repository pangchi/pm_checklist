"""
exif_checker.py — Validate photo EXIF timestamps before accepting uploads.

Strategy:
  - Try to read DateTimeOriginal, then DateTimeDigitized, then DateTime from EXIF.
  - If a timestamp is found and it is older than max_age_minutes, reject the photo.
  - If no EXIF timestamp exists (e.g. screenshots, PDFs, some phone cameras with
    EXIF stripped), allow the photo through — we cannot penalise legitimate phones
    that strip metadata, and PDFs have no EXIF concept.
  - All comparisons done in UTC. EXIF DateTime has no timezone; we treat it as the
    server's local wall-clock time converted to UTC for comparison.
"""

import io
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# EXIF tag IDs we try in priority order
_EXIF_TAGS = {
    36867: "DateTimeOriginal",
    36868: "DateTimeDigitized",
    306:   "DateTime",
}
_EXIF_FMT = "%Y:%m:%d %H:%M:%S"


def _parse_exif_dt(raw: str) -> Optional[datetime]:
    """Parse an EXIF datetime string into a naive datetime, or None on failure."""
    try:
        return datetime.strptime(raw.strip(), _EXIF_FMT)
    except (ValueError, AttributeError):
        return None


def get_photo_exif_datetime(file_bytes: bytes) -> Optional[datetime]:
    """
    Extract the best available EXIF capture datetime from image bytes.
    Returns a naive datetime (local wall-clock, no tz info), or None.
    """
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
    except ImportError:
        logger.warning("[EXIF] Pillow not installed — skipping EXIF check.")
        return None

    try:
        img = Image.open(io.BytesIO(file_bytes))
        exif_data = img._getexif()  # returns dict or None
        if not exif_data:
            return None

        for tag_id, tag_name in _EXIF_TAGS.items():
            raw = exif_data.get(tag_id)
            if raw:
                dt = _parse_exif_dt(str(raw))
                if dt:
                    logger.debug(f"[EXIF] {tag_name} = {dt}")
                    return dt

        return None

    except Exception as e:
        logger.debug(f"[EXIF] Could not read EXIF data: {e}")
        return None


def check_photo_age(
    file_bytes: bytes,
    max_age_minutes: int = 60,
    server_utc_offset_minutes: int = 0,
) -> dict:
    """
    Validate that a photo's EXIF timestamp is within max_age_minutes of now.

    Returns a dict:
    {
        "ok":             True | False,
        "has_exif":       True | False,      # whether any EXIF datetime was found
        "exif_dt":        datetime | None,   # naive local datetime from EXIF
        "exif_utc":       datetime | None,   # UTC-aware datetime
        "age_minutes":    float | None,
        "error":          str | None,        # human-readable rejection reason
    }
    """
    now_utc = datetime.now(timezone.utc)

    exif_naive = get_photo_exif_datetime(file_bytes)

    if exif_naive is None:
        # No EXIF — allow through (cannot verify, but also cannot reject)
        return {
            "ok":          True,
            "has_exif":    False,
            "exif_dt":     None,
            "exif_utc":    None,
            "age_minutes": None,
            "error":       None,
        }

    # Treat EXIF datetime as local wall-clock and convert to UTC
    exif_utc = exif_naive.replace(tzinfo=timezone.utc) - timedelta(minutes=server_utc_offset_minutes)

    age = now_utc - exif_utc
    age_minutes = age.total_seconds() / 60

    if age_minutes < 0:
        # EXIF timestamp is in the future — possible clock skew; allow with warning
        logger.warning(
            f"[EXIF] Photo timestamp is {abs(age_minutes):.1f} min in the future. "
            "Possible clock skew — allowing."
        )
        return {
            "ok":          True,
            "has_exif":    True,
            "exif_dt":     exif_naive,
            "exif_utc":    exif_utc,
            "age_minutes": age_minutes,
            "error":       None,
        }

    if age_minutes > max_age_minutes:
        taken_str = exif_naive.strftime("%Y-%m-%d %H:%M:%S")
        error = (
            f"Photo was taken {age_minutes:.0f} minutes ago "
            f"({taken_str}) — only photos taken within the last "
            f"{max_age_minutes} minutes are accepted. "
            f"Please take a new photo now."
        )
        logger.warning(f"[EXIF] Rejected photo: {error}")
        return {
            "ok":          False,
            "has_exif":    True,
            "exif_dt":     exif_naive,
            "exif_utc":    exif_utc,
            "age_minutes": age_minutes,
            "error":       error,
        }

    return {
        "ok":          True,
        "has_exif":    True,
        "exif_dt":     exif_naive,
        "exif_utc":    exif_utc,
        "age_minutes": age_minutes,
        "error":       None,
    }
