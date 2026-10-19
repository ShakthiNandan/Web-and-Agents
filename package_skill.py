#!/usr/bin/env python3
"""Package agent-hub skill into a cloud-installable .skill file.

A .skill file is a ZIP archive conforming to Claude skill packaging conventions,
containing:
    agent-hub/SKILL.md

Usage:
    python package_skill.py
"""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILL_MD = ROOT / "SKILL.md"
OUTPUT_SKILL = ROOT / "agent-hub.skill"


def build_skill():
    if not SKILL_MD.exists():
        raise FileNotFoundError(f"SKILL.md not found at {SKILL_MD}")

    # Ensure deterministic packaging
    with zipfile.ZipFile(OUTPUT_SKILL, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(SKILL_MD, arcname="agent-hub/SKILL.md")

    print(f"Successfully packaged {OUTPUT_SKILL} ({OUTPUT_SKILL.stat().st_size} bytes)")
    print("Contains:")
    with zipfile.ZipFile(OUTPUT_SKILL, "r") as zf:
        for name in zf.namelist():
            print(f"  - {name}")


if __name__ == "__main__":
    build_skill()
