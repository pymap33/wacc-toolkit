"""Guards against the 2026-09-09 regression class: a new wacc/*.py module or
data/*.json file added without regenerating wacc/manifest.json, which is
what the browser's Pyodide loader (web/index.html) actually fetches. This
test can't see the browser itself, but it can catch the drift that caused
the failure — run it (or scripts/generate_manifest.py --check, if added
later) before every commit that touches wacc/ or data/.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.generate_manifest import collect_data_files, collect_modules, MANIFEST_PATH


def test_manifest_exists():
    assert MANIFEST_PATH.exists(), (
        "wacc/manifest.json is missing — run scripts/generate_manifest.py"
    )


def test_manifest_modules_match_directory():
    manifest = json.loads(MANIFEST_PATH.read_text())
    actual = collect_modules()
    assert manifest["modules"] == actual, (
        f"wacc/manifest.json's module list is stale (manifest={manifest['modules']!r}, "
        f"actual={actual!r}). Run scripts/generate_manifest.py and commit the result — "
        "this is the exact drift that broke the live browser tool on 2026-09-09."
    )


def test_manifest_data_matches_directory():
    manifest = json.loads(MANIFEST_PATH.read_text())
    actual = collect_data_files()
    assert manifest["data"] == actual, (
        f"wacc/manifest.json's data list is stale (manifest={manifest['data']!r}, "
        f"actual={actual!r}). Run scripts/generate_manifest.py and commit the result."
    )


if __name__ == "__main__":
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print(f"OK: {t.__name__}")
    print(f"\n{len(tests)} tests passed.")
