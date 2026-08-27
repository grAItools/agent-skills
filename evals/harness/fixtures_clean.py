"""Restore scenario fixtures to their authored state after live runs."""

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "scenarios"

PRISTINE = {
    "efficacy-designing-before-coding/fixture": {
        "README.md", "REQUIREMENTS.md",
        "metrics_cli/__init__.py", "metrics_cli/cli.py", "metrics_cli/store.py",
        "tests/__init__.py", "tests/test_store.py",
    },
    "efficacy-verifying-changes/fixture": {
        "BUG_REPORT.md", "check_suite.sh",
        "inventory/__init__.py", "inventory/models.py",
        "tests/__init__.py", "tests/test_models.py",
    },
    "triggering-designing-before-coding/fixture": {
        "README.md", "REQUIREMENTS.md",
        "exporters/csv_exporter.py", "exporters/json_exporter.py",
        "exporters/xml_exporter.py",
        "src/api.py", "src/models.py",
    },
    "triggering-verifying-changes/fixture": {
        "README.md", "SPEC.md",
        "src/reporting.py", "tests/__init__.py", "tests/test_reporting.py",
    },
}


def clean_fixtures() -> list[str]:
    removed: list[str] = []
    for rel_dir, allowed in PRISTINE.items():
        base = ROOT / rel_dir
        if not base.is_dir():
            continue
        allowed_paths = {base / p for p in allowed}
        for path in sorted(base.rglob("*")):
            if "__pycache__" in path.parts:
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path)
                    removed.append(str(path) + "/")
                elif path.is_file():
                    path.unlink()
                    removed.append(str(path))
                continue
            if (path.is_file() or path.is_symlink()) and path not in allowed_paths:
                path.unlink()
                removed.append(str(path))
        for sub in sorted(d for d in base.rglob("__pycache__") if d.is_dir()):
            shutil.rmtree(sub)
            removed.append(str(sub) + "/")
    return removed


if __name__ == "__main__":
    removed = clean_fixtures()
    print(f"removed {len(removed)} stray file(s)")
    for entry in removed:
        print("  -", entry)
