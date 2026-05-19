import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("COPYCAT_LOG_TO_FILE", "false")

SERVER_PATH = Path(__file__).resolve().parents[1] / "server"
if str(SERVER_PATH) not in sys.path:
    sys.path.insert(0, str(SERVER_PATH))

from data_guard import DataGuardError, guard_data_root, summarize_data_root


class DataGuardTests(unittest.TestCase):
    def test_allows_empty_first_install_and_writes_marker(self):
        with tempfile.TemporaryDirectory() as data_root:
            os.mkdir(os.path.join(data_root, "lost+found"))

            summary = guard_data_root(data_root)

            self.assertEqual(summary.durable_count, 0)
            self.assertTrue(
                os.path.isfile(
                    os.path.join(data_root, ".copycat", "install.json")
                )
            )

    def test_rejects_cache_only_volume_without_marker(self):
        with tempfile.TemporaryDirectory() as data_root:
            index_path = os.path.join(data_root, ".copycat", "index")
            os.makedirs(index_path)
            Path(index_path, "_5_2.toc").write_text("cache", encoding="utf-8")

            with self.assertRaises(DataGuardError):
                guard_data_root(data_root)

    def test_rejects_marker_with_previous_data_when_data_disappears(self):
        with tempfile.TemporaryDirectory() as data_root:
            marker_path = os.path.join(data_root, ".copycat", "install.json")
            os.makedirs(os.path.dirname(marker_path))
            with open(marker_path, "w", encoding="utf-8") as f:
                json.dump({"lastDurableCount": 3}, f)

            with self.assertRaises(DataGuardError):
                guard_data_root(data_root)

    def test_warn_mode_does_not_reject_cache_only_volume(self):
        with tempfile.TemporaryDirectory() as data_root:
            index_path = os.path.join(data_root, ".copycat", "index")
            os.makedirs(index_path)
            Path(index_path, "_5_2.toc").write_text("cache", encoding="utf-8")

            with patch.dict(os.environ, {"COPYCAT_DATA_GUARD_MODE": "warn"}):
                summary = guard_data_root(data_root)

            self.assertEqual(summary.index_file_count, 1)

    def test_durable_data_updates_marker_count(self):
        with tempfile.TemporaryDirectory() as data_root:
            Path(data_root, "note.md").write_text("hello", encoding="utf-8")

            guard_data_root(data_root)
            summary = summarize_data_root(data_root)

            self.assertEqual(summary.previous_durable_count, 1)


if __name__ == "__main__":
    unittest.main()
