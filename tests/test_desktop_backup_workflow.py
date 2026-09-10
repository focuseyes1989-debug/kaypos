import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from ui.settings.backup_reset_setting import _backup_database_file, _restore_database_file


@unittest.skipUnless(os.environ.get("KAY_DESKTOP_QA_ISOLATED") == "1", "Use the isolated QA runner")
class DesktopBackupTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(dir=os.environ["KAY_DESKTOP_QA_DIR"])
        self.addCleanup(self.folder.cleanup)
        self.source = str(Path(self.folder.name) / "source.db")
        self.backup = str(Path(self.folder.name) / "backup.db")
        self.target = str(Path(self.folder.name) / "restored.db")

    def test_wal_backup_restores_committed_rows(self):
        connection = sqlite3.connect(self.source)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("CREATE TABLE products (id INTEGER, name TEXT)")
            connection.execute("INSERT INTO products VALUES (1,'QA product')")
            connection.commit()
            _backup_database_file(self.source, self.backup)
        finally:
            connection.close()
        with patch("ui.settings.backup_reset_setting._force_close_all_connections"):
            self.assertTrue(_restore_database_file(self.backup, self.target))
        restored = sqlite3.connect(self.target)
        try:
            self.assertEqual(restored.execute("SELECT * FROM products").fetchall(), [(1, "QA product")])
            self.assertEqual(restored.execute("PRAGMA integrity_check").fetchall(), [("ok",)])
        finally:
            restored.close()

    def test_corrupt_backup_cannot_replace_existing_target(self):
        Path(self.backup).write_bytes(b"not a SQLite backup")
        connection = sqlite3.connect(self.target)
        connection.execute("CREATE TABLE keep_me (id INTEGER)")
        connection.commit()
        connection.close()
        before = Path(self.target).read_bytes()
        with patch("ui.settings.backup_reset_setting._force_close_all_connections") as close:
            with self.assertRaises(sqlite3.DatabaseError):
                _restore_database_file(self.backup, self.target)
            close.assert_not_called()
        self.assertEqual(Path(self.target).read_bytes(), before)
