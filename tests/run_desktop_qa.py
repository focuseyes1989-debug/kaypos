"""Run desktop checks against disposable SQLite storage, never the shop DB."""

import os
import argparse
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("offscreen", "windows"), default="offscreen")
    parser.add_argument("--shell", action="store_true")
    parser.add_argument("--workflows", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    os.chdir(root)
    os.environ["QT_QPA_PLATFORM"] = args.platform
    os.environ["ZAY_POS_DB_BACKEND"] = "sqlite"
    os.environ["KAY_DESKTOP_QA_ISOLATED"] = "1"
    original_connect = sqlite3.connect
    with tempfile.TemporaryDirectory(prefix="kay-desktop-qa-", ignore_cleanup_errors=True) as directory:
        database = str(Path(directory) / "qa.db")
        os.environ["KAY_DESKTOP_QA_DIR"] = directory

        def isolated_connect(path, *args, **kwargs):
            # All application SQLite entry points share the disposable fixture.
            target = ":memory:" if str(path) == ":memory:" else database
            if target != ":memory:" and Path(path).resolve().is_relative_to(Path(directory).resolve()):
                target = path
            return original_connect(target, *args, **kwargs)

        sqlite3.connect = isolated_connect
        try:
            from loguru import logger
            logger.remove()
            logger.add(sys.stderr, level="ERROR")
            from models.database import create_tables, close_all_connections
            create_tables()
            modules = [
                "tests.test_desktop_remaining_layout",
                "tests.test_desktop_reports_layout",
                "tests.test_desktop_management_layout",
                "tests.test_desktop_payment_layout",
                "tests.test_desktop_refresh_controls",
                "tests.test_main_py_phase10_desktop_layout",
                "tests.test_desktop_sale_details",
                "tests.test_desktop_settings_integration",
            ]
            if args.shell:
                modules.append("tests.test_desktop_live_shell")
            if args.workflows:
                modules.extend([
                    "tests.test_desktop_workflows",
                    "tests.test_desktop_backup_workflow",
                    "tests.test_stock_movement_variant_reversal",
                    "tests.test_variant_batches",
                ])
            suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
            sys.excepthook = sys.__excepthook__
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            close_all_connections()
            return 0 if result.wasSuccessful() else 1
        finally:
            sqlite3.connect = original_connect


if __name__ == "__main__":
    raise SystemExit(main())
