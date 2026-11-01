"""Extract phase: PostgreSQL (OLTP) -> Parquet staging files.

Small reference tables are extracted in one shot. student_vle (~10.6M rows)
is extracted in batches via keyset pagination on its surrogate id, writing
one Parquet part file per batch, so the process never holds the whole table
in memory and never issues one unbounded query against the source.
"""
import time

import pandas as pd
from sqlalchemy import create_engine

from dmt.config import BATCH_SIZE, POSTGRES_DSN, STAGING_DIR

SMALL_TABLES = [
    "courses",
    "assessments",
    "vle",
    "student_info",
    "student_registration",
    "student_assessment",
]


def extract_small_table(engine, table: str) -> int:
    df = pd.read_sql(f"SELECT * FROM {table}", engine)
    out_dir = STAGING_DIR / table
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_dir / "part-0000.parquet", index=False)
    return len(df)


def extract_student_vle(engine, batch_size: int = BATCH_SIZE, progress=print) -> int:
    out_dir = STAGING_DIR / "student_vle"
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob("part-*.parquet"):
        f.unlink()

    last_id = 0
    part = 0
    total = 0
    while True:
        query = (
            "SELECT id, code_module, code_presentation, id_student, id_site, date, sum_click "
            "FROM student_vle WHERE id > %(last_id)s ORDER BY id LIMIT %(batch_size)s"
        )
        df = pd.read_sql(query, engine, params={"last_id": last_id, "batch_size": batch_size})
        if df.empty:
            break
        df.to_parquet(out_dir / f"part-{part:04d}.parquet", index=False)
        last_id = int(df["id"].max())
        total += len(df)
        part += 1
        progress(f"student_vle: batch {part} ({total} rows so far)")
    return total


def run_extract(progress=print) -> dict:
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    engine = create_engine(POSTGRES_DSN)
    counts = {}
    try:
        for table in SMALL_TABLES:
            t0 = time.time()
            n = extract_small_table(engine, table)
            counts[table] = n
            progress(f"extracted {table}: {n} rows in {time.time() - t0:.1f}s")

        t0 = time.time()
        n = extract_student_vle(engine, progress=progress)
        counts["student_vle"] = n
        progress(f"extracted student_vle: {n} rows in {time.time() - t0:.1f}s")
    finally:
        engine.dispose()
    return counts


if __name__ == "__main__":
    run_extract()
