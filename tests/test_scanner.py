import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from navvis_dataset_explorer.cli import main, write_report
from navvis_dataset_explorer.scanner import scan


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "scan"
        self.root.mkdir()

    def dataset(self, folder, metadata=None, size=7):
        folder = self.root / folder
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "dataset.json").write_text(json.dumps(metadata if metadata is not None else {"dataset": {"name": folder.name, "dataset_uuid": "synthetic"}}), encoding="utf-8")
        (folder / "payload.bin").write_bytes(b"x" * size)
        return folder

    def test_nested_totals_do_not_double_count(self):
        parent = self.dataset("collection/parent")
        self.dataset("collection/parent/child", size=11)
        inventory = scan(self.root)
        actual = sum(p.stat().st_size for p in parent.rglob("*") if p.is_file())
        self.assertEqual(inventory["summary"]["dataset_count"], 2)
        self.assertEqual(inventory["summary"]["dataset_logical_bytes"], actual)
        self.assertEqual(inventory["summary"]["nested_dataset_count"], 1)
        self.assertEqual(next(d for d in inventory["datasets"] if d["path"] == "collection/parent/dataset.json")["logical_bytes"], actual)
        self.assertEqual(inventory["summary"]["duplicate_uuids"], ["synthetic"])

    def test_exclusions_and_output_directory(self):
        self.dataset("valid")
        self.dataset(".Trashes/hidden")
        self.dataset("cache/hidden")
        self.dataset("report/hidden")
        inventory = scan(self.root, excludes=["cache"], output_directory=self.root / "report")
        self.assertEqual(inventory["summary"]["dataset_count"], 1)
        self.assertEqual(len(inventory["summary"]["excluded_paths"]), 3)

    def test_bad_and_missing_metadata(self):
        self.dataset("valid", metadata={})
        bad = self.dataset("invalid")
        (bad / "dataset.json").write_text('{"broken":', encoding="utf-8")
        inventory = scan(self.root)
        self.assertEqual(inventory["summary"]["dataset_count"], 1)
        self.assertEqual(inventory["summary"]["dataset_json_files"], 2)
        self.assertEqual(len(inventory["summary"]["errors"]), 1)
        write_report(inventory, self.base / "output")

    def test_read_error_marks_parent_size_partial(self):
        folder = self.dataset("valid")
        original = Path.lstat
        def broken_lstat(path, *args, **kwargs):
            if path == folder / "payload.bin":
                raise PermissionError("Synthetic denied file")
            return original(path, *args, **kwargs)
        with patch.object(Path, "lstat", broken_lstat):
            inventory = scan(self.root)
        self.assertFalse(inventory["datasets"][0]["size_complete"])
        self.assertEqual(len(inventory["summary"]["errors"]), 1)

    def test_metadata_is_escaped_in_html_and_csv(self):
        self.dataset("hostile", {"dataset": {"name": '</script><script>bad()</script>', "dataset_id": '=1+1'}})
        inventory = scan(self.root)
        output = self.base / "out"
        write_report(inventory, output)
        html = (output / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('</script><script>bad()', html)
        with (output / "dataset-inventory.csv").open(encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]["metadata.dataset.dataset_id"], "'=1+1")
        self.assertEqual(json.loads((output / "dataset-inventory.json").read_text())["datasets"], inventory["datasets"])

    def test_symlinks_not_followed(self):
        folder = self.dataset("valid")
        try:
            (self.root / "link").symlink_to(folder, target_is_directory=True)
            (folder / "linked-file").symlink_to(folder / "payload.bin")
        except OSError:
            self.skipTest("Symbolic links unavailable")
        inventory = scan(self.root)
        self.assertEqual(inventory["summary"]["dataset_count"], 1)
        self.assertEqual(inventory["datasets"][0]["file_count"], 2)

    def test_root_metadata_and_rejected_output(self):
        self.dataset("", metadata={})
        self.assertEqual(scan(self.root)["summary"]["dataset_count"], 1)
        with self.assertRaises(ValueError):
            scan(self.root, output_directory=self.root)

    def test_nan_rejected_and_fail_on_errors_exit(self):
        folder = self.dataset("broken")
        (folder / "dataset.json").write_text('{"value": NaN}', encoding="utf-8")
        code = main([str(self.root), "-o", str(self.base / "out"), "--quiet", "--fail-on-errors"])
        self.assertEqual(code, 2)
        self.assertTrue((self.base / "out/index.html").exists())

    def test_metadata_only_skips_payload_stat(self):
        folder = self.dataset("valid")
        original = Path.lstat
        def checked_lstat(path, *args, **kwargs):
            if path == folder / "payload.bin":
                raise AssertionError("Metadata-only mode must not stat payload files")
            return original(path, *args, **kwargs)
        with patch.object(Path, "lstat", checked_lstat):
            inventory = scan(self.root, metadata_only=True)
        self.assertEqual(inventory["summary"]["dataset_count"], 1)
        self.assertIsNone(inventory["summary"]["dataset_logical_bytes"])
        self.assertIsNone(inventory["datasets"][0]["logical_bytes"])
        self.assertIsNone(inventory["datasets"][0]["allocated_bytes"])
        self.assertEqual(inventory["summary"]["errors"], [])

    def test_empty_inventory(self):
        result = scan(self.root)
        write_report(result, self.base / "out")
        self.assertEqual(result["summary"]["dataset_count"], 0)
        self.assertEqual(result["summary"]["dataset_logical_bytes"], 0)


if __name__ == "__main__":
    unittest.main()
