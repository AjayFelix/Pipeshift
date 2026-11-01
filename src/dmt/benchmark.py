"""Scaled OLTP-vs-OLAP benchmark: the project's centerpiece.

Runs the *same shape* of analytical query (group-by + AVG + COUNT over a
row-count slice of the VLE interaction data) against Postgres (OLTP, raw
student_vle table) and MotherDuck (OLAP, fact_vle_interaction star table),
at increasing slice sizes, and times both. Both sides select their slice by
ORDER BY <the same original row id> LIMIT n, so both engines are aggregating
the exact same underlying rows at each size -- not just "n rows each".

Fair-comparison rule (see design doc): Postgres uses only the realistic OLTP
indexes already on student_vle (id/PK, id_student, id_site, course, date) --
nothing added specifically to speed up this query.
"""
import statistics
import time

import pandas as pd
from sqlalchemy import create_engine, text

from dmt.config import POSTGRES_DSN
from dmt.load import motherduck_connect

DEFAULT_SLICES = [100_000, 1_000_000, 10_655_280]
REPEATS = 3

POSTGRES_QUERY = """
    WITH slice AS (
        SELECT * FROM student_vle ORDER BY id LIMIT :n
    )
    SELECT code_module, code_presentation, id_student,
           AVG(sum_click) AS avg_clicks, COUNT(*) AS n_events
    FROM slice
    GROUP BY code_module, code_presentation, id_student
    ORDER BY avg_clicks DESC
"""

MOTHERDUCK_QUERY = """
    WITH slice AS (
        SELECT * FROM fact_vle_interaction ORDER BY source_id LIMIT {n}
    )
    SELECT student_key, course_key,
           AVG(sum_click) AS avg_clicks, COUNT(*) AS n_events
    FROM slice
    GROUP BY student_key, course_key
    ORDER BY avg_clicks DESC
"""


def _time_postgres(engine, n: int, repeats: int) -> list[float]:
    times = []
    with engine.connect() as conn:
        for _ in range(repeats):
            t0 = time.perf_counter()
            conn.execute(text(POSTGRES_QUERY), {"n": n}).fetchall()
            times.append(time.perf_counter() - t0)
    return times


def _time_motherduck(con, n: int, repeats: int) -> list[float]:
    times = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        con.execute(MOTHERDUCK_QUERY.format(n=n)).fetchall()
        times.append(time.perf_counter() - t0)
    return times


def run_benchmark(slices=None, repeats: int = REPEATS, progress=print) -> pd.DataFrame:
    slices = slices or DEFAULT_SLICES
    engine = create_engine(POSTGRES_DSN)
    con = motherduck_connect()
    rows = []
    try:
        for n in slices:
            pg_times = _time_postgres(engine, n, repeats)
            progress(f"postgres  n={n:>10}: median {statistics.median(pg_times):.3f}s over {repeats} runs")
            for t in pg_times:
                rows.append({"engine": "Postgres (OLTP)", "rows": n, "seconds": t})

            md_times = _time_motherduck(con, n, repeats)
            progress(f"motherduck n={n:>10}: median {statistics.median(md_times):.3f}s over {repeats} runs")
            for t in md_times:
                rows.append({"engine": "MotherDuck (OLAP)", "rows": n, "seconds": t})
    finally:
        engine.dispose()
        con.close()
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = run_benchmark()
    print(df.groupby(["engine", "rows"])["seconds"].median())
