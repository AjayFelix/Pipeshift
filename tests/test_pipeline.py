import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb

from dmt.config import STAGING_DIR

STAR_DIR = STAGING_DIR / "star"


def test_staged_source_tables_present():
    for table in ["courses", "assessments", "vle", "student_info", "student_registration", "student_assessment", "student_vle"]:
        parts = list((STAGING_DIR / table).glob("part-*.parquet"))
        assert parts, f"no staged parquet for {table}"


def test_star_schema_present():
    for table in ["dim_course", "dim_student", "dim_assessment", "fact_assessment_submission", "fact_vle_interaction"]:
        assert (STAR_DIR / f"{table}.parquet").exists(), f"missing {table}.parquet"


def test_fact_vle_interaction_no_rows_dropped():
    con = duckdb.connect()
    source_count = con.execute(
        f"SELECT count(*) FROM read_parquet('{STAGING_DIR / 'student_vle' / 'part-*.parquet'}')"
    ).fetchone()[0]
    fact_count = con.execute(
        f"SELECT count(*) FROM read_parquet('{STAR_DIR / 'fact_vle_interaction.parquet'}')"
    ).fetchone()[0]
    con.close()
    assert source_count == fact_count == 10_655_280


def test_fact_vle_interaction_has_stable_row_id():
    con = duckdb.connect()
    n_distinct = con.execute(
        f"SELECT count(DISTINCT source_id) FROM read_parquet('{STAR_DIR / 'fact_vle_interaction.parquet'}')"
    ).fetchone()[0]
    con.close()
    assert n_distinct == 10_655_280
