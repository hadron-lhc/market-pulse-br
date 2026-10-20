"""Idempotent CSV -> PostgreSQL ingestion into the ``raw`` schema.

Usage:
    python -m ecommerce_intel.ingest

Every run truncates and reloads all raw tables inside a single transaction, so
repeated runs can never duplicate source rows. Row counts are asserted against
the source CSVs before the transaction commits.
"""

from __future__ import annotations

import argparse
import csv
import io
import logging
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import psycopg

from .config import Settings, load_settings
from .db import connect, ensure_database

log = logging.getLogger("ecommerce_intel.ingest")

REPO_ROOT = Path(__file__).resolve().parents[2]
DDL_PATH = REPO_ROOT / "sql" / "raw_ddl.sql"

_TS_FORMAT = "%Y-%m-%d %H:%M:%S"
_COPY_CHUNK_CHARS = 1 << 20  # flush the COPY buffer roughly every million characters


class IngestError(RuntimeError):
    """Raised when a source value cannot be cast to the declared column type."""


@dataclass(frozen=True)
class Column:
    name: str
    dtype: str  # text | integer | numeric | timestamp


@dataclass(frozen=True)
class TableSpec:
    table: str
    csv_file: str
    columns: tuple[Column, ...]

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]


def _text(raw: str) -> str | None:
    return raw if raw != "" else None


def _integer(raw: str) -> int | None:
    if raw == "":
        return None
    return int(raw)


def _numeric(raw: str) -> Decimal | None:
    if raw == "":
        return None
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise IngestError(f"not a number: {raw!r}") from exc


