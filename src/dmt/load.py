"""Load phase: star-schema Parquet -> MotherDuck (cloud OLAP target)."""
import os
import time

import duckdb

from dmt.config import MOTHERDUCK_DB, MOTHERDUCK_TOKEN, STAGING_DIR

STAR_DIR = STAGING_DIR / "star"

STAR_TABLES = [
    "dim_course",
    "dim_student",
    "dim_assessment",
    "fact_assessment_submission",
    "fact_vle_interaction",
]


def motherduck_connect():
    if not MOTHERDUCK_TOKEN:
        raise RuntimeError("MOTHERDUCK_TOKEN is not set (check .env)")
    os.environ["motherduck_token"] = MOTHERDUCK_TOKEN
    con = duckdb.connect("md:")
    con.execute(f"CREATE DATABASE IF NOT EXISTS {MOTHERDUCK_DB}")
    con.execute(f"USE {MOTHERDUCK_DB}")
    return con


def run_load(progress=print) -> dict:
    con = motherduck_connect()
    counts = {}
    t0 = time.time()
    try:
        for table in STAR_TABLES:
            path = STAR_DIR / f"{table}.parquet"
            if not path.exists():
                raise FileNotFoundError(f"missing {path} -- run the transform phase first")
            t1 = time.time()
            con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_parquet('{path}')")
            n = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            counts[table] = n
            progress(f"loaded {table} into MotherDuck: {n} rows in {time.time() - t1:.1f}s")
    finally:
        con.close()
    progress(f"load phase done in {time.time() - t0:.1f}s")
    return counts


if __name__ == "__main__":
    run_load()
