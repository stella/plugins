"""Verify packaging boundaries and reproducibility without external dependencies."""

import os
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from build_zip import MTIME, build_zip


class BuildZipTest(unittest.TestCase):
    def test_reproducible_package_and_hidden_file_filter(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin = root / "plugins/stella"
            included = [".codex-plugin/plugin.json", ".claude-plugin/plugin.json",
                        ".mcp.json", "README.md", "assets/logo.png"]
            excluded = [".DS_Store", ".env", ".git/config",
                        ".codex-plugin/.secret", "assets/.DS_Store",
                        "assets/.cache/data", "assets/.hidden"]
            for name in included + excluded:
                path = plugin / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(name)
            (root / "plugins/other").mkdir()
            (root / "plugins/other/private.txt").write_text("outside")
            first, second = root / "first.zip", root / "second.zip"
            digest = build_zip(plugin, first)
            for name in included:
                path = plugin / name
                os.utime(path, (1700000000, 1700000000))
                path.chmod(0o600)
            self.assertEqual(digest, build_zip(plugin, second))
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with ZipFile(first) as archive:
                self.assertEqual(archive.namelist(), sorted(included))
                self.assertIsNone(archive.testzip())
                for entry in archive.infolist():
                    self.assertEqual(entry.date_time, MTIME)
                    self.assertEqual(entry.external_attr >> 16, 0o100644)

    def test_rejects_missing_manifest_symlink_and_output_inside_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin = root / "plugin"
            plugin.mkdir()
            with self.assertRaisesRegex(ValueError, "missing required"):
                build_zip(plugin, root / "package.zip")
            with self.assertRaisesRegex(ValueError, "outside"):
                build_zip(plugin, plugin / "package.zip")
            (plugin / "link").symlink_to(root)
            with self.assertRaisesRegex(ValueError, "symlink"):
                build_zip(plugin, root / "package.zip")


if __name__ == "__main__":
    unittest.main()
