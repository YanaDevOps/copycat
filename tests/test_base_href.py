import builtins
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

from helpers import replace_base_href


class BaseHrefTests(unittest.TestCase):
    def test_does_not_write_when_base_href_already_matches(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir, "index.html")
            index_path.write_text('<base href="/" />', encoding="utf-8")
            original_open = builtins.open

            def open_without_write(path, mode="r", *args, **kwargs):
                if any(flag in mode for flag in ("w", "a", "x", "+")):
                    raise AssertionError("replace_base_href attempted to write")
                return original_open(path, mode, *args, **kwargs)

            with patch("builtins.open", open_without_write):
                replace_base_href(str(index_path), "/")

            self.assertEqual(index_path.read_text(encoding="utf-8"), '<base href="/" />')

    def test_updates_base_href_when_different(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir, "index.html")
            index_path.write_text('<base href="/" />', encoding="utf-8")

            replace_base_href(str(index_path), "/copycat")

            self.assertEqual(
                index_path.read_text(encoding="utf-8"),
                '<base href="/copycat/" />',
            )


if __name__ == "__main__":
    unittest.main()
