"""Inspect a tiny sample of Software Heritage's Aggregated Contents dataset."""

import boto3
import duckdb
from botocore import UNSIGNED
from botocore.config import Config

BUCKET = "softwareheritage"
PREFIX = "derived_datasets/2026-06-04/contents/"


def first_parquet_file() -> str:
    """Return one Parquet shard from the public S3 dataset."""
    s3 = boto3.client(
        "s3",
        region_name="us-east-1",
        config=Config(signature_version=UNSIGNED),
    )
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".parquet"):
                return f"s3://{BUCKET}/{obj['Key']}"
    raise RuntimeError("No Parquet files found.")


def main() -> None:
    parquet_uri = first_parquet_file()
    print(f"Reading one shard: {parquet_uri}\n")

    con = duckdb.connect()
    con.execute("INSTALL httpfs")
    con.execute("LOAD httpfs")
    con.execute("SET s3_region='us-east-1'")

    df = con.execute(
        """
        SELECT
            id,
            length,
            filename,
            filename_occurrences,
            first_occurrence_timestamp,
            first_occurrence_revrel,
            first_occurrence_origin
        FROM read_parquet(?)
        WHERE filename IS NOT NULL
        LIMIT 20
        """,
        [parquet_uri],
    ).df()

    df["filename"] = df["filename"].apply(
        lambda value: bytes(value).decode("utf-8", errors="replace")
        if value is not None
        else None
    )

    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
