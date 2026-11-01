"""One-time loader: OULAD CSVs (data/raw/oulad/) -> PostgreSQL (OLTP source).

Run once after scripts/download_data.py. Not part of the pipeline's Extract
phase -- the pipeline always extracts FROM Postgres, this script is what gets
Postgres populated in the first place.
"""
import csv
import io
import os
import sys
import time
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "oulad"
SCHEMA_SQL = ROOT / "scripts" / "schema.sql"

DSN = os.environ["POSTGRES_DSN"]

# (csv filename, table name, column list in CSV order)
SIMPLE_TABLES = [
    ("courses.csv", "courses", ["code_module", "code_presentation", "module_presentation_length"]),
    ("assessments.csv", "assessments", ["code_module", "code_presentation", "id_assessment", "assessment_type", "date", "weight"]),
    ("vle.csv", "vle", ["id_site", "code_module", "code_presentation", "activity_type", "week_from", "week_to"]),
    ("studentInfo.csv", "student_info", ["code_module", "code_presentation", "id_student", "gender", "region", "highest_education", "imd_band", "age_band", "num_of_prev_attempts", "studied_credits", "disability", "final_result"]),
    ("studentRegistration.csv", "student_registration", ["code_module", "code_presentation", "id_student", "date_registration", "date_unregistration"]),
    ("studentAssessment.csv", "student_assessment", ["id_assessment", "id_student", "date_submitted", "is_banked", "score"]),
]

# Loaded separately: has a surrogate id column not present in the CSV.
STUDENT_VLE_COLUMNS = ["code_module", "code_presentation", "id_student", "id_site", "date", "sum_click"]


def apply_schema(conn):
    with conn.cursor() as cur:
        cur.execute(SCHEMA_SQL.read_text())
    conn.commit()
    print("schema applied")


def copy_csv(conn, csv_path: Path, table: str, columns: list[str]):
    """Stream the CSV into Postgres via COPY, rewriting the OULAD '?' missing-value
    marker to an unquoted empty field (COPY's NULL marker) along the way -- COPY's
    own NULL option only matches *unquoted* fields, and every field in these CSVs
    is quoted, so '?' has to be cleaned before it reaches COPY."""
    cols = ", ".join(columns)
    sql = f"COPY {table} ({cols}) FROM STDIN WITH (FORMAT csv, HEADER false, NULL '')"
    t0 = time.time()

    buf = io.StringIO()
    writer = csv.writer(buf)
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader)  # header
        for row in reader:
            writer.writerow("" if v == "?" else v for v in row)
    buf.seek(0)

    with conn.cursor() as cur:
        cur.copy_expert(sql, buf)
    conn.commit()
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {table}")
        n = cur.fetchone()[0]
    print(f"{table}: loaded {n} rows in {time.time() - t0:.1f}s")


def create_student_vle_indexes(conn):
    t0 = time.time()
    with conn.cursor() as cur:
        cur.execute("CREATE INDEX idx_student_vle_student ON student_vle (id_student)")
        cur.execute("CREATE INDEX idx_student_vle_site ON student_vle (id_site)")
        cur.execute("CREATE INDEX idx_student_vle_course ON student_vle (code_module, code_presentation)")
        cur.execute("CREATE INDEX idx_student_vle_date ON student_vle (date)")
    conn.commit()
    print(f"student_vle indexes built in {time.time() - t0:.1f}s")


def main():
    if not RAW_DIR.exists():
        sys.exit(f"missing {RAW_DIR} -- run scripts/download_data.py first")

    conn = psycopg2.connect(DSN)
    try:
        apply_schema(conn)
        for csv_name, table, columns in SIMPLE_TABLES:
            copy_csv(conn, RAW_DIR / csv_name, table, columns)
        copy_csv(conn, RAW_DIR / "studentVle.csv", "student_vle", STUDENT_VLE_COLUMNS)
        create_student_vle_indexes(conn)
    finally:
        conn.close()
    print("done")


if __name__ == "__main__":
    main()
