import importlib.util
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("refine_build", ROOT / "scripts" / "build.py")
build = importlib.util.module_from_spec(_spec)
sys.modules["refine_build"] = build
_spec.loader.exec_module(build)


class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.src = cls.tmp / "refine"
        shutil.copytree(
            build.SRC, cls.src, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.log", "meta.json")
        )
        (cls.src / "__pycache__").mkdir(exist_ok=True)
        (cls.src / "__pycache__" / "x.pyc").write_bytes(b"\0")
        (cls.src / "theme" / "__pycache__").mkdir(parents=True, exist_ok=True)
        (cls.src / "theme" / "__pycache__" / "y.pyo").write_bytes(b"\0")
        (cls.src / "user_files" / "logs").mkdir(parents=True, exist_ok=True)
        (cls.src / "user_files" / "logs" / "x.log").write_text("log")
        (cls.src / "user_files" / "secret.css").write_text("x")
        (cls.src / "meta.json").write_text("{}")
        (cls.src / ".DS_Store").write_bytes(b"\0")
        (cls.src / "Thumbs.db").write_bytes(b"\0")
        (cls.src / "stray.pyc").write_bytes(b"\0")
        cls.out1 = build.build(cls.src, cls.tmp / "o1")
        cls.out2 = build.build(cls.src, cls.tmp / "o2")
        with zipfile.ZipFile(cls.out1) as z:
            cls.names = z.namelist()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_name(self):
        self.assertEqual(self.out1.name, "refine-0.1.0.ankiaddon")

    def test_root_files_no_top_folder(self):
        self.assertIn("__init__.py", self.names)
        self.assertIn("manifest.json", self.names)
        self.assertFalse(any(n.startswith("refine/") for n in self.names))

    def test_paths_clean(self):
        for n in self.names:
            self.assertNotIn("\\", n)
            self.assertFalse(n.startswith("/"))
            self.assertNotIn("..", n.split("/"))

    def test_excluded_absent(self):
        for n in self.names:
            self.assertNotIn("__pycache__", n)
            self.assertFalse(n.endswith((".pyc", ".pyo", ".log")), n)
            self.assertNotIn(n.rsplit("/", 1)[-1], ("meta.json", ".DS_Store", "Thumbs.db"))
        self.assertEqual([n for n in self.names if n.startswith("user_files/")], ["user_files/README.txt"])

    def test_sorted_and_fixed_times(self):
        self.assertEqual(self.names, sorted(self.names))
        with zipfile.ZipFile(self.out1) as z:
            for i in z.infolist():
                self.assertEqual(i.date_time, build.FIXED_TIME)
                self.assertEqual(i.compress_type, zipfile.ZIP_DEFLATED)

    def test_reproducible(self):
        self.assertEqual(self.out1.read_bytes(), self.out2.read_bytes())

    def test_validate_ok(self):
        problems, total = build.validate(self.out1)
        self.assertEqual(problems, [])
        self.assertGreater(total, 0)

    def test_validate_rejects_bad_archives(self):
        bad = self.tmp / "bad.ankiaddon"
        with zipfile.ZipFile(bad, "w") as z:
            z.writestr("refine/__init__.py", "")
            z.writestr("a\\b.py", "")
            z.writestr("../evil.py", "")
            z.writestr("__pycache__/m.pyc", "")
        problems = " | ".join(build.validate(bad)[0])
        for needle in ("'..'", "bytecode", "__init__.py not at", "manifest.json not at"):
            self.assertIn(needle, problems)

    def test_real_tree_builds_without_pycache(self):
        out = build.build(build.SRC, self.tmp / "real")
        self.assertEqual(build.validate(out)[0], [])
        self.assertIn("__init__.py", build.top_level(out))


if __name__ == "__main__":
    unittest.main()
