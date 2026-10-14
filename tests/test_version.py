import unittest
from pathlib import Path

from kyanbasu import __version__
from kyanbasu.version import __version__ as version_module_version


class TestVersionModule(unittest.TestCase):
    def test_root_level_script_is_not_a_supported_entry_point(self):
        self.assertFalse((Path(__file__).parents[1] / "Kyanbasu.py").exists())

    def test_package_version_comes_from_dependency_free_version_module(self):
        self.assertEqual(__version__, version_module_version)

if __name__ == "__main__":
    unittest.main()
