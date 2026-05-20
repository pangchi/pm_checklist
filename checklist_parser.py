"""
checklist_parser.py — Parses the editable .txt checklist template into
a structured list of sections and steps.
"""


VALID_STEP_TYPES = {"STEP", "STEP_VALUE", "PHOTO", "NOTE"}

import re as _re
_MIN_PATTERN = _re.compile(r'\[min=(\d+)\]', _re.IGNORECASE)


def _extract_min_seconds(label: str) -> tuple[str, int]:
    """
    Strip [min=N] modifier from a step label and return (clean_label, seconds).
    N is in seconds. Returns (label, 0) if no modifier present.
    Example: "Inspect belt tension [min=120]" -> ("Inspect belt tension", 120)
    """
    m = _MIN_PATTERN.search(label)
    if not m:
        return label.strip(), 0
    clean = _MIN_PATTERN.sub("", label).strip()
    return clean, int(m.group(1))


def parse_template(filepath: str) -> list[dict]:
    """
    Parse the checklist template file.

    Returns a list of sections:
    [
      {
        "title": "Pre-Maintenance Safety Checks",
        "index": 0,
        "steps": [
          {
            "type": "NOTE" | "STEP" | "STEP_VALUE" | "PHOTO",
            "label": "Check all cable routing...",
            "index": 0,
            "key": "0_0",          # "{section_index}_{step_index}"
            "requires_value": bool,
            "requires_photo": bool,
          },
          ...
        ]
      },
      ...
    ]
    """
    sections = []
    current_section = None
    step_idx = 0

    with open(filepath, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()

            # Skip blank lines and comments
            if not line or line.startswith("#"):
                continue

            if line.upper().startswith("SECTION:"):
                title = line[len("SECTION:"):].strip()
                current_section = {
                    "title": title,
                    "index": len(sections),
                    "steps": [],
                }
                sections.append(current_section)
                step_idx = 0
                continue

            # Parse step types
            parsed = False
            for stype in VALID_STEP_TYPES:
                prefix = f"{stype}:"
                if line.upper().startswith(prefix):
                    label = line[len(prefix):].strip()
                    if current_section is None:
                        # Auto-create a default section
                        current_section = {
                            "title": "General",
                            "index": 0,
                            "steps": [],
                        }
                        sections.append(current_section)
                        step_idx = 0

                    sec_idx = current_section["index"]
                    clean_label, min_secs = _extract_min_seconds(label)
                    step = {
                        "type": stype,
                        "label": clean_label,
                        "index": step_idx,
                        "key": f"{sec_idx}_{step_idx}",
                        "requires_value": stype == "STEP_VALUE",
                        "requires_photo": stype == "PHOTO",
                        "is_interactive": stype != "NOTE",
                        "min_seconds": min_secs,
                    }
                    current_section["steps"].append(step)
                    if stype != "NOTE":
                        step_idx += 1
                    parsed = True
                    break

            if not parsed and current_section is not None:
                # Treat bare lines as STEP
                step = {
                    "type": "STEP",
                    "label": line,
                    "index": step_idx,
                    "key": f"{current_section['index']}_{step_idx}",
                    "requires_value": False,
                    "requires_photo": False,
                    "is_interactive": True,
                    "min_seconds": 0,
                }
                current_section["steps"].append(step)
                step_idx += 1

    return sections


def get_interactive_steps(section: dict) -> list[dict]:
    """Return only steps that require user action (exclude NOTEs)."""
    return [s for s in section["steps"] if s["is_interactive"]]


def parse_template_from_string(text: str) -> list[dict]:
    """Parse checklist content from a string (e.g. from DB) instead of a file."""
    sections = []
    current_section = None
    step_idx = 0

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.upper().startswith("SECTION:"):
            title = line[len("SECTION:"):].strip()
            current_section = {
                "title": title,
                "index": len(sections),
                "steps": [],
            }
            sections.append(current_section)
            step_idx = 0
            continue

        parsed = False
        for stype in VALID_STEP_TYPES:
            prefix = f"{stype}:"
            if line.upper().startswith(prefix):
                label = line[len(prefix):].strip()
                if current_section is None:
                    current_section = {"title": "General", "index": 0, "steps": []}
                    sections.append(current_section)
                    step_idx = 0
                sec_idx = current_section["index"]
                clean_label, min_secs = _extract_min_seconds(label)
                step = {
                    "type": stype, "label": clean_label, "index": step_idx,
                    "key": f"{sec_idx}_{step_idx}",
                    "requires_value": stype == "STEP_VALUE",
                    "requires_photo": stype == "PHOTO",
                    "is_interactive": stype != "NOTE",
                    "min_seconds": min_secs,
                }
                current_section["steps"].append(step)
                if stype != "NOTE":
                    step_idx += 1
                parsed = True
                break

        if not parsed and current_section is not None:
            step = {
                "type": "STEP", "label": line,
                "index": step_idx,
                "key": f"{current_section['index']}_{step_idx}",
                "requires_value": False, "requires_photo": False,
                "is_interactive": True,
                "min_seconds": 0,
            }
            current_section["steps"].append(step)
            step_idx += 1

    return sections


def validate_template(text: str) -> list[str]:
    """
    Validate checklist content. Returns a list of error/warning strings.
    Empty list = valid.
    """
    errors = []
    has_section = False
    has_interactive = False
    seen_labels = []

    for i, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.upper().startswith("SECTION:"):
            title = line[len("SECTION:"):].strip()
            if not title:
                errors.append(f"Line {i}: SECTION: has no title.")
            has_section = True
            continue

        matched = False
        for stype in VALID_STEP_TYPES:
            if line.upper().startswith(f"{stype}:"):
                raw_label = line[len(stype)+1:].strip()
                clean_label, min_secs = _extract_min_seconds(raw_label)
                if not clean_label:
                    errors.append(f"Line {i}: {stype}: has no description.")
                if clean_label in seen_labels:
                    errors.append(f"Line {i}: Duplicate step label: '{clean_label[:60]}'")
                seen_labels.append(clean_label)
                if stype != "NOTE":
                    has_interactive = True
                matched = True
                break

        if not matched and line:
            errors.append(f"Line {i}: Unrecognised line (not a SECTION/STEP/NOTE/etc.): '{line[:60]}'")

    if not has_section:
        errors.append("No SECTION: found. At least one section is required.")
    if not has_interactive:
        errors.append("No interactive steps (STEP/STEP_VALUE/PHOTO) found.")

    return errors
