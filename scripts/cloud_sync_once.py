"""Initialize/test/run one cloud sync pass.

Usage:
    python scripts/cloud_sync_once.py --test
    python scripts/cloud_sync_once.py --init
    python scripts/cloud_sync_once.py --sync
    python scripts/cloud_sync_once.py --pull
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from services.cloud_sync_service import CloudSyncService  # noqa: E402
from utils.env_loader import load_project_env  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="ZAY POS cloud PostgreSQL sync utility")
    parser.add_argument("--test", action="store_true", help="Test cloud PostgreSQL connection only")
    parser.add_argument("--init", action="store_true", help="Create/verify cloud PostgreSQL schema")
    parser.add_argument("--sync", action="store_true", help="Run one local-to-cloud sync pass")
    parser.add_argument("--pull", action="store_true", help="Pull cloud PostgreSQL data into the local database")
    parser.add_argument("--table", action="append", help="Sync only this table; can be passed more than once")
    args = parser.parse_args()

    load_project_env()
    service = CloudSyncService(tables=args.table) if args.table else CloudSyncService()

    if args.test:
        result = service.test_connection()
        print(result.message)
        return 0 if result.ok else 1

    if args.init:
        result = service.initialize_cloud()
        print(result.message)
        return 0 if result.ok else 1

    if args.pull:
        result = service.pull_once()
        print(result.message)
        return 0 if result.ok else 1

    if args.sync or not any((args.test, args.init, args.pull)):
        result = service.sync_once()
        print(result.message)
        return 0 if result.ok else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
