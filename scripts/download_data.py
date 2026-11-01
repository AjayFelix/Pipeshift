"""One-time OULAD dataset download. No account/API token required.

The original https://analyse.kmi.open.ac.uk/open_dataset link has been
retired (redirects to a generic OU Analyse page as of Nov 2026); this uses
the UCI Machine Learning Repository mirror (dataset id 349), which is the
same CC BY 4.0 dataset and needs no authentication.
"""
import zipfile
from pathlib import Path

import requests

URL = "https://archive.ics.uci.edu/static/public/349/open+university+learning+analytics+dataset.zip"
ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
ZIP_PATH = RAW_DIR / "oulad.zip"
EXTRACT_DIR = RAW_DIR / "oulad"

EXPECTED_FILES = [
    "courses.csv", "assessments.csv", "vle.csv",
    "studentInfo.csv", "studentRegistration.csv",
    "studentAssessment.csv", "studentVle.csv",
]


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if not ZIP_PATH.exists():
        print(f"downloading {URL}")
        resp = requests.get(URL, stream=True, timeout=120)
        resp.raise_for_status()
        with open(ZIP_PATH, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        print(f"saved {ZIP_PATH} ({ZIP_PATH.stat().st_size / 1e6:.1f} MB)")
    else:
        print(f"{ZIP_PATH} already present, skipping download")

    with zipfile.ZipFile(ZIP_PATH) as zf:
        zf.extractall(EXTRACT_DIR)

    missing = [f for f in EXPECTED_FILES if not (EXTRACT_DIR / f).exists()]
    if missing:
        raise SystemExit(f"extraction incomplete, missing: {missing}")

    print(f"extracted to {EXTRACT_DIR}")


if __name__ == "__main__":
    main()
