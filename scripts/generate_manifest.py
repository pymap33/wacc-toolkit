"""Generate wacc/manifest.json — the single source of truth for which files
web/index.html must fetch into the Pyodide virtual filesystem.

This exists because of two live-site bugs found 2026-09-09: (1) segment.py
was added to the wacc/ package but web/index.html's hardcoded fetch list
wasn't updated, so `import wacc` threw ModuleNotFoundError in the browser
and broke the entire page; (2) a missing .nojekyll file caused GitHub Pages'
Jekyll build to silently 404 any underscore-prefixed file, including
__init__.py. Fix (1) is structural: the fetch list is generated from the
actual directory contents instead of hand-maintained, so a forgotten update
is no longer possible. Run this after adding, removing, or renaming any
wacc/*.py module or data/*.json file, before committing.

Usage: python scripts/generate_manifest.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WACC_DIR = REPO_ROOT / "wacc"
DATA_DIR = REPO_ROOT / "data"
MANIFEST_PATH = WACC_DIR / "manifest.json"


def collect_modules() -> list[str]:
    """All wacc/*.py files, excluding __pycache__ and the manifest itself."""
    return sorted(p.name for p in WACC_DIR.glob("*.py"))


def collect_data_files() -> list[str]:
    """All data/*.json files. Fetched unconditionally into the Pyodide FS —
    harmless if a given calculator doesn't use one; avoids a second
    hand-maintained list that could drift the same way the module list did.
    """
    return sorted(p.name for p in DATA_DIR.glob("*.json"))


def main() -> None:
    manifest = {
        "generated": datetime.now(timezone.utc).date().isoformat(),
        "modules": collect_modules(),
        "data": collect_data_files(),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {MANIFEST_PATH.relative_to(REPO_ROOT)}:")
    print(f"  modules: {manifest['modules']}")
    print(f"  data:    {manifest['data']}")


if __name__ == "__main__":
    main()
