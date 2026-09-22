"""Build dashboard-ready counts from Software Heritage Aggregated Contents.

Development mode intentionally reads only a bounded number of rows per shard.
Use --rows-per-shard 0 only when you actually intend to scan each selected shard
in full.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from urllib.parse import quote

import boto3
from botocore import UNSIGNED
from botocore.config import Config
import duckdb
import pandas as pd

from language_map import build_extension_language_map
from swh_utils import extract_extension, timestamp_to_year

BUCKET = "softwareheritage"
DEFAULT_PREFIX = "derived_datasets/2026-06-04/contents/"
DATASET_EXPORT = "2026-06-04"


def list_parquet_keys(prefix: str) -> list[str]:
    s3 = boto3.client("s3", region_name="us-east-1", config=Config(signature_version=UNSIGNED))
    keys: list[str] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".parquet"):
                keys.append(key)
    return sorted(keys)


def public_https_url(key: str) -> str:
    return f"https://{BUCKET}.s3.amazonaws.com/{quote(key, safe='/')}"


def process_shard(con, url: str, min_year: int, max_year: int, rows_per_shard: int) -> pd.DataFrame:
    limit_sql = "" if rows_per_shard == 0 else f"LIMIT {int(rows_per_shard)}"
    query = f"""
        SELECT filename, first_occurrence_timestamp
        FROM read_parquet(?)
        WHERE filename IS NOT NULL
          AND first_occurrence_timestamp IS NOT NULL
        {limit_sql}
    """
    print("    reading rows...", flush=True)
    sample = con.execute(query, [url]).fetch_df()
    print(f"    received {len(sample):,} rows; aggregating...", flush=True)

    counter: Counter[tuple[int, str]] = Counter()
    for filename, timestamp in zip(sample["filename"], sample["first_occurrence_timestamp"]):
        ext = extract_extension(filename)
        if not ext:
            continue
        year = timestamp_to_year(timestamp)
        if year is None or year < min_year or year > max_year:
            continue
        counter[(year, ext)] += 1

    return pd.DataFrame(
        ((year, ext, count) for (year, ext), count in counter.items()),
        columns=["year", "extension", "count"],
    )


def combine_checkpoints(checkpoint_dir: Path) -> pd.DataFrame:
    frames = [pd.read_csv(path) for path in sorted(checkpoint_dir.glob("*.csv"))]
    if not frames:
        return pd.DataFrame(columns=["year", "extension", "count"])
    combined = pd.concat(frames, ignore_index=True)
    return combined.groupby(["year", "extension"], as_index=False)["count"].sum()


def make_language_counts(extension_counts: pd.DataFrame, extension_map: dict[str, tuple[str, str]]) -> pd.DataFrame:
    mapped = extension_counts.copy()
    mapped[["language", "type"]] = mapped["extension"].apply(
        lambda ext: pd.Series(extension_map.get(str(ext), (None, None)))
    )
    mapped = mapped.dropna(subset=["language", "type"])
    return mapped.groupby(["year", "language", "type"], as_index=False)["count"].sum()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-shards", type=int, default=1, help="Number of shards. 0 = all.")
    parser.add_argument(
        "--rows-per-shard",
        type=int,
        default=100_000,
        help="Rows read from each shard. 0 = full shard. Default is a fast development sample.",
    )
    parser.add_argument("--min-year", type=int, default=1967)
    parser.add_argument("--max-year", type=int, default=2026)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--rebuild", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = args.data_dir / "shard_counts"
    if args.rebuild and checkpoint_dir.exists():
        shutil.rmtree(checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    print("Listing public Parquet shards...", flush=True)
    all_keys = list_parquet_keys(DEFAULT_PREFIX)
    if not all_keys:
        raise RuntimeError("No Parquet shards found.")
    selected_keys = all_keys if args.max_shards == 0 else all_keys[: args.max_shards]
    print(f"Dataset has {len(all_keys)} shards; this run targets {len(selected_keys)}.", flush=True)
    if args.rows_per_shard:
        print(f"Development sample: at most {args.rows_per_shard:,} rows per shard.", flush=True)
    else:
        print("FULL-SHARD MODE: this can take a long time.", flush=True)

    con = duckdb.connect()
    con.execute("INSTALL httpfs")
    con.execute("LOAD httpfs")

    for index, key in enumerate(selected_keys):
        checkpoint = checkpoint_dir / f"{index:05d}.csv"
        if checkpoint.exists():
            print(f"[{index + 1}/{len(selected_keys)}] already complete", flush=True)
            continue
        print(f"[{index + 1}/{len(selected_keys)}] {key}", flush=True)
        counts = process_shard(con, public_https_url(key), args.min_year, args.max_year, args.rows_per_shard)
        counts.to_csv(checkpoint, index=False)
        print(f"    wrote {len(counts):,} extension/year groups", flush=True)

    extension_counts = combine_checkpoints(checkpoint_dir)
    extension_counts.to_csv(args.data_dir / "extension_year_counts.csv", index=False)

    extension_map, map_source, ambiguous = build_extension_language_map(args.data_dir / "languages.yml")
    language_counts = make_language_counts(extension_counts, extension_map)
    language_counts.to_csv(args.data_dir / "language_year_counts.csv", index=False)

    metadata = {
        "dataset_export": DATASET_EXPORT,
        "total_shards": len(all_keys),
        "targeted_shards": len(selected_keys),
        "rows_per_shard": args.rows_per_shard,
        "partial": len(selected_keys) < len(all_keys) or args.rows_per_shard > 0,
        "min_year": args.min_year,
        "max_year": args.max_year,
        "language_map_source": map_source,
        "ambiguous_extensions_skipped": len(ambiguous),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (args.data_dir / "build_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print("Done.", flush=True)
    print(f"  {args.data_dir / 'extension_year_counts.csv'}", flush=True)
    print(f"  {args.data_dir / 'language_year_counts.csv'}", flush=True)


if __name__ == "__main__":
    main()
