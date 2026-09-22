"""Interactive dashboard for Software Heritage programming-language trends."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATA_DIR = Path("data")
LANGUAGE_COUNTS = DATA_DIR / "language_year_counts.csv"
EXTENSION_COUNTS = DATA_DIR / "extension_year_counts.csv"
METADATA = DATA_DIR / "build_metadata.json"
PAPER_REFERENCE = DATA_DIR / "paper_reference_top10.csv"

st.set_page_config(page_title="Software Heritage Language Trends", layout="wide")


@st.cache_data
def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


@st.cache_data
def load_metadata() -> dict:
    if METADATA.exists():
        return json.loads(METADATA.read_text(encoding="utf-8"))
    return {}


def data_status(metadata: dict) -> None:
    if not metadata:
        st.info(
            "No 2026 aggregate has been built yet. Run `python build_counts.py --max-shards 3` "
            "for a quick sample or `--max-shards 0` for the full export."
        )
        return
    if metadata.get("partial"):
        st.warning(
            f"Partial 2026 sample: {metadata.get('targeted_shards', '?')} of "
            f"{metadata.get('total_shards', '?')} Parquet shards. Trends are exploratory, "
            "not full-dataset results."
        )
    else:
        st.success(
            f"Full aggregate built from the {metadata.get('dataset_export', '2026-06-04')} export."
        )


def add_metric_columns(df: pd.DataFrame, group_key: str) -> pd.DataFrame:
    out = df.copy()
    out["year"] = pd.to_numeric(out["year"], errors="coerce").astype("Int64")
    out["count"] = pd.to_numeric(out["count"], errors="coerce").fillna(0)
    out = out.dropna(subset=["year", group_key])
    out["year"] = out["year"].astype(int)
    out = out.sort_values([group_key, "year"])
    out["cumulative_count"] = out.groupby(group_key)["count"].cumsum()
    return out


def language_dashboard(df: pd.DataFrame) -> None:
    st.subheader("Programming-language trends")
    st.caption(
        "Interactive version of the paper's language-level views: yearly share, yearly count, "
        "and cumulative count."
    )

    types = sorted(df["type"].dropna().unique().tolist())
    selected_types = st.multiselect(
        "Language types", types, default=[t for t in ["programming", "markup", "data"] if t in types]
    )
    filtered_type = df[df["type"].isin(selected_types)].copy()

    if filtered_type.empty:
        st.warning("Select at least one language type.")
        return

    year_min = int(filtered_type["year"].min())
    year_max = int(filtered_type["year"].max())
    default_start = max(2000, year_min)
    default_end = min(2023, year_max)
    years = st.slider(
        "Year range", year_min, year_max, (default_start, max(default_start, default_end))
    )
    window = filtered_type[filtered_type["year"].between(*years)].copy()

    totals = (
        window.groupby("language", as_index=False)["count"]
        .sum()
        .sort_values("count", ascending=False)
    )
    default_languages = totals.head(10)["language"].tolist()
    languages = st.multiselect(
        "Languages", totals["language"].tolist(), default=default_languages
    )
    if not languages:
        st.warning("Select at least one language.")
        return

    metric = st.radio(
        "View",
        ["Share of yearly activity", "Annual file count", "Cumulative file count"],
        horizontal=True,
    )

    # The share denominator is all languages in the selected types, not only the
    # displayed languages. This avoids renormalizing a top-N selection to 100%.
    year_totals = window.groupby("year", as_index=False)["count"].sum().rename(
        columns={"count": "year_total"}
    )
    selected = window[window["language"].isin(languages)].merge(year_totals, on="year")
    selected["share"] = selected["count"] / selected["year_total"] * 100
    selected = add_metric_columns(selected, "language")

    if metric == "Share of yearly activity":
        fig = px.area(
            selected,
            x="year",
            y="share",
            color="language",
            labels={"share": "Share of activity (%)", "year": "Year", "language": "Language"},
        )
        fig.update_yaxes(rangemode="tozero")
    elif metric == "Annual file count":
        log_y = st.checkbox("Log scale", value=False, key="lang_annual_log")
        fig = px.line(
            selected,
            x="year",
            y="count",
            color="language",
            markers=True,
            log_y=log_y,
            labels={"count": "Unique contents first seen", "year": "Year", "language": "Language"},
        )
    else:
        log_y = st.checkbox("Log scale", value=False, key="lang_cumulative_log")
        fig = px.line(
            selected,
            x="year",
            y="cumulative_count",
            color="language",
            markers=True,
            log_y=log_y,
            labels={
                "cumulative_count": "Cumulative unique contents",
                "year": "Year",
                "language": "Language",
            },
        )

    fig.update_layout(legend_title_text="Language", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        selected[["year", "language", "type", "count", "share", "cumulative_count"]]
        .sort_values(["year", "count"], ascending=[False, False]),
        use_container_width=True,
        hide_index=True,
    )


def extension_dashboard(df: pd.DataFrame) -> None:
    st.subheader("File-extension trends")
    st.caption("This is the direct extension-level step corresponding to Figures 4 and 5 in the paper.")

    year_min = int(df["year"].min())
    year_max = int(df["year"].max())
    default_start = max(2000, year_min)
    default_end = min(2023, year_max)
    years = st.slider(
        "Year range", year_min, year_max, (default_start, max(default_start, default_end)), key="ext_years"
    )
    window = df[df["year"].between(*years)].copy()
    top_n = st.slider("Top extensions", 5, 25, 10)
    top_extensions = (
        window.groupby("extension", as_index=False)["count"].sum().nlargest(top_n, "count")["extension"]
    )
    selected = window[window["extension"].isin(top_extensions)].copy()

    metric = st.radio(
        "View",
        ["Share of yearly activity", "Annual file count"],
        horizontal=True,
        key="ext_metric",
    )
    year_totals = window.groupby("year", as_index=False)["count"].sum().rename(
        columns={"count": "year_total"}
    )
    selected = selected.merge(year_totals, on="year")
    selected["share"] = selected["count"] / selected["year_total"] * 100

    if metric == "Share of yearly activity":
        fig = px.area(selected, x="year", y="share", color="extension")
        fig.update_yaxes(title="Share of activity (%)", rangemode="tozero")
    else:
        log_y = st.checkbox("Log scale", value=True, key="ext_log")
        fig = px.line(selected, x="year", y="count", color="extension", markers=True, log_y=log_y)
        fig.update_yaxes(title="Unique contents first seen")

    fig.update_layout(hovermode="x unified", legend_title_text="Extension")
    st.plotly_chart(fig, use_container_width=True)


def validation_view(current: pd.DataFrame | None) -> None:
    st.subheader("Paper reference / validation")
    reference = load_csv(PAPER_REFERENCE)
    st.caption(
        "The MSR 2025 paper prints selected years for its top ten languages in Table II. "
        "These values provide a concrete reference check; the 2026 export is expected to differ because the archive was updated."
    )

    if current is None or current.empty:
        st.dataframe(reference, use_container_width=True, hide_index=True)
        return

    current = current[current["language"].isin(reference["language"].unique())]
    merged = reference.merge(current, on=["language", "type", "year"], how="left", suffixes=("_paper", "_2026"))
    merged["difference"] = merged["count_2026"] - merged["count_paper"]
    st.dataframe(merged, use_container_width=True, hide_index=True)


st.title("Software Heritage Programming Language Explorer")
st.write(
    "A first-pass interactive reproduction of the MSR 2025 programming-language evolution analysis, "
    "using the updated Software Heritage Aggregated Contents export."
)

metadata = load_metadata()
data_status(metadata)

if LANGUAGE_COUNTS.exists() and EXTENSION_COUNTS.exists():
    languages_df = add_metric_columns(load_csv(LANGUAGE_COUNTS), "language")
    extensions_df = load_csv(EXTENSION_COUNTS)

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Language trends", "Extension trends", "Validation", "Method"]
    )
    with tab1:
        language_dashboard(languages_df)
    with tab2:
        extension_dashboard(extensions_df)
    with tab3:
        validation_view(languages_df)
    with tab4:
        st.markdown(
            """
            **Pipeline**

            `Aggregated Contents Parquet → filename extension → year of first occurrence → extension/year counts → GitHub Linguist mapping → language/year counts → interactive views`

            The dashboard counts each unique Software Heritage content row once, matching the paper's first-occurrence activity idea. It does **not** weight rows by `filename_occurrences`.

            **Important limitations**

            - A filename extension is only a proxy for programming language.
            - Ambiguous extensions can map to multiple languages; unresolved cases are skipped rather than guessed.
            - Recent years may be incomplete because Software Heritage crawling lags newly created projects.
            - A partial shard run is an exploratory sample, not a population estimate.
            """
        )
else:
    tab1, tab2 = st.tabs(["Paper reference", "How to build 2026 data"])
    with tab1:
        validation_view(None)
    with tab2:
        st.code(
            "pip install -r requirements.txt\n"
            "python build_counts.py --max-shards 3\n"
            "streamlit run app.py",
            language="bash",
        )
