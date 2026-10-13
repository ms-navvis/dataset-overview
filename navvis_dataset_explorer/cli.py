"""Standard-library-only CLI and report writer."""
import argparse
import csv
import json
import sys
from pathlib import Path

from .scanner import scan

DEVICE_MODELS = {"G11": "VLX 3", "G12": "VLX 4", "K4": "MLX", "L4": "CLX"}


def flatten(obj, prefix=""):
    result = {}
    for key, value in obj.items():
        field = "%s.%s" % (prefix, key) if prefix else key
        if isinstance(value, dict):
            result.update(flatten(value, field))
        elif isinstance(value, list):
            result[field] = json.dumps(value, ensure_ascii=False)
        else:
            result[field] = value
    return result


def csv_cell(value):
    """Keep metadata beginning with spreadsheet formulas as literal text."""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def write_report(inventory, destination):
    destination = Path(destination).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    # Embedded JSON is inert; escaping '<' prevents closing the script element.
    encoded = json.dumps(inventory, ensure_ascii=False, allow_nan=False)
    encoded = encoded.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    template = Path(__file__).with_name("dashboard.html").read_text(encoding="utf-8")
    if template.count("__INVENTORY__") != 1:
        raise ValueError("Dashboard template must have exactly one data placeholder")
    (destination / "index.html").write_text(template.replace("__INVENTORY__", encoded), encoding="utf-8")
    (destination / "dataset-inventory.json").write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    rows = []
    for dataset in inventory["datasets"]:
        row = flatten({key: value for key, value in dataset.items() if key != "metadata"})
        row.update(flatten(dataset["metadata"], "metadata"))
        device = dataset["metadata"].get("device", {})
        serial = device.get("serial", "") if isinstance(device, dict) else ""
        row["device_model"] = DEVICE_MODELS.get(str(serial).split("-")[0], "Unknown")
        rows.append(row)
    columns = list(dict.fromkeys(key for row in rows for key in row)) or ["path"]
    with (destination / "dataset-inventory.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows({k: csv_cell(v) for k, v in row.items()} for row in rows)
    return destination / "index.html"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Scan NavVis dataset.json files and create an offline dashboard.")
    parser.add_argument("root", type=Path, help="Mounted drive, NAS folder, UNC path, or local directory")
    parser.add_argument("--output", "-o", type=Path, default=Path("report"), help="Report directory (default: ./report)")
    parser.add_argument("--exclude", action="append", default=[], metavar="DIRECTORY_NAME", help="Skip this directory name at every depth; repeat as needed")
    parser.add_argument("--metadata-only", action="store_true", help="Read dataset metadata without measuring other files; sizes remain unavailable")
    parser.add_argument("--quiet", action="store_true", help="Hide periodic scan progress")
    parser.add_argument("--fail-on-errors", action="store_true", help="Write a partial report but return exit code 2 if scan errors occurred")
    args = parser.parse_args(argv)
    def progress(counts):
        print("Scanned {files:,} files / {directories:,} folders; found {dataset_json_files:,} dataset.json files".format(**counts), file=sys.stderr)
    try:
        inventory = scan(args.root, excludes=args.exclude, output_directory=args.output,
                         progress=None if args.quiet else progress, metadata_only=args.metadata_only)
        dashboard = write_report(inventory, args.output)
    except (OSError, ValueError) as exc:
        parser.exit(1, "Error: %s\n" % exc)
    summary = inventory["summary"]
    size = summary["dataset_logical_bytes"]
    print("%s datasets; %s" % (summary["dataset_count"], "sizes not measured" if size is None else "%.2f GB of files" % (size / 1e9)))
    print("Dashboard: %s" % dashboard)
    if summary["errors"]:
        print("WARNING: %d scan errors; review diagnostics in the dashboard. Totals may be incomplete." % len(summary["errors"]), file=sys.stderr)
    if not summary["dataset_count"]:
        print("No readable dataset.json files were found.", file=sys.stderr)
    return 2 if args.fail_on_errors and summary["errors"] else 0
