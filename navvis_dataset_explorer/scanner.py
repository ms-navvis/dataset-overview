"""Read metadata and measure files in one traversal, without following links."""
import json
from collections import Counter
import os
import stat
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_EXCLUDES = frozenset({
    ".Trashes", ".Spotlight-V100", ".fseventsd", ".git",
    "$RECYCLE.BIN", "System Volume Information", "@eaDir", "#recycle",
})
MAX_METADATA_BYTES = 16 * 1024 * 1024


def scan(root, *, excludes=(), output_directory=None, progress=None, metadata_only=False):
    """Scan a mounted/local directory. File sizes are logical; allocation is optional.

    Dataset folders include their children. The overall total counts nested
    dataset folders only once. Unreadable entries produce diagnostics, not
    invented sizes. Nothing is written to the scanned directory.
    """
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Scan root must be an accessible directory: %s" % root)
    excluded_names = DEFAULT_EXCLUDES | set(excludes)
    output_directory = (Path(output_directory).expanduser().resolve()
                        if output_directory else None)
    if output_directory == root:
        raise ValueError("Output directory must be different from the scan root")
    datasets, errors, skipped = [], [], []
    directories = {}
    counters = {"files": 0, "directories": 0, "dataset_json_files": 0}
    last_progress = time.monotonic()

    def relative(path):
        return Path(path).relative_to(root).as_posix() or "."

    def error(path, operation, exc):
        errors.append({"path": relative(path), "operation": operation,
                       "message": str(exc)})

    def tick():
        nonlocal last_progress
        if progress and time.monotonic() - last_progress >= 5:
            progress(dict(counters))
            last_progress = time.monotonic()

    # Each regular file is stat'ed once. Directory totals are merged bottom-up.
    # Keep directory totals rather than storing every file path (NAS scale).
    def walk_error(exc):
        error(exc.filename or root, "list directory", exc)
        path = Path(exc.filename or root)
        # Mark ancestor totals incomplete even if this directory was not yielded.
        while path == root or root in path.parents:
            directories.setdefault(path, {"bytes": 0, "allocated": 0,
                                          "files": 0, "complete": True})["complete"] = False
            if path == root:
                break
            path = path.parent

    for base, dirs, names in os.walk(root, followlinks=False, onerror=walk_error):
        base = Path(base)
        counters["directories"] += 1
        totals = directories.setdefault(base, {"bytes": 0, "allocated": 0,
                                              "files": 0, "complete": True})
        kept = []
        for name in dirs:
            path = base / name
            if name in excluded_names or path == output_directory:
                skipped.append(relative(path))
            elif path.is_symlink():
                skipped.append(relative(path))
            else:
                kept.append(name)
        dirs[:] = kept
        for name in names:
            path = base / name
            try:
                if metadata_only and name != "dataset.json":
                    continue
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode):
                    continue
                counters["files"] += 1
                totals["bytes"] += info.st_size
                totals["files"] += 1
                blocks = getattr(info, "st_blocks", None)
                if blocks is None:
                    totals["allocated"] = None
                elif totals["allocated"] is not None:
                    totals["allocated"] += blocks * 512
                if name == "dataset.json":
                    counters["dataset_json_files"] += 1
                    if info.st_size > MAX_METADATA_BYTES:
                        raise ValueError("Metadata exceeds the 16 MiB size limit")
                    with path.open("r", encoding="utf-8-sig") as handle:
                        metadata = json.load(handle, parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Invalid JSON number: " + value)))
                    if not isinstance(metadata, dict):
                        raise ValueError("dataset.json must contain a JSON object")
                    datasets.append({"path": relative(path), "folder_path": str(base),
                                     "metadata": metadata, "_folder": base})
            except (OSError, ValueError, UnicodeError) as exc:
                error(path, "read metadata" if name == "dataset.json" else "stat file", exc)
                if not (name == "dataset.json" and isinstance(exc, (ValueError, UnicodeError))):
                    totals["complete"] = False
            tick()
        tick()

    for folder in sorted(directories, key=lambda p: len(p.parts), reverse=True):
        if folder == root:
            continue
        parent = directories.setdefault(folder.parent, {"bytes": 0, "allocated": 0,
                                                       "files": 0, "complete": True})
        child = directories[folder]
        parent["bytes"] += child["bytes"]
        parent["files"] += child["files"]
        parent["complete"] &= child["complete"]
        parent["allocated"] = (None if parent["allocated"] is None or child["allocated"] is None
                               else parent["allocated"] + child["allocated"])
    for dataset in datasets:
        totals = directories[dataset["_folder"]]
        dataset.update(logical_bytes=None if metadata_only else totals["bytes"],
                       allocated_bytes=None if metadata_only else totals["allocated"],
                       file_count=None if metadata_only else totals["files"],
                       size_complete=totals["complete"])
    datasets.sort(key=lambda d: d["path"])
    dataset_folders = {d["_folder"] for d in datasets}
    top_level = [d for d in datasets if not any(p in dataset_folders for p in d["_folder"].parents)]
    top_folders = {d["_folder"] for d in top_level}
    groups = {}
    for d in datasets:
        group = d["path"].split("/")[0] if "/" in d["path"] else root.name
        d["collection"] = group
        entry = groups.setdefault(group, {"datasets": 0, "logical_bytes": 0, "allocated_bytes": 0})
        entry["datasets"] += 1
        if d["_folder"] in top_folders:
            entry["logical_bytes"] = None if metadata_only else entry["logical_bytes"] + d["logical_bytes"]
            entry["allocated_bytes"] = (None if entry["allocated_bytes"] is None or d["allocated_bytes"] is None
                                        else entry["allocated_bytes"] + d["allocated_bytes"])
    uuids = []
    for d in datasets:
        identity = d["metadata"].get("dataset", {})
        uuid = identity.get("dataset_uuid") if isinstance(identity, dict) else None
        if isinstance(uuid, str) and uuid:
            uuids.append(uuid)
    uuid_counts = Counter(uuids)
    allocated = [d["allocated_bytes"] for d in top_level]
    summary = {
        "drive": str(root), "label": root.name,
        "scan_time_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_count": len(datasets), "dataset_json_files": counters["dataset_json_files"],
        "unique_uuids": len(set(uuids)), "duplicate_uuids": sorted(x for x, count in uuid_counts.items() if count > 1),
        "dataset_logical_bytes": None if metadata_only else sum(d["logical_bytes"] for d in top_level),
        "dataset_allocated_bytes": None if None in allocated else sum(allocated),
        "nested_dataset_count": len(datasets) - len(top_level),
        "groups": groups, "scanned_file_count": counters["files"],
        "scanned_file_bytes": None if metadata_only else directories.get(root, {}).get("bytes", 0),
        "scan_mode": "metadata-only" if metadata_only else "full",
        "size_complete": not errors,
        "excluded_paths": skipped, "errors": errors,
    }
    for d in datasets:
        del d["_folder"]
    if progress:
        progress(dict(counters))
    return {"summary": summary, "datasets": datasets}
