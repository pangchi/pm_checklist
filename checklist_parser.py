"""
checklist_parser.py — Parses the editable .txt checklist template into
a structured list of sections and steps.
"""


VALID_STEP_TYPES = {"STEP", "STEP_VALUE", "PHOTO", "NOTE"}


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
                    step = {
                        "type": stype,
                        "label": label,
                        "index": step_idx,
                        "key": f"{sec_idx}_{step_idx}",
                        "requires_value": stype == "STEP_VALUE",
                        "requires_photo": stype == "PHOTO",
                        "is_interactive": stype != "NOTE",
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
                }
                current_section["steps"].append(step)
                step_idx += 1

    return sections


def get_interactive_steps(section: dict) -> list[dict]:
    """Return only steps that require user action (exclude NOTEs)."""
    return [s for s in section["steps"] if s["is_interactive"]]
