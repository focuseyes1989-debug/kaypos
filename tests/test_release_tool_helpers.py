import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import gui_update_tool_GitHub_Delete_Releases as release_tool
import generate_update


class ReleaseToolHelpersTests(unittest.TestCase):
    def test_detect_default_version_reads_version_json(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "update_build").mkdir()
            (root / "update_build" / "version.json").write_text(
                '{"version": "2.1.3"}',
                encoding="utf-8",
            )

            self.assertEqual(release_tool.detect_default_version(root), "2.1.3")

    def test_resolve_repo_uses_environment_value(self):
        with mock.patch.dict(os.environ, {"GITHUB_REPO": "demo/repo"}, clear=False):
            self.assertEqual(release_tool.resolve_repo(""), "demo/repo")

    def test_resolve_token_uses_environment_value(self):
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "abc123"}, clear=False):
            self.assertEqual(release_tool.resolve_token(""), "abc123")

    def test_generate_update_finds_launcher_from_dist_launcher(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "dist_launcher").mkdir()
            (root / "dist_launcher" / "ZAY_POS_Launcher.exe").write_bytes(b"launcher")

            with mock.patch.object(generate_update, "PROJECT_ROOT", root):
                found = generate_update.find_versioned_folder("1.5.7")

            self.assertEqual(found, root / "dist_launcher")

    def test_generate_update_falls_back_to_latest_dist_folder(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            dist_dir = root / "dist"
            dist_dir.mkdir()
            latest_dir = dist_dir / "ZAY_POS_v1.5.6"
            latest_dir.mkdir()
            (latest_dir / "ZAY_POS.exe").write_bytes(b"app")

            with mock.patch.object(generate_update, "PROJECT_ROOT", root):
                found = generate_update.find_versioned_folder("1.5.7")

            self.assertEqual(found, latest_dir)


if __name__ == "__main__":
    unittest.main()
