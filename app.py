"""Interactive dashboard for the MSR 2025 Software Heritage language-evolution study.

The app works immediately with published values from Table II of the paper.
If a 2026 aggregate has been built locally, the same views can be switched to
that updated Software Heritage data.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


# -------------------------------------------------------------------
# Paths
# -------------------------------------------------------------------

DATA_DIR = Path("data")

PAPER_REFERENCE = DATA_DIR / "paper_reference_top10.csv"
LANGUAGE_COUNTS = DATA_DIR / "language_year_counts.csv"
EXTENSION_COUNTS = DATA_DIR / "extension_year_counts.csv"
METADATA = DATA_DIR / "build_metadata.json"


# -------------------------------------------------------------------
# Languages emphasized in the MSR 2025 paper
# -------------------------------------------------------------------

PAPER_LANGUAGES = [
    "JavaScript",
    "Java",
    "Python",
    "C",
    "C++",
    "PHP",
    "C#",
    "HTML",
    "XML",
    "JSON",
]


st.set_page_config(
    page_title="Software Heritage Language Trends",
    layout="wide",
)


# -------------------------------------------------------------------
# Data loading
# -------------------------------------------------------------------

@st.cache_data
def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


@st.cache_data
def load_metadata() -> dict:
    if METADATA.exists():
        return json.loads(
            METADATA.read_text(encoding="utf-8")
        )

    return {}


def prep_language_data(df: pd.DataFrame) -> pd.DataFrame:

    out = df.copy()

    out["year"] = pd.to_numeric(
        out["year"],
        errors="coerce",
    )

    out["count"] = pd.to_numeric(
        out["count"],
        errors="coerce",
    )

    out = out.dropna(
        subset=[
            "year",
            "count",
            "language",
            "type",
        ]
    )

    out["year"] = out["year"].astype(int)
    out["count"] = out["count"].astype(float)

    return out.sort_values(
        ["year", "language"]
    )


def preferred_languages(
    df: pd.DataFrame,
) -> list[str]:

    available = set(
        df["language"].dropna().unique()
    )

    preferred = [
        language
        for language in PAPER_LANGUAGES
        if language in available
    ]

    return preferred


# -------------------------------------------------------------------
# Explore
# -------------------------------------------------------------------

def language_trends(
    df: pd.DataFrame,
    paper_mode: bool,
) -> None:

    st.subheader("Language trends")

    if paper_mode:

        st.caption(
            "Published Table II values for the paper's top 10 "
            "languages. The table reports selected years "
            "(2000–2003 and 2018–2021)."
        )

    else:

        st.caption(
            "Language/year counts generated from the updated "
            "2026 Software Heritage Aggregated Contents export."
        )

    # ---------------------------------------------------------------
    # Language type
    # ---------------------------------------------------------------

    types = sorted(
        df["type"].dropna().unique()
    )

    selected_types = st.multiselect(
        "Language type",
        types,
        default=[
            x
            for x in [
                "programming",
                "markup",
                "data",
            ]
            if x in types
        ],
    )

    base = df[
        df["type"].isin(selected_types)
    ].copy()

    if base.empty:

        st.warning(
            "Select at least one language type."
        )

        return

    # ---------------------------------------------------------------
    # Language ordering
    # ---------------------------------------------------------------

    totals = (
        base.groupby(
            "language",
            as_index=False,
        )["count"]
        .sum()
        .sort_values(
            "count",
            ascending=False,
        )
    )

    available_languages = (
        totals["language"].tolist()
    )

    paper_available = [
        language
        for language in PAPER_LANGUAGES
        if language in available_languages
    ]

    other_languages = [
        language
        for language in available_languages
        if language not in paper_available
    ]

    language_options = (
        paper_available
        + other_languages
    )

    # Use paper languages by default.
    # If none exist, fall back to highest-count languages.
    if paper_available:

        default_languages = paper_available

    else:

        default_languages = (
            totals.head(6)["language"].tolist()
        )

    languages = st.multiselect(
        "Languages",
        language_options,
        default=default_languages,
    )

    if not languages:

        st.warning(
            "Select at least one language."
        )

        return

    selected = base[
        base["language"].isin(languages)
    ].copy()

    # ---------------------------------------------------------------
    # Metric
    # ---------------------------------------------------------------

    metric = st.radio(
        "Measure",
        [
            "Annual file count",
            "Share of language activity",
        ],
        horizontal=True,
    )

    if metric == "Annual file count":

        log_y = st.checkbox(
            "Log scale",
            value=True,
        )

        fig = px.line(
            selected,
            x="year",
            y="count",
            color="language",
            markers=True,
            log_y=log_y,
            labels={
                "count":
                    "Unique file contents first seen",
                "year":
                    "Year",
                "language":
                    "Language",
            },
        )

    else:

        # Important:
        # denominator uses ALL languages in the currently selected
        # language types, not just the languages visible on screen.

        yearly_totals = (
            base.groupby(
                "year",
                as_index=False,
            )["count"]
            .sum()
            .rename(
                columns={
                    "count": "year_total"
                }
            )
        )

        selected = selected.merge(
            yearly_totals,
            on="year",
            how="left",
        )

        selected["share"] = (
            selected["count"]
            / selected["year_total"]
            * 100
        )

        fig = px.line(
            selected,
            x="year",
            y="share",
            color="language",
            markers=True,
            labels={
                "share":
                    "Share of activity (%)",
                "year":
                    "Year",
                "language":
                    "Language",
            },
        )

        fig.update_yaxes(
            rangemode="tozero"
        )

    fig.update_layout(
        hovermode="x unified",
        legend_title_text="Language",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    if paper_mode:

        st.caption(
            "The paper publishes values for selected years only. "
            "The gap between 2003 and 2018 does not mean there was "
            "no activity during those years."
        )


# -------------------------------------------------------------------
# Compare
# -------------------------------------------------------------------

def ranking_view(
    df: pd.DataFrame,
) -> None:

    st.subheader("Compare languages")

    paper_languages_available = (
        preferred_languages(df)
    )

    if paper_languages_available:

        compare_df = df[
            df["language"].isin(
                paper_languages_available
            )
        ].copy()

    else:

        compare_df = df.copy()

    years = sorted(
        compare_df["year"]
        .unique()
        .tolist()
    )

    if not years:

        st.warning(
            "No data available for comparison."
        )

        return

    selected_year = st.select_slider(
        "Year",
        options=years,
        value=years[-1],
    )

    year_df = (
        compare_df[
            compare_df["year"]
            == selected_year
        ]
        .sort_values(
            "count",
            ascending=True,
        )
    )

    st.markdown(
        f"### Language activity in {selected_year}"
    )

    if year_df.empty:

        st.info(
            "No paper languages are present "
            "for this year."
        )

    else:

        fig = px.bar(
            year_df,
            x="count",
            y="language",
            orientation="h",
            color="type",
            labels={
                "count":
                    "Unique file contents first seen",
                "language":
                    "Language",
                "type":
                    "Type",
            },
        )

        fig.update_layout(
            yaxis_title=None,
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    # ---------------------------------------------------------------
    # 2018 → 2021 comparison
    # ---------------------------------------------------------------

    if (
        2018 in years
        and 2021 in years
    ):

        start = (
            compare_df[
                compare_df["year"] == 2018
            ][
                ["language", "count"]
            ]
            .rename(
                columns={
                    "count": "count_2018"
                }
            )
        )

        end = (
            compare_df[
                compare_df["year"] == 2021
            ][
                ["language", "count"]
            ]
            .rename(
                columns={
                    "count": "count_2021"
                }
            )
        )

        change = start.merge(
            end,
            on="language",
        )

        change["change"] = (
            change["count_2021"]
            - change["count_2018"]
        )

        change["percent_change"] = (
            change["change"]
            / change["count_2018"]
            * 100
        )

        # Follow paper language order
        order_map = {
            language: index
            for index, language
            in enumerate(PAPER_LANGUAGES)
        }

        change["order"] = (
            change["language"]
            .map(order_map)
            .fillna(999)
        )

        change = (
            change.sort_values("order")
            .drop(columns="order")
        )

        st.markdown(
            "### 2018 → 2021 change"
        )

        st.dataframe(
            change,
            use_container_width=True,
            hide_index=True,
            column_config={

                "language":
                    "Language",

                "count_2018":
                    st.column_config.NumberColumn(
                        "2018",
                        format="%,.0f",
                    ),

                "count_2021":
                    st.column_config.NumberColumn(
                        "2021",
                        format="%,.0f",
                    ),

                "change":
                    st.column_config.NumberColumn(
                        "Change",
                        format="%+,.0f",
                    ),

                "percent_change":
                    st.column_config.NumberColumn(
                        "% change",
                        format="%+.1f%%",
                    ),
            },
        )


# -------------------------------------------------------------------
# Extension-level data
# -------------------------------------------------------------------

def extension_view(
    df: pd.DataFrame,
) -> None:

    st.subheader(
        "Extension trends"
    )

    st.caption(
        "This is the extension → year stage "
        "used before extensions are mapped "
        "to programming languages."
    )

    years = sorted(
        df["year"]
        .dropna()
        .unique()
        .tolist()
    )

    if not years:

        return

    start, end = st.select_slider(
        "Year range",
        options=years,
        value=(
            years[0],
            years[-1],
        ),
    )

    window = df[
        df["year"].between(
            start,
            end,
        )
    ].copy()

    top_n = st.slider(
        "Top extensions",
        5,
        20,
        10,
    )

    top = (
        window.groupby(
            "extension"
        )["count"]
        .sum()
        .nlargest(top_n)
        .index
    )

    selected = window[
        window["extension"].isin(top)
    ]

    fig = px.line(
        selected,
        x="year",
        y="count",
        color="extension",
        markers=True,
        log_y=True,
        labels={
            "year":
                "Year",
            "count":
                "Unique file contents first seen",
            "extension":
                "Extension",
        },
    )

    fig.update_layout(
        hovermode="x unified"
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


# -------------------------------------------------------------------
# Header
# -------------------------------------------------------------------

st.title(
    "Software Heritage Programming Language Explorer"
)

st.write(
    "Explore programming-language evolution using the "
    "MSR 2025 Software Heritage study and the updated "
    "2026 Aggregated Contents dataset."
)


# -------------------------------------------------------------------
# Sources
# -------------------------------------------------------------------

paper_df = prep_language_data(
    load_csv(PAPER_REFERENCE)
)

has_2026 = (
    LANGUAGE_COUNTS.exists()
)


sources = [
    "MSR 2025 paper — published values"
]

if has_2026:

    sources.append(
        "Software Heritage 2026 — local aggregate"
    )


source = st.selectbox(
    "Data source",
    sources,
)


paper_mode = source.startswith(
    "MSR 2025"
)


# -------------------------------------------------------------------
# Current dataset
# -------------------------------------------------------------------

if paper_mode:

    current = paper_df

    st.info(
        "Published values from Table II of the "
        "MSR 2025 paper."
    )

else:

    current = prep_language_data(
        load_csv(LANGUAGE_COUNTS)
    )

    metadata = load_metadata()

    if metadata.get("partial"):

        rows = metadata.get(
            "rows_per_shard"
        )

        targeted = metadata.get(
            "targeted_shards",
            "?",
        )

        total = metadata.get(
            "total_shards",
            "?",
        )

        row_note = ""

        if (
            isinstance(rows, int)
            and rows > 0
        ):

            row_note = (
                f", up to {rows:,} "
                "rows per shard"
            )

        st.warning(
            f"Exploratory 2026 sample: "
            f"{targeted} of {total} shards"
            f"{row_note}. "
            "Use this to test the pipeline, "
            "not as a population-level estimate."
        )

    else:

        st.success(
            "Full locally generated "
            "2026 aggregate."
        )


# -------------------------------------------------------------------
# Tabs
# -------------------------------------------------------------------

trend_tab, compare_tab, data_tab, method_tab = (
    st.tabs(
        [
            "Explore",
            "Compare",
            "Data",
            "Method",
        ]
    )
)


with trend_tab:

    language_trends(
        current,
        paper_mode=paper_mode,
    )


with compare_tab:

    ranking_view(
        current
    )


with data_tab:

    st.subheader(
        "Language/year data"
    )

    display_data = current.copy()

    paper_available = (
        preferred_languages(
            display_data
        )
    )

    if paper_available:

        only_paper = st.checkbox(
            "Show paper languages only",
            value=True,
        )

        if only_paper:

            display_data = display_data[
                display_data[
                    "language"
                ].isin(
                    paper_available
                )
            ]

    st.dataframe(
        display_data.sort_values(
            ["year", "count"],
            ascending=[
                False,
                False,
            ],
        ),
        use_container_width=True,
        hide_index=True,
    )

    if (
        not paper_mode
        and EXTENSION_COUNTS.exists()
    ):

        st.divider()

        extension_view(
            load_csv(
                EXTENSION_COUNTS
            )
        )


with method_tab:

    st.markdown(
        """
### Analysis pipeline

`Aggregated Contents`

↓

`most popular filename`

↓

`file extension`

↓

`first-occurrence year`

↓

`extension/year counts`

↓

`GitHub Linguist language mapping`

↓

`language/year counts`

↓

`interactive visualizations`

### Dashboard purpose

The MSR 2025 paper presents programming-language
evolution through fixed figures.

This dashboard makes those results explorable by
allowing the user to:

- select programming languages
- separate programming, markup and data languages
- compare annual activity
- compare relative language share
- inspect individual years
- compare changes between years
- explore updated Software Heritage data using the
  same general analysis pipeline

The 2026 sample mode is intended to validate that the
updated Aggregated Contents data can pass through the
pipeline successfully before processing the complete
dataset.
"""
    )


# -------------------------------------------------------------------
# 2026 build instructions
# -------------------------------------------------------------------

if not has_2026:

    with st.expander(
        "Build updated 2026 data"
    ):

        st.code(
            "python build_counts.py "
            "--max-shards 0 "
            "--rows-per-shard 100000",
            language="bash",
        )

        st.caption(
            "This samples rows across all available "
            "Parquet shards rather than relying on "
            "a single shard."
        )