def _timestamp(raw: str) -> datetime | None:
    if raw == "":
        return None
    for fmt in (_TS_FORMAT, "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise IngestError(f"unexpected timestamp format: {raw!r}")


_CASTS = {
    "text": _text,
    "integer": _integer,
    "numeric": _numeric,
    "timestamp": _timestamp,
}

TABLES: dict[str, TableSpec] = {
    "customers": TableSpec(
        "customers",
        "olist_customers_dataset.csv",
        (
            Column("customer_id", "text"),
            Column("customer_unique_id", "text"),
            Column("customer_zip_code_prefix", "integer"),
            Column("customer_city", "text"),
            Column("customer_state", "text"),
        ),
    ),
    "sellers": TableSpec(
        "sellers",
        "olist_sellers_dataset.csv",
        (
            Column("seller_id", "text"),
            Column("seller_zip_code_prefix", "integer"),
            Column("seller_city", "text"),
            Column("seller_state", "text"),
        ),
    ),
    "products": TableSpec(
        "products",
        "olist_products_dataset.csv",
        (
            Column("product_id", "text"),
            Column("product_category_name", "text"),
            Column("product_name_lenght", "integer"),
            Column("product_description_lenght", "integer"),
            Column("product_photos_qty", "integer"),
            Column("product_weight_g", "integer"),
            Column("product_length_cm", "integer"),
            Column("product_height_cm", "integer"),
            Column("product_width_cm", "integer"),
        ),
    ),
    "product_category_name_translation": TableSpec(
        "product_category_name_translation",
        "product_category_name_translation.csv",
        (
            Column("product_category_name", "text"),
            Column("product_category_name_english", "text"),
        ),
    ),
    "geolocation": TableSpec(
        "geolocation",
        "olist_geolocation_dataset.csv",
        (
            Column("geolocation_zip_code_prefix", "integer"),
            Column("geolocation_lat", "numeric"),
            Column("geolocation_lng", "numeric"),
            Column("geolocation_city", "text"),
            Column("geolocation_state", "text"),
        ),
    ),
    "orders": TableSpec(
        "orders",
        "olist_orders_dataset.csv",
        (
            Column("order_id", "text"),
            Column("customer_id", "text"),
            Column("order_status", "text"),
            Column("order_purchase_timestamp", "timestamp"),
            Column("order_approved_at", "timestamp"),
            Column("order_delivered_carrier_date", "timestamp"),
            Column("order_delivered_customer_date", "timestamp"),
            Column("order_estimated_delivery_date", "timestamp"),
        ),
    ),
    "order_items": TableSpec(
        "order_items",
        "olist_order_items_dataset.csv",
        (
            Column("order_id", "text"),
            Column("order_item_id", "integer"),
            Column("product_id", "text"),
            Column("seller_id", "text"),
            Column("shipping_limit_date", "timestamp"),
            Column("price", "numeric"),
            Column("freight_value", "numeric"),
        ),
    ),
    "order_payments": TableSpec(
        "order_payments",
        "olist_order_payments_dataset.csv",
        (
            Column("order_id", "text"),
            Column("payment_sequential", "integer"),
            Column("payment_type", "text"),
            Column("payment_installments", "integer"),
            Column("payment_value", "numeric"),
        ),
    ),
    "order_reviews": TableSpec(
        "order_reviews",
        "olist_order_reviews_dataset.csv",
        (
            Column("review_id", "text"),
            Column("order_id", "text"),
            Column("review_score", "integer"),
            Column("review_comment_title", "text"),
            Column("review_comment_message", "text"),
            Column("review_creation_date", "timestamp"),
            Column("review_answer_timestamp", "timestamp"),
        ),
    ),
}

# Load order respects foreign keys declared in sql/raw_ddl.sql.
LOAD_ORDER = [
    "customers",
    "sellers",
    "products",
    "product_category_name_translation",
    "geolocation",
    "orders",
    "order_items",
    "order_payments",
    "order_reviews",
]


def iter_casted_rows(spec: TableSpec, csv_path: Path) -> Iterator[list[object]]:
    """Yield rows of casted values in ``spec`` column order."""
    casts = [_CASTS[c.dtype] for c in spec.columns]
    expected = len(spec.columns)
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        if header != spec.column_names:
            raise IngestError(
                f"{csv_path.name}: unexpected header\n"
                f"  expected: {spec.column_names}\n"
                f"  found:    {header}"
            )
        for line_no, raw_row in enumerate(reader, start=2):
            if len(raw_row) != expected:
                raise IngestError(
                    f"{csv_path.name}:{line_no}: expected {expected} fields, found {len(raw_row)}"
                )
            row: list[object] = []
            for column, cast, value in zip(spec.columns, casts, raw_row, strict=True):
                try:
                    row.append(cast(value))
                except (IngestError, ValueError) as exc:
                    raise IngestError(
                        f"{csv_path.name}:{line_no}: column {column.name}: {exc}"
                    ) from exc
            yield row


def count_csv_rows(csv_path: Path) -> int:
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        next(reader)  # header
        return sum(1 for _ in reader)


def load_table(conn: psycopg.Connection, spec: TableSpec, data_dir: Path) -> tuple[int, float]:
    """COPY one CSV into ``raw.<table>``. Returns (rows, seconds)."""
    csv_path = data_dir / spec.csv_file
    if not csv_path.exists():
        raise IngestError(f"missing source file: {csv_path}")

    started = time.perf_counter()
    columns = ", ".join(spec.column_names)
    copy_sql = f"COPY raw.{spec.table} ({columns}) FROM STDIN (FORMAT csv)"
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    with conn.cursor() as cursor, cursor.copy(copy_sql) as copy:
        for row in iter_casted_rows(spec, csv_path):
            writer.writerow(row)
            if buffer.tell() >= _COPY_CHUNK_CHARS:
                copy.write(buffer.getvalue())
                buffer.seek(0)
                buffer.truncate(0)
        if buffer.tell():
            copy.write(buffer.getvalue())
    elapsed = time.perf_counter() - started
    return count_csv_rows(csv_path), elapsed


def run(settings: Settings) -> dict[str, int]:
    ensure_database(settings)
    truncate_sql = "TRUNCATE " + ", ".join(f"raw.{t}" for t in LOAD_ORDER)

    counts: dict[str, int] = {}
    conn = connect(settings)
    try:
        # DDL is idempotent (IF NOT EXISTS) and safe to commit up front.
        conn.autocommit = True
        conn.execute(DDL_PATH.read_text(encoding="utf-8"))
        with conn.transaction():
            conn.execute(truncate_sql)
            for name in LOAD_ORDER:
                spec = TABLES[name]
                rows, elapsed = load_table(conn, spec, settings.data_dir)
                loaded = conn.execute(f"SELECT count(*) FROM raw.{spec.table}").fetchone()[0]
                if loaded != rows:
                    raise IngestError(
                        f"{spec.table}: CSV has {rows} rows but database has {loaded}"
                    )
                counts[name] = rows
                log.info("loaded raw.%-32s %8d rows in %5.1fs", spec.table, rows, elapsed)
    except (IngestError, psycopg.Error):
        log.exception("ingestion aborted; transaction rolled back")
        raise
    finally:
        conn.close()
    log.info("ingestion complete: %d tables, %d rows", len(counts), sum(counts.values()))
    return counts


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    try:
        run(load_settings())
    except (IngestError, psycopg.Error) as exc:
        log.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
