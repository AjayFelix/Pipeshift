"""Orchestrates the three pipeline phases: Extract -> Transform -> Load."""
import time

from dmt.extract import run_extract
from dmt.load import run_load
from dmt.transform import run_transform


def run_pipeline(progress=print) -> dict:
    t0 = time.time()
    progress("=== Extract: Postgres -> Parquet staging ===")
    extract_counts = run_extract(progress=progress)

    progress("=== Transform: staged Parquet -> star schema ===")
    transform_counts = run_transform(progress=progress)

    progress("=== Load: star schema -> MotherDuck ===")
    load_counts = run_load(progress=progress)

    progress(f"pipeline complete in {time.time() - t0:.1f}s")
    return {"extract": extract_counts, "transform": transform_counts, "load": load_counts}


if __name__ == "__main__":
    run_pipeline()
