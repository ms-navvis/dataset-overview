"""Generate an offline preview with synthetic metadata only."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from navvis_dataset_explorer.cli import write_report

names = ["Demo office", "Demo workshop", "Demo facade", "Demo lobby"]
serials = ["G11-0000", "G12-0000", "K4-0000", "L4-0000"]
datasets = []
for i, (name, serial) in enumerate(zip(names, serials)):
    datasets.append({"path": "Synthetic/%s/dataset.json" % i,
                     "folder_path": "/demo/Synthetic/%s" % i, "collection": "Synthetic",
                     "logical_bytes": (i+1)*1000000000, "allocated_bytes": (i+1)*1100000000,
                     "file_count": (i+1)*100, "size_complete": True,
                     "metadata": {"dataset": {"name": name, "dataset_id": "synthetic-%s" % i,
                                              "dataset_uuid": "00000000-0000-0000-0000-%012d" % i},
                                  "root": {"dataset_type": "rec", "dataset_version_layout": "rec-v4"},
                                  "device": {"serial": serial, "software_release_rec": "synthetic-example"},
                                  "statistics": {"mapping_timestart": 1767225600+i*3600,
                                                 "mapping_duration": 300+i*120,
                                                 "trajectory_length": 100+i*50,
                                                 "capture_locations_panoramas_rec": 10+i*20,
                                                 "mapped_area_v2_rec": 200+i*100}}})
inventory = {"summary": {"drive": "/demo", "label": "Synthetic example data",
                         "scan_time_utc": "2026-01-01T00:00:00Z", "dataset_count": 4,
                         "errors": [], "nested_dataset_count": 0}, "datasets": datasets}
# Intermediate exports are kept out of the source tree.
import tempfile
with tempfile.TemporaryDirectory() as folder:
    page = write_report(inventory, folder)
    Path(__file__).with_name("demo.html").write_text(page.read_text(encoding="utf-8"), encoding="utf-8")
print("Wrote examples/demo.html (synthetic data)")
