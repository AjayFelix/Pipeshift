# DMT — PostgreSQL to MotherDuck Migration Tool

Migrates the OULAD (Open University Learning Analytics Dataset) from
PostgreSQL (OLTP) into MotherDuck (serverless cloud OLAP), and demonstrates
*why*: a scaled benchmark panel runs the same analytical query against both
engines at increasing row counts. Postgres wins at small scale; MotherDuck
overtakes it once the data gets large — which is the whole point.

## Prerequisites

- Python 3.10+
- PostgreSQL running locally (`pg_isready` should say "accepting connections")
- A free [MotherDuck](https://motherduck.com) account — sign up, then grab a
  service token from **Settings -> Tokens**

## 1. Set up the environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

```bash
cp .env.example .env
```

Open `.env` and fill in `MOTHERDUCK_TOKEN` with the token from your MotherDuck
account. `POSTGRES_DSN` and `MOTHERDUCK_DB` already have working defaults.

## 2. Create the Postgres database

```bash
createdb dmt
```

(The target MotherDuck database doesn't need to be created manually — the
Load phase creates it automatically on first connect.)

## 3. Get the data in

```bash
python3 scripts/download_data.py   # one-time: fetches OULAD, no login needed (44MB)
python3 scripts/load_source.py     # one-time: loads the 7 CSVs into Postgres (~40s)
```

`load_source.py` applies the schema (`scripts/schema.sql`) and bulk-loads via
`COPY`, including the ~10.6M-row `student_vle` table. You should see row
counts for all 7 tables printed, ending in `done`.

## 4. Run it

```bash
streamlit run app.py
```

This opens the dashboard with four panels:

- **Pipeline** — buttons to run Extract / Transform / Load individually, or
  the full pipeline in one go, with a live log of progress.
- **Table Browser** — row counts and a preview of each star-schema table, read
  live from MotherDuck.
- **Ad-hoc SQL** — run any query against MotherDuck and see the result.
- **Benchmark** — the centerpiece. Runs the same query against Postgres and
  MotherDuck at 100K / 1M / and the full ~10.6M row slice, and plots latency
  for both. Takes about 10-15 seconds.

First time through, use the **Pipeline** panel and click **Run Full
Pipeline** (or run the command below) before using the other three panels —
they all read from MotherDuck, which is only populated after the Load phase.

### Running the pipeline from the command line instead

```bash
PYTHONPATH=src python3 -m dmt.pipeline   # extract -> transform -> load, in order
```

Or one phase at a time: `python3 -m dmt.extract`, `dmt.transform`, `dmt.load`
(same `PYTHONPATH=src` prefix).

## Architecture

```
OULAD zip -> PostgreSQL (OLTP, 7 normalized tables)
          -> Extract  (chunked, Postgres -> Parquet staging)
          -> Transform (DuckDB, Parquet -> star schema)
          -> Load     (star schema Parquet -> MotherDuck)
          -> Streamlit dashboard (pipeline control, browser, SQL, benchmark)
```

Star schema: `dim_course`, `dim_student`, `dim_assessment`,
`fact_assessment_submission`, `fact_vle_interaction` (the large fact table,
10.6M rows, ~33MB as Parquet).

## What a working run looks like

```
$ python3 scripts/load_source.py
...
student_vle: loaded 10655280 rows in 23.5s
student_vle indexes built in 10.0s
done

$ PYTHONPATH=src python3 -m dmt.benchmark
postgres   n=    100000: median 0.027s over 3 runs
motherduck n=    100000: median 0.218s over 3 runs
postgres   n=   1000000: median 0.181s over 3 runs
motherduck n=   1000000: median 0.452s over 3 runs
postgres   n=  10655280: median 2.068s over 3 runs
motherduck n=  10655280: median 1.268s over 3 runs
```

Postgres is faster at small scale (lower per-query overhead); MotherDuck
overtakes it at full scale, which is the result the project is built to show.
Exact numbers vary run to run but the crossover pattern should hold.

## Tests

```bash
python3 -m pytest tests/
```

Checks that every pipeline stage preserves row counts end to end (no silent
row loss through the extract/transform joins).

## Troubleshooting

- **`psycopg2.errors.InvalidTextRepresentation` on load** — shouldn't happen;
  `load_source.py` already cleans the OULAD `?` missing-value marker before
  it reaches Postgres's `COPY`.
- **`MOTHERDUCK_TOKEN is not set`** — check `.env` has the token filled in
  and you're running commands from the project root (`python-dotenv` loads
  `.env` from the current working directory).
- **Load phase looks stuck on `fact_vle_interaction`** — it's uploading
  ~10.6M rows to MotherDuck; on the free tier this took about 7 minutes in
  testing. Everything else loads in a few seconds.
