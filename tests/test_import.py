"""Minimal bootstrap import check."""

import importlib
import unittest


class TestImport(unittest.TestCase):
    def test_package_import(self):
        package = importlib.import_module("stability_label_curation")
        self.assertEqual(package.__name__, "stability_label_curation")


if __name__ == "__main__":
    unittest.main()
