# Software Heritage Programming Language Explorer

A small, reproducible dashboard built from Software Heritage's **Aggregated Contents** dataset. The goal is to turn results from Desmazières, Di Cosmo & Lorentz (MSR 2025), *50 Years of Programming Language Evolution through the Software Heritage looking glass*, into an interactive view using the updated `2026-06-04` Software Heritage export.

## What this adds to the original small demo

The original repository only inspected 20 rows from one Parquet shard. This version keeps that lightweight idea but adds the actual first-pass analysis pipeline and dashboard:

`Aggregated Contents → extension → year → extension/year counts → GitHub Linguist → language/year counts → interactive dashboard`

The dashboard includes:

- **Language trends**: share of yearly activity, annual counts, cumulative counts, optional log scale.
- **Extension trends**: the direct extension-level equivalent of the paper's Figures 4 and 5.
- **Paper validation**: selected Table II values for the paper's top ten languages, so the updated export can be compared against the published 2024-export results.
- **Run metadata**: clearly marks partial-shard demo runs versus a full dataset aggregation.

## Why this matches the paper

The paper first associates each unique file content with its most popular filename and first-occurrence timestamp, extracts the final filename extension, counts extensions by year, and then maps extensions to languages using GitHub Linguist. The resulting views correspond to:

- Figure 4: percentage of activity by file extension
- Figure 5: annual quantity by file extension
- Figure 6: percentage of activity by programming / markup / data language
- Figures 7–8: annual quantity by language (linear / log)
- Figures 9–10: cumulative quantity by language (linear / log)

This project uses the same basic sequence. It is a **first-pass reproduction**, not a claim of byte-for-byte equivalence with the authors' original pipeline: unresolved ambiguous extensions are skipped rather than guessed, except for a small explicit override set (including the paper's `.pl → Perl` example).

## Dataset

Updated Aggregated Contents export:

```text
s3://softwareheritage/derived_datasets/2026-06-04/contents/
```

Each row represents a unique content node and includes its most popular filename and first known occurrence timestamp. The analysis counts each row once; `filename_occurrences` is not used as a weight.

## Run a quick development sample

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python build_counts.py --max-shards 3
streamlit run app.py
```

The app will label this as a **partial sample**. It is useful for validating the pipeline and dashboard, but it should not be interpreted as a population estimate.

## Run the full aggregation

```bash
python build_counts.py --max-shards 0
streamlit run app.py
```

`--max-shards 0` processes every public Parquet shard. The dataset contains tens of billions of unique contents, so a full run can require substantial time and bandwidth. The script writes one small checkpoint CSV per shard under `data/shard_counts/`, so an interrupted run can be restarted without reprocessing completed shards.

To start over:

```bash
python build_counts.py --max-shards 3 --rebuild
```

## Output files

After `build_counts.py` runs:

```text
data/extension_year_counts.csv
data/language_year_counts.csv
data/build_metadata.json
data/shard_counts/*.csv
data/languages.yml
```

The per-shard checkpoints and downloaded Linguist catalog are ignored by Git. The final aggregate CSVs and `build_metadata.json` should be committed after a successful run so the deployed dashboard can load immediately without rescanning S3. `data/paper_reference_top10.csv` is also versioned as a small validation fixture copied from the selected years printed in Table II of the paper.

## Important limitations

1. **Extension ≠ language.** The paper uses file extensions as a scalable proxy for programming language; the same limitation applies here.
2. **Ambiguous extensions exist.** GitHub Linguist can associate an extension with multiple languages. The paper resolved these case-by-case. This demo applies explicit overrides only where stated and skips other unresolved ambiguities.
3. **Recent years can be incomplete.** The paper attributes the drop in its most recent years to Software Heritage crawler lag. The dashboard exposes the years but does not treat the newest values as complete.
4. **Partial shard runs are only development samples.** They are not random samples and should not be used to estimate global language popularity.
5. **The 2026 export should not exactly equal the paper.** The paper used the `2024-08-23` Aggregated Contents dataset; this project intentionally targets the updated `2026-06-04` export.

## Files

- `inspect_contents.py` — original 20-row inspection demo
- `build_counts.py` — remote Parquet aggregation with resumable shard checkpoints
- `language_map.py` — GitHub Linguist extension mapping
- `swh_utils.py` — filename / extension / timestamp helpers
- `app.py` — Streamlit dashboard
- `data/paper_reference_top10.csv` — selected Table II reference values
- `tests/test_swh_utils.py` — basic transformation tests

## References

- Desmazières, A., Di Cosmo, R., & Lorentz, V. (2025). *50 Years of Programming Language Evolution through the Software Heritage looking glass*. MSR 2025.
- Software Heritage Aggregated Contents dataset, export `2026-06-04`.
- GitHub Linguist `languages.yml` for extension-to-language metadata.


## Deploy as a live dashboard

After the aggregation finishes, commit `data/extension_year_counts.csv`, `data/language_year_counts.csv`, and `data/build_metadata.json` with the code. The repository can then be deployed directly with Streamlit Community Cloud using `app.py` as the entry point. The deployed app reads the precomputed aggregate files; it does not rescan the full Software Heritage dataset on every page load.
