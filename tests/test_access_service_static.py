import ast
import unittest
from pathlib import Path


class AccessServiceStaticTests(unittest.TestCase):
    def test_search_notes_does_not_reference_for_write(self):
        source_path = Path(__file__).resolve().parents[1] / "server" / "access" / "service.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8-sig"))
        search_notes = _find_method(tree, "AccessService", "search_notes")

        references = [
            node
            for node in ast.walk(search_notes)
            if isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id == "for_write"
        ]

        self.assertEqual(references, [])


def _find_method(tree, class_name, method_name):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return item
    raise AssertionError(f"{class_name}.{method_name} was not found")


if __name__ == "__main__":
    unittest.main()
