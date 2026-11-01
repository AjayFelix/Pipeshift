"""Transform phase: staged Parquet (raw, source-shaped) -> star-schema Parquet.

Runs entirely in local DuckDB against the Parquet files written by the
Extract phase -- no network, no MotherDuck connection needed for this step.

Dimensions get surrogate integer keys (row_number over a stable sort) so the
fact tables carry FK columns rather than natural composite keys, matching a
conventional star schema for the report's database-design section.

vle.csv (activity-type metadata, 6,364 rows) is denormalized directly into
fact_vle_interaction rather than kept as its own tiny dimension -- defensible
either way at this scale; this project denormalizes it to keep the schema to
four tables.
"""
import time

import duckdb

from dmt.config import STAGING_DIR

STAR_DIR = STAGING_DIR / "star"


def _glob(table: str) -> str:
    return str(STAGING_DIR / table / "part-*.parquet")


def run_transform(progress=print) -> dict:
    STAR_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    counts = {}
    t0 = time.time()

    con.execute(f"""
        CREATE OR REPLACE TABLE dim_course AS
        SELECT
            row_number() OVER (ORDER BY code_module, code_presentation) AS course_key,
            code_module, code_presentation, module_presentation_length
        FROM read_parquet('{_glob("courses")}')
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE dim_student AS
        SELECT
            row_number() OVER (ORDER BY si.code_module, si.code_presentation, si.id_student) AS student_key,
            si.id_student, si.code_module, si.code_presentation,
            si.gender, si.region, si.highest_education, si.imd_band, si.age_band,
            si.num_of_prev_attempts, si.studied_credits, si.disability, si.final_result,
            sr.date_registration, sr.date_unregistration
        FROM read_parquet('{_glob("student_info")}') si
        LEFT JOIN read_parquet('{_glob("student_registration")}') sr
            ON si.code_module = sr.code_module
           AND si.code_presentation = sr.code_presentation
           AND si.id_student = sr.id_student
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE dim_assessment AS
        SELECT
            row_number() OVER (ORDER BY id_assessment) AS assessment_key,
            id_assessment, code_module, code_presentation, assessment_type, date, weight
        FROM read_parquet('{_glob("assessments")}')
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE fact_assessment_submission AS
        SELECT
            ds.student_key, da.assessment_key,
            sa.date_submitted, sa.is_banked, sa.score
        FROM read_parquet('{_glob("student_assessment")}') sa
        JOIN dim_assessment da ON da.id_assessment = sa.id_assessment
        JOIN dim_student ds
            ON ds.id_student = sa.id_student
           AND ds.code_module = da.code_module
           AND ds.code_presentation = da.code_presentation
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE fact_vle_interaction AS
        SELECT
            sv.id AS source_id,
            ds.student_key, dc.course_key,
            sv.id_site, v.activity_type,
            sv.date, sv.sum_click
        FROM read_parquet('{_glob("student_vle")}') sv
        JOIN dim_course dc
            ON dc.code_module = sv.code_module AND dc.code_presentation = sv.code_presentation
        JOIN dim_student ds
            ON ds.id_student = sv.id_student
           AND ds.code_module = sv.code_module
           AND ds.code_presentation = sv.code_presentation
        LEFT JOIN read_parquet('{_glob("vle")}') v ON v.id_site = sv.id_site
    """)

    for table in ["dim_course", "dim_student", "dim_assessment", "fact_assessment_submission", "fact_vle_interaction"]:
        con.execute(f"COPY {table} TO '{STAR_DIR / (table + '.parquet')}' (FORMAT parquet)")
        n = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        counts[table] = n
        progress(f"transformed {table}: {n} rows")

    con.close()
    progress(f"transform phase done in {time.time() - t0:.1f}s")
    return counts


if __name__ == "__main__":
    run_transform()
