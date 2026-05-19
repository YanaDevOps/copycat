import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("COPYCAT_LOG_TO_FILE", "false")

SERVER_PATH = Path(__file__).resolve().parents[1] / "server"
if str(SERVER_PATH) not in sys.path:
    sys.path.insert(0, str(SERVER_PATH))

pydantic_stub = types.ModuleType("pydantic")
pydantic_stub.BaseModel = object
sys.modules.setdefault("pydantic", pydantic_stub)

from helpers import resolve_root_app_dir


class LegacyMetadataMigrationTests(unittest.TestCase):
    def test_does_not_scan_arbitrary_hidden_directories(self):
        with tempfile.TemporaryDirectory() as data_root:
            random_hidden = Path(data_root, ".unexpected")
            random_hidden.mkdir()
            Path(random_hidden, "metadata.json").write_text("{}", encoding="utf-8")

            app_dir = resolve_root_app_dir(data_root)

            self.assertFalse(os.path.exists(os.path.join(app_dir, "metadata.json")))

    def test_copies_explicit_flatnotes_metadata_without_removing_source(self):
        with tempfile.TemporaryDirectory() as data_root:
            flatnotes = Path(data_root, ".flatnotes")
            flatnotes.mkdir()
            source = Path(flatnotes, "metadata.json")
            source.write_text('{"version": 1}', encoding="utf-8")

            app_dir = resolve_root_app_dir(data_root)

            self.assertTrue(source.exists())
            self.assertEqual(
                Path(app_dir, "metadata.json").read_text(encoding="utf-8"),
                '{"version": 1}',
            )

    def test_supports_configured_legacy_metadata_dir(self):
        with tempfile.TemporaryDirectory() as data_root:
            legacy = Path(data_root, ".old-copycat")
            legacy.mkdir()
            Path(legacy, "metadata.json").write_text("{}", encoding="utf-8")

            with patch.dict(
                os.environ,
                {"COPYCAT_LEGACY_METADATA_DIRS": ".old-copycat"},
            ):
                app_dir = resolve_root_app_dir(data_root)

            self.assertTrue(os.path.exists(os.path.join(app_dir, "metadata.json")))


if __name__ == "__main__":
    unittest.main()
