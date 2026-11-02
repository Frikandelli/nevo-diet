"""Put the NEVO files in data/nevo/ from RIVM's zip.  python3 setup_data.py [path/to/zip]

Based on data from NEVO online version 2025/9.0, RIVM, Bilthoven and other data sources.

The NEVO files are RIVM's copyright and aren't in this repo, so every computer needs the zip once. RIVM provides it for
free. The app shows the same steps and takes the zip by upload. Without a path this looks in data/, ~/Downloads,
~/Documents and ~/Desktop. The CSV files are extracted unchanged; nothing else is touched.
"""
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NEVO_DIR = ROOT / "data/nevo"
REQUEST_URL = "https://www.rivm.nl/en/dutch-food-composition-database/nevo-online-request-dataset"
REQUIRED = ["NEVO2025_v9.0.csv", "NEVO2025_v9.0_Recepten_Recipes.csv"]      # what the code reads
HELP = f"""
The NEVO dataset isn't on this computer yet. It's free, but only RIVM may hand it out.

  1. Request it: {REQUEST_URL}
     Fill in your email and accept the conditions. RIVM emails you a download link.
  2. Upload the zip in the app, or put it in ~/Downloads and start the app again, or run:
     python3 setup_data.py /path/to/the.zip
"""


def missing(folder=NEVO_DIR):
    return [f for f in REQUIRED if not (folder / f).exists()]


def candidates():
    folders = [ROOT / "data"] + [Path.home() / d for d in ("Downloads", "Documents", "Desktop")]
    found = [z for d in folders if d.is_dir() for z in d.iterdir() if z.suffix.lower() == ".zip"
             and z.name.lower().startswith("nevo")]
    return sorted(found, key=lambda z: z.stat().st_mtime, reverse=True)


def extract(source):
    """Extract the CSV files of a zip (a path or an open file) that holds the required files. False if it doesn't."""
    with zipfile.ZipFile(source) as z:
        csvs = {Path(m).name: m for m in z.namelist() if m.lower().endswith(".csv")}
        if not all(f in csvs for f in REQUIRED):
            return False
        NEVO_DIR.mkdir(parents=True, exist_ok=True)
        for name, member in csvs.items():
            (NEVO_DIR / name).write_bytes(z.read(member))
    return True


def main(args):
    if args:
        zips = [Path(args[0]).expanduser()]
    elif missing():
        zips = candidates()
    else:
        return 0
    for z in zips:
        try:
            if extract(z):
                print(f"NEVO files extracted from {z} to {NEVO_DIR}")
                return 0
        except (OSError, zipfile.BadZipFile) as e:
            print(f"Can't read {z}: {e}", file=sys.stderr)
    if zips:
        print("Tried, but without the required NEVO files: " + ", ".join(map(str, zips)), file=sys.stderr)
    print(HELP, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
