"""Static checks for SQLite-specific SQL that blocks PostgreSQL migration."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCAN_DIRS = ("models", "utils", "ui", "server", "services")
PATTERNS = {
    "sqlite_import": "import sqlite3",
    "pragma": "PRAGMA ",
    "autoincrement": "AUTOINCREMENT",
    "insert_or_replace": "INSERT OR REPLACE",
    "begin_immediate": "BEGIN IMMEDIATE",
    "sqlite_date_func": "DATE(",
    "sqlite_strftime": "strftime(",
    "last_insert_rowid": "last_insert_rowid",
}


def get_postgres_readiness_report(scan_dirs=DEFAULT_SCAN_DIRS):
    findings = []
    for scan_dir in scan_dirs:
        root = PROJECT_ROOT / scan_dir
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            for line_no, line in enumerate(lines, start=1):
                upper_line = line.upper()
                for key, pattern in PATTERNS.items():
                    haystack = upper_line if pattern.isupper() else line
                    if pattern in haystack:
                        findings.append({
                            "kind": key,
                            "file": str(path.relative_to(PROJECT_ROOT)),
                            "line": line_no,
                            "text": line.strip(),
                        })
    summary = {}
    for finding in findings:
        summary[finding["kind"]] = summary.get(finding["kind"], 0) + 1
    return {
        "ok": not findings,
        "summary": summary,
        "findings": findings,
    }
