"""Profile the raw schema and write ``docs/data_quality_report.md``.

Usage:
    python -m ecommerce_intel.quality_profile

The report is generated from the actual loaded data: row counts, primary key
uniqueness, null rates, referential integrity, join fan-out candidates and the
order-level revenue reconciliation between items and payments.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

import psycopg

from .config import Settings, load_settings
from .db import connect

log = logging.getLogger("ecommerce_intel.quality_profile")

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = REPO_ROOT / "docs" / "data_quality_report.md"

PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "orders": ("order_id",),
    "customers": ("customer_id",),
    "order_items": ("order_id", "order_item_id"),
    "order_payments": ("order_id", "payment_sequential"),
    "products": ("product_id",),
    "sellers": ("seller_id",),
    "product_category_name_translation": ("product_category_name",),
    "order_reviews": (),  # review_id is duplicated in the source
    "geolocation": (),  # duplicates by design
}

FOREIGN_KEYS: list[tuple[str, str, str, str]] = [
    # (child table, child column, parent table, parent column)
    ("orders", "customer_id", "customers", "customer_id"),
    ("order_items", "order_id", "orders", "order_id"),
    ("order_items", "product_id", "products", "product_id"),
    ("order_items", "seller_id", "sellers", "seller_id"),
    ("order_payments", "order_id", "orders", "order_id"),
    ("order_reviews", "order_id", "orders", "order_id"),
]

FANOUT_QUERIES: dict[str, str] = {
    "orders with more than 1 item": (
        "SELECT count(*) FROM (SELECT order_id FROM raw.order_items "
        "GROUP BY order_id HAVING count(*) > 1) t"
    ),
    "orders with more than 1 payment record": (
        "SELECT count(*) FROM (SELECT order_id FROM raw.order_payments "
        "GROUP BY order_id HAVING count(*) > 1) t"
    ),
    "orders with more than 1 review record": (
        "SELECT count(*) FROM (SELECT order_id FROM raw.order_reviews "
        "GROUP BY order_id HAVING count(*) > 1) t"
    ),
    "orders with no items": (
        "SELECT count(*) FROM raw.orders o "
        "WHERE NOT EXISTS (SELECT 1 FROM raw.order_items i WHERE i.order_id = o.order_id)"
    ),
    "orders with no payment record": (
        "SELECT count(*) FROM raw.orders o "
        "WHERE NOT EXISTS (SELECT 1 FROM raw.order_payments p WHERE p.order_id = o.order_id)"
    ),
    "orders with no review record": (
        "SELECT count(*) FROM raw.orders o "
        "WHERE NOT EXISTS (SELECT 1 FROM raw.order_reviews r WHERE r.order_id = o.order_id)"
    ),
}

REVENUE_QUERY = """
WITH item_totals AS (
    SELECT order_id,
           sum(price + freight_value)              AS item_total,
           count(*)                                AS item_count
    FROM raw.order_items
    GROUP BY order_id
),
payment_totals AS (
    SELECT order_id, sum(payment_value) AS payment_total
    FROM raw.order_payments
    GROUP BY order_id
)
SELECT
    (SELECT coalesce(sum(price + freight_value), 0) FROM raw.order_items)          AS goods_plus_freight,
    (SELECT coalesce(sum(payment_value), 0) FROM raw.order_payments)               AS payment_sum,
    count(*)                                                                        AS orders_both,
    count(*) FILTER (WHERE abs(item_total - payment_total) > 0.01)                  AS orders_mismatch,
    coalesce(max(abs(item_total - payment_total)), 0)                               AS max_abs_diff
