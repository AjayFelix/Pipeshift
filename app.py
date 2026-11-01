"""DMT -- Postgres (OLTP) -> MotherDuck (OLAP) migration tool.

Streamlit dashboard: pipeline control, star-schema browser, ad-hoc SQL, and
the scaled Postgres-vs-MotherDuck benchmark panel.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import plotly.express as px
import streamlit as st

from dmt.extract import run_extract
from dmt.transform import run_transform
from dmt.load import run_load, motherduck_connect, STAR_TABLES
from dmt.benchmark import run_benchmark, DEFAULT_SLICES

st.set_page_config(page_title="DMT: OLTP -> OLAP Migration", layout="wide")
st.title("DMT -- PostgreSQL to MotherDuck")
st.caption("OULAD dataset: small OLTP source, cloud-native OLAP target.")

page = st.sidebar.radio("Panel", ["Pipeline", "Table Browser", "Ad-hoc SQL", "Benchmark"])


def _run_with_log(label, fn):
    log_box = st.empty()
    lines = []

    def progress(msg):
        lines.append(msg)
        log_box.code("\n".join(lines))

    with st.spinner(label):
        result = fn(progress=progress)
    st.success(f"{label} complete")
    return result


if page == "Pipeline":
    st.header("Pipeline control")
    col1, col2, col3, col4 = st.columns(4)

    if col1.button("Run Extract"):
        counts = _run_with_log("Extract: Postgres -> Parquet", run_extract)
        st.json(counts)

    if col2.button("Run Transform"):
        counts = _run_with_log("Transform: Parquet -> star schema", run_transform)
        st.json(counts)

    if col3.button("Run Load"):
        try:
            counts = _run_with_log("Load: star schema -> MotherDuck", run_load)
            st.json(counts)
        except RuntimeError as e:
            st.error(str(e))

    if col4.button("Run Full Pipeline", type="primary"):
        st.subheader("Extract")
        e = _run_with_log("Extract", run_extract)
        st.subheader("Transform")
        t = _run_with_log("Transform", run_transform)
        st.subheader("Load")
        try:
            l = _run_with_log("Load", run_load)
            st.json({"extract": e, "transform": t, "load": l})
        except RuntimeError as err:
            st.error(str(err))

elif page == "Table Browser":
    st.header("Star schema (MotherDuck)")
    try:
        con = motherduck_connect()
        counts = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in STAR_TABLES}
        st.dataframe(pd.DataFrame(counts.items(), columns=["table", "rows"]), use_container_width=True)

        table = st.selectbox("Preview a table", STAR_TABLES)
        n = st.slider("Rows to preview", 10, 1000, 100)
        df = con.execute(f"SELECT * FROM {table} LIMIT {n}").fetchdf()
        st.dataframe(df, use_container_width=True)
        con.close()
    except RuntimeError as e:
        st.error(str(e))

elif page == "Ad-hoc SQL":
    st.header("Ad-hoc SQL against MotherDuck")
    sql = st.text_area("SQL", "SELECT * FROM fact_vle_interaction LIMIT 20", height=120)
    if st.button("Run query"):
        try:
            con = motherduck_connect()
            df = con.execute(sql).fetchdf()
            con.close()
            st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(str(e))

elif page == "Benchmark":
    st.header("Postgres vs. MotherDuck: scaled benchmark")
    st.markdown(
        "Same query shape (group-by + AVG + COUNT over the VLE click data), "
        "run against both engines at increasing row-count slices, selecting "
        "the **same underlying rows** on both sides via the original row id. "
        "Postgres uses only its standard OLTP indexes -- nothing added to "
        "specifically speed up this query."
    )
    repeats = st.slider("Repeats per slice (median is plotted)", 1, 5, 3)

    if st.button("Run benchmark", type="primary"):
        try:
            df = run_benchmark(slices=DEFAULT_SLICES, repeats=repeats, progress=st.write)
            st.session_state["benchmark_df"] = df
        except RuntimeError as e:
            st.error(str(e))

    df = st.session_state.get("benchmark_df")
    if df is not None:
        summary = df.groupby(["engine", "rows"], as_index=False)["seconds"].median()
        fig = px.line(
            summary, x="rows", y="seconds", color="engine", markers=True,
            log_x=True, log_y=True,
            title="Query latency vs. row-count slice (median of repeats)",
            labels={"rows": "Rows aggregated", "seconds": "Latency (s)"},
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(summary, use_container_width=True)
