# NavVis Dataset Explorer

Turn a folder of NavVis recordings into an offline HTML dashboard. Scan a local drive or mounted NAS share, then open the report in a browser.

The dashboard supports search across every metadata field, collection and device filters, sortable columns, panorama counts, expandable metadata, pagination, and export of all filtered results to CSV.

## Quick start

Requires Python 3.9 or newer. No third-party runtime packages, web server, cloud account, or build step are required.

1. Download this repository as a ZIP and extract it, or clone it.
2. Open a terminal in the extracted repository folder.
3. Run:

```sh
python3 -m navvis_dataset_explorer "/path/to/datasets" --output report
```

On Windows, use `py -m navvis_dataset_explorer` instead of `python3`.

Open `report/index.html` in a browser. The report also includes `dataset-inventory.json` with every original metadata field and `dataset-inventory.csv` for spreadsheets. Generated reports stay on your computer. The HTML embeds its data and works offline.

For a quick preview, open [the synthetic demo](examples/demo.html) after downloading the repository.

## NAS and PRC usage

Run the scanner on a computer that can read the share, or directly on the NAS if it has Python and you have an approved shell session.

For PRC access, connect the required VPN (Tunnelblick on macOS) first. Mount the SMB share through Finder or your operating system, then pass its **filesystem path** to the scanner. An `smb://` URL is a connection address, not a filesystem path.

macOS, with the PRC share mounted as `PRC`:

```sh
python3 -m navvis_dataset_explorer "/Volumes/PRC/Sample_Data" --output report
```

Windows, after connecting the required VPN and mounting the share as `Z:`:

```powershell
py -m navvis_dataset_explorer "Z:\Sample_Data" --output report
```

Linux, after mounting the share:

```sh
python3 -m navvis_dataset_explorer "/mnt/prc/Sample_Data" --output report
```

The scanner uses your existing filesystem access. It does not store SMB passwords or connect to the VPN itself. Put the output on a local disk for best performance. Leave the VPN and share connected throughout the scan.

A large NAS may take time: the scanner must list folders and request each file's size, but reads file contents only for `dataset.json`. Progress is printed about every five seconds during traversal. The dashboard shows 100 rows per page; filters, totals, sorting, and CSV export cover the full inventory.

For a quick first inventory on a large NAS, skip file-size measurement:

```sh
python3 -m navvis_dataset_explorer "/Volumes/PRC/Sample_Data" --metadata-only --output report
```

This still walks the folder tree and reads each `dataset.json`, but does not request a size for every other file. Sizes display as **Not measured** / **Unavailable**. Rerun without `--metadata-only` for storage totals.

## Options

```sh
python3 -m navvis_dataset_explorer "/Volumes/PRC/Sample_Data" \
  --output report \
  --exclude old-backups \
  --exclude cache \
  --fail-on-errors
```

- `--output`, `-o`: destination directory; defaults to `./report`.
- `--exclude`: skip folders with this exact name at every depth; can be repeated.
- `--metadata-only`: scan metadata without measuring file sizes.
- `--quiet`: suppress progress messages.
- `--fail-on-errors`: generate a partial report but return exit code 2 if any scan errors occur, useful for scheduled jobs.

The root must be an accessible folder. The output directory cannot be the root itself. An output directory inside the root is excluded from scanning.

## Counts and size measurements

- One dataset is one readable `dataset.json` containing a JSON object. The dashboard preserves UUIDs and reports duplicates; it does not silently discard copies of a dataset.
- Dataset size includes every regular file beneath its folder. Folder links and other symbolic links are not followed.
- Nested dataset folders are included in their parent row's size, but are counted only once in dashboard storage totals. The recording and pano totals sum the selected dataset records.
- File size is logical bytes. Disk space occupied uses the filesystem's allocated blocks when available. Some NAS and Windows filesystems do not report allocation; the dashboard displays **Unavailable** rather than estimating it. Server compression, deduplication, replication, and snapshots are not measured.
- GB means 1,000,000,000 bytes.
- Panos comes from `statistics.capture_locations_panoramas_rec`.
- Area v2 comes from `statistics.mapped_area_v2_rec`. All original area estimates are available in Details.
- Device models are inferred from the serial prefix: G11 → VLX 3, G12 → VLX 4, K4 → MLX, L4 → CLX. Unknown prefixes remain Unknown.
- Missing metadata is shown as a dash. Read errors and partial sizes appear in scan diagnostics; partial sizes have an asterisk.
- System folders (`.Trashes`, `.Spotlight-V100`, `.fseventsd`, `.git`, `$RECYCLE.BIN`, `System Volume Information`, `@eaDir`, and `#recycle`) are skipped.
- A report is a snapshot. Files changing during a scan can affect the results; rerun to refresh it.

The generated report contains dataset names, identifiers, device serials, and local paths. Share the code freely; review a generated inventory before sharing that inventory. The public demo contains synthetic data only.

## Optional installation

Run from the repository folder as above, or install it locally:

```sh
python3 -m pip install .
navvis-dataset-explorer "/path/to/datasets" --output report
```

## Development

```sh
python3 -m unittest discover -s tests -v
node tests/test_dashboard.cjs
```

The tests create temporary synthetic datasets and check sizes, nested folders, exclusions, bad metadata, report escaping, filters, sorting, pagination, and device mappings. No real scan data is needed.

MIT licensed. This is a community utility, not an official NavVis product.