FROM item_totals
JOIN payment_totals USING (order_id)
"""

ORDER_STATUS_QUERY = """
SELECT order_status, count(*)
FROM raw.orders
GROUP BY order_status
ORDER BY count(*) DESC
"""


def _table_columns(conn: psycopg.Connection, table: str) -> list[tuple[str, str]]:
    rows = conn.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'raw' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table,),
    ).fetchall()
    return [(r[0], r[1]) for r in rows]


def _null_rates(conn: psycopg.Connection, table: str) -> list[tuple[str, str, int]]:
    """Return [(column, data_type, null_count)] using a single scan per table."""
    columns = _table_columns(conn, table)
    filters = ", ".join(f"count(*) FILTER (WHERE {name} IS NULL) AS {name}" for name, _ in columns)
    counts = conn.execute(f"SELECT {filters} FROM raw.{table}").fetchone()
    return [(name, dtype, count) for (name, dtype), count in zip(columns, counts, strict=True)]


def _pk_duplicates(conn: psycopg.Connection, table: str) -> int | None:
    pk = PRIMARY_KEYS[table]
    if not pk:
        return None
    cols = ", ".join(pk)
    return conn.execute(
        f"SELECT count(*) FROM (SELECT {cols} FROM raw.{table} "
        f"GROUP BY {cols} HAVING count(*) > 1) d"
    ).fetchone()[0]


def _fk_orphans(conn: psycopg.Connection) -> list[tuple[str, int]]:
    results = []
    for child, child_col, parent, parent_col in FOREIGN_KEYS:
        orphans = conn.execute(
            f"""
            SELECT count(*) FROM raw.{child} c
            WHERE NOT EXISTS (
                SELECT 1 FROM raw.{parent} p WHERE p.{parent_col} = c.{child_col}
            )
            """
        ).fetchone()[0]
        results.append((f"{child}.{child_col} -> {parent}.{parent_col}", orphans))
    return results


def build_report(conn: psycopg.Connection) -> str:
    tables = list(PRIMARY_KEYS)
    lines: list[str] = []
    lines.append("# Data Quality Report (raw schema)")
    lines.append("")
    lines.append(
        f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S} — "
        "all values below are computed from the loaded Olist CSVs."
    )
    lines.append("")

    lines.append("## Row counts and primary keys")
    lines.append("")
    lines.append("| table | rows | primary key | duplicate pk rows |")
    lines.append("|---|---:|---|---:|")
    for table in tables:
        rows = conn.execute(f"SELECT count(*) FROM raw.{table}").fetchone()[0]
        pk = ", ".join(PRIMARY_KEYS[table]) or "_(none)_"
        dups = _pk_duplicates(conn, table)
        dups_text = "n/a" if dups is None else f"{dups:,}"
        lines.append(f"| raw.{table} | {rows:,} | {pk} | {dups_text} |")
    lines.append("")

    lines.append("## Null rates by column (non-zero only)")
    lines.append("")
    lines.append("| table | column | type | nulls | null % |")
    lines.append("|---|---|---|---:|---:|")
    for table in tables:
        total = conn.execute(f"SELECT count(*) FROM raw.{table}").fetchone()[0]
        for col, dtype, nulls in _null_rates(conn, table):
            if nulls:
                pct = 100 * nulls / total
                lines.append(f"| raw.{table} | {col} | {dtype} | {nulls:,} | {pct:.2f}% |")
    lines.append("")

    lines.append("## Referential integrity (orphan child rows)")
    lines.append("")
    lines.append("| foreign key | orphan rows |")
    lines.append("|---|---:|")
    for label, orphans in _fk_orphans(conn):
        lines.append(f"| {label} | {orphans:,} |")
    lines.append("")

    lines.append("## Join fan-out risk (multi-record orders)")
    lines.append("")
    lines.append("| condition | orders |")
    lines.append("|---|---:|")
    for label, query in FANOUT_QUERIES.items():
        lines.append(f"| {label} | {conn.execute(query).fetchone()[0]:,} |")
    lines.append("")
    lines.append(
        "These counts are the reason revenue and order metrics are computed at "
        "item or order grain in dedicated aggregation models instead of joining "
        "orders x items x payments x reviews directly."
    )
    lines.append("")

    goods, payments, both, mismatch, max_diff = conn.execute(REVENUE_QUERY).fetchone()
    lines.append("## Revenue reconciliation: items vs payments")
    lines.append("")
    lines.append("| measure | value |")
    lines.append("|---|---:|")
    lines.append(f"| sum(item price + freight) | {goods:,.2f} |")
    lines.append(f"| sum(payment_value) | {payments:,.2f} |")
    lines.append(f"| difference | {payments - goods:,.2f} |")
    lines.append(f"| orders present in both tables | {both:,} |")
    lines.append(f"| orders where abs difference > 0.01 | {mismatch:,} |")
    lines.append(f"| max abs difference on a single order | {max_diff:,.2f} |")
    lines.append("")
    lines.append(
        "Payments can include vouchers and orders that have no items, so the two "
        "totals are expected to differ slightly. Item revenue (price + freight) is "
        "the project's revenue definition; payment totals are used for "
        "reconciliation only."
    )
    lines.append("")

    lines.append("## Order status distribution")
    lines.append("")
    lines.append("| status | orders |")
    lines.append("|---|---:|")
    for status, count in conn.execute(ORDER_STATUS_QUERY).fetchall():
        lines.append(f"| {status} | {count:,} |")
    lines.append("")

    lines.append("## Timestamp ranges")
    lines.append("")
    lines.append("| column | min | max | nulls |")
    lines.append("|---|---|---|---:|")
    for col in (
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ):
        row = conn.execute(
            f"SELECT min({col}), max({col}), count(*) - count({col}) FROM raw.orders"
        ).fetchone()
        lines.append(f"| orders.{col} | {row[0] or '—'} | {row[1] or '—'} | {row[2]:,} |")
    lines.append("")
    return "\n".join(lines) + "\n"


def run(settings: Settings) -> Path:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect(settings) as conn:
        report = build_report(conn)
    REPORT_PATH.write_text(report, encoding="utf-8")
    log.info("wrote %s", REPORT_PATH.relative_to(REPO_ROOT))
    return REPORT_PATH


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    del argv  # no CLI flags today; kept for symmetry with ingest
    try:
        run(load_settings())
    except psycopg.Error as exc:
        log.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
