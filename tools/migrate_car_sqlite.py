"""Import the legacy Car Management SQLite database into KAY POS PostgreSQL."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.env_loader import load_project_env

load_project_env()

from server.car_management_service import CAR_COLUMNS, CarRepository


def migrate(source_path: Path, dry_run=False) -> tuple[int, int]:
    if not source_path.is_file():
        raise FileNotFoundError(f"Legacy database not found: {source_path}")

    source = sqlite3.connect(source_path)
    try:
        cursor = source.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cars'")
        if cursor.fetchone() is None:
            raise RuntimeError("The selected SQLite database does not contain a cars table.")
        cursor.execute(f"SELECT {', '.join(CAR_COLUMNS)} FROM cars ORDER BY id")
        rows = cursor.fetchall()
    finally:
        source.close()

    if dry_run:
        return len(rows), 0

    repository = CarRepository()
    repository.ensure_schema()
    imported = 0
    for row in rows:
        data = dict(zip(CAR_COLUMNS, row))
        if repository.insert(data, explicit_id=data["id"]) is not None:
            imported += 1
    repository.sync_id_sequence()
    return len(rows), imported


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate legacy car_data.db into the configured KAY POS database")
    parser.add_argument("source", type=Path, help="Path to the legacy car_data.db")
    parser.add_argument("--dry-run", action="store_true", help="Validate and count rows without writing")
    args = parser.parse_args()
    total, imported = migrate(args.source.resolve(), args.dry_run)
    if args.dry_run:
        print(f"Validated {total} legacy car record(s); no data was written.")
    else:
        print(f"Migration complete: {imported} imported, {total - imported} already present/skipped.")


if __name__ == "__main__":
    main()
