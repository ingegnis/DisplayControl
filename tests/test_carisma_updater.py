"""Offline updater regression: staged archives, backups and safe rollback."""
import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

import carisma_updater as updater


def archive(path, files, wrapper=""):
    with zipfile.ZipFile(path, "w") as z:
        if wrapper:
            z.writestr(wrapper + "/", "")
        for name, content in files.items():
            z.writestr(wrapper + "/" + name if wrapper else name, content)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(version):
    return {"server.py": "# " + version, "prompt_module.py": "# module",
            "prompt_player.html": "<html>Prompt</html>"}


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / "install"

    def add_release(self, name, files=None, wrapper="repo-main"):
        path = self.base / (name + ".zip")
        sha = archive(path, files if files is not None else source(name), wrapper)
        updater.stage(self.home, path, sha, name)
        return path

    def test_wrapped_archive_stage_activation_and_rollback(self):
        self.add_release("v1")
        self.add_release("v2")
        data = self.home / "shared" / "data"
        (data / "script.txt").write_text("PRIVATE SCRIPT", encoding="utf-8")
        updater.activate(self.home, "v1", None)
        self.assertTrue((self.home / "current" / "data" / "script.txt").is_file())
        updater.activate(self.home, "v2", None)
        self.assertEqual((self.home / "current" / "server.py").read_text(), "# v2")
        backups = list((self.home / "backups").glob("data-*"))
        self.assertGreaterEqual(len(backups), 2)
        self.assertEqual((backups[-1] / "script.txt").read_text(), "PRIVATE SCRIPT")
        updater.rollback(self.home, None)
        self.assertEqual((self.home / "current" / "server.py").read_text(), "# v1")
        self.assertEqual((self.home / "current" / "data" / "script.txt").read_text(), "PRIVATE SCRIPT")

    def test_bad_hash_does_not_stage(self):
        path = self.base / "bad.zip"
        archive(path, source("bad"))
        with self.assertRaises(RuntimeError):
            updater.stage(self.home, path, "0" * 64, "bad")
        self.assertFalse((self.home / "releases" / "bad").exists())

    def test_traversal_rejected(self):
        path = self.base / "traversal.zip"
        sha = archive(path, {**source("x"), "../escape": "bad"}, wrapper="")
        with self.assertRaises(RuntimeError):
            updater.stage(self.home, path, sha, "traversal")
        self.assertFalse((self.home / "releases" / "traversal").exists())
        self.assertFalse((self.home / "escape").exists())

    def test_operational_data_rejected(self):
        path = self.base / "secrets.zip"
        sha = archive(path, {**source("x"), "data/cluster.json": "secret"})
        with self.assertRaises(RuntimeError):
            updater.stage(self.home, path, sha, "secrets")
        self.assertFalse((self.home / "releases" / "secrets").exists())


if __name__ == "__main__":
    unittest.main()
