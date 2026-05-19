import os
import tempfile
import unittest

from server.path_safety import (
    UnsafeIndexPathError,
    assert_safe_index_directory,
)


class IndexPathSafetyTests(unittest.TestCase):
    def test_allows_legacy_index_directory(self):
        with tempfile.TemporaryDirectory() as data_root:
            index_path = os.path.join(data_root, ".copycat", "index")

            resolved_path = assert_safe_index_directory(
                index_path=index_path,
                data_root=data_root,
                notes_path=data_root,
            )

            self.assertEqual(resolved_path, os.path.realpath(index_path))

    def test_allows_group_index_directory(self):
        with tempfile.TemporaryDirectory() as data_root:
            group_root = os.path.join(data_root, "groups", "team")
            notes_path = os.path.join(group_root, "notes")
            index_path = os.path.join(group_root, ".copycat", "index")

            resolved_path = assert_safe_index_directory(
                index_path=index_path,
                data_root=data_root,
                notes_path=notes_path,
            )

            self.assertEqual(resolved_path, os.path.realpath(index_path))

    def test_rejects_data_root(self):
        with tempfile.TemporaryDirectory() as data_root:
            with self.assertRaises(UnsafeIndexPathError):
                assert_safe_index_directory(
                    index_path=data_root,
                    data_root=data_root,
                    notes_path=data_root,
                )

    def test_rejects_notes_directory(self):
        with tempfile.TemporaryDirectory() as data_root:
            notes_path = os.path.join(data_root, "groups", "team", "notes")

            with self.assertRaises(UnsafeIndexPathError):
                assert_safe_index_directory(
                    index_path=notes_path,
                    data_root=data_root,
                    notes_path=notes_path,
                )

    def test_rejects_root_attachments_directory(self):
        with tempfile.TemporaryDirectory() as data_root:
            with self.assertRaises(UnsafeIndexPathError):
                assert_safe_index_directory(
                    index_path=os.path.join(data_root, "attachments"),
                    data_root=data_root,
                    notes_path=data_root,
                )

    def test_rejects_group_root_named_index(self):
        with tempfile.TemporaryDirectory() as data_root:
            notes_path = os.path.join(data_root, "groups", "index", "notes")
            group_root = os.path.dirname(notes_path)

            with self.assertRaises(UnsafeIndexPathError):
                assert_safe_index_directory(
                    index_path=group_root,
                    data_root=data_root,
                    notes_path=notes_path,
                )

    def test_rejects_path_outside_data_root(self):
        with tempfile.TemporaryDirectory() as data_root:
            with tempfile.TemporaryDirectory() as other_root:
                with self.assertRaises(UnsafeIndexPathError):
                    assert_safe_index_directory(
                        index_path=os.path.join(other_root, ".copycat", "index"),
                        data_root=data_root,
                        notes_path=data_root,
                    )

    def test_rejects_index_not_under_copycat_directory(self):
        with tempfile.TemporaryDirectory() as data_root:
            with self.assertRaises(UnsafeIndexPathError):
                assert_safe_index_directory(
                    index_path=os.path.join(data_root, "index"),
                    data_root=data_root,
                    notes_path=data_root,
                )

    def test_rejects_non_index_basename(self):
        with tempfile.TemporaryDirectory() as data_root:
            with self.assertRaises(UnsafeIndexPathError):
                assert_safe_index_directory(
                    index_path=os.path.join(data_root, ".copycat", "cache"),
                    data_root=data_root,
                    notes_path=data_root,
                )


if __name__ == "__main__":
    unittest.main()
