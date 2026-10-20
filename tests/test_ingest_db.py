"""Database integration tests against the synthetic fixture schema.

These pin the ingestion guarantees (idempotency, PK/FK enforcement, NULL
handling) and the anti-double-counting aggregation patterns using the
invented fixture rows — never the real Olist data.
"""

from __future__ import annotations

import dataclasses

import psycopg
import pytest

from ecommerce_intel import ingest


def test_row_counts_match_fixture_csvs(fixture_conn):
    expected = {
        "orders": 4,
        "customers": 4,
        "sellers": 2,
        "products": 2,
        "order_items": 4,
        "order_payments": 4,
        "order_reviews": 4,
    }
    for table, count in expected.items():
        loaded = fixture_conn.execute(f"SELECT count(*) FROM raw.{table}").fetchone()[0]
        assert loaded == count, table


RELOAD_ORDER = [
    ("customers", "fixture_customers.csv"),
    ("sellers", "fixture_sellers.csv"),
    ("products", "fixture_products.csv"),
    ("orders", "fixture_orders.csv"),
    ("order_items", "fixture_order_items.csv"),
    ("order_payments", "fixture_order_payments.csv"),
    ("order_reviews", "fixture_order_reviews.csv"),
]


def test_reload_is_idempotent(fixture_conn, seeds_dir):
    """A second truncate+copy pass must not change row counts."""
    tables = [t for t, _ in RELOAD_ORDER]
    before = {
        table: fixture_conn.execute(f"SELECT count(*) FROM raw.{table}").fetchone()[0]
        for table in tables
    }
    fixture_conn.execute("TRUNCATE " + ", ".join(f"raw.{t}" for t in tables))
    for table, filename in RELOAD_ORDER:
        spec = dataclasses.replace(ingest.TABLES[table], csv_file=filename)
        ingest.load_table(fixture_conn, spec, seeds_dir)
    after = {
        table: fixture_conn.execute(f"SELECT count(*) FROM raw.{table}").fetchone()[0]
        for table in tables
    }
    assert after == before


def test_primary_key_violation_rejected(fixture_conn):
    with pytest.raises(psycopg.errors.UniqueViolation):
        fixture_conn.execute(
            """
            insert into raw.orders (
                order_id, customer_id, order_status, order_purchase_timestamp,
                order_estimated_delivery_date
            ) values (
                'o_multi_item', 'c1', 'delivered', '2018-01-01 10:00:00',
                '2018-01-09 00:00:00'
            )
            """
        )


def test_foreign_key_violation_rejected(fixture_conn):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        fixture_conn.execute(
            """
            insert into raw.orders (
                order_id, customer_id, order_status, order_purchase_timestamp,
                order_estimated_delivery_date
            ) values (
                'o_ghost', 'no_such_customer', 'delivered', '2018-01-01 10:00:00',
                '2018-01-09 00:00:00'
            )
            """
        )


def test_missing_and_canceled_timestamps_are_null(fixture_conn):
    row = fixture_conn.execute(
        """
        select order_delivered_carrier_date, order_delivered_customer_date
        from raw.orders where order_id = 'o_missing_ts'
        """
    ).fetchone()
    assert row == (None, None)

    carrier, delivered = fixture_conn.execute(
        """
        select order_delivered_carrier_date, order_delivered_customer_date
        from raw.orders where order_id = 'o_canceled'
        """
    ).fetchone()
    assert carrier is None and delivered is None


def test_multi_item_order_groups_to_one_row(fixture_conn):
    total = fixture_conn.execute(
        """
        select sum(price + freight_value)
        from raw.order_items where order_id = 'o_multi_item'
        """
    ).fetchone()[0]
    assert float(total) == 170.0


def test_multi_payment_order_groups_to_one_row(fixture_conn):
    total = fixture_conn.execute(
        """
        select sum(payment_value)
        from raw.order_payments where order_id = 'o_multi_pay'
        """
    ).fetchone()[0]
    assert float(total) == 35.0


def test_naive_join_would_double_count(fixture_conn):
    """Documents the fan-out the pipeline is designed to avoid."""
    naive = fixture_conn.execute(
        """
        select sum(i.price + i.freight_value)
        from raw.order_items i
        join raw.order_payments p on i.order_id = p.order_id
        where i.order_id = 'o_multi_pay'
        """
    ).fetchone()[0]
    assert float(naive) == 70.0  # vs the true 35.00


def test_revenue_population_excludes_canceled(fixture_conn):
    revenue = fixture_conn.execute(
        """
        select sum(i.price + i.freight_value)
        from raw.order_items i
        join raw.orders o on i.order_id = o.order_id
        where o.order_status not in ('canceled', 'unavailable')
        """
    ).fetchone()[0]
    assert float(revenue) == 205.0  # canceled order's 100.00 excluded


def test_review_dedup_keeps_latest_answer(fixture_conn):
    score = fixture_conn.execute(
        """
        select review_score from (
            select review_score,
                   row_number() over (
                       partition by order_id
                       order by review_answer_timestamp desc, review_id desc
                   ) as rn
            from raw.order_reviews where order_id = 'o_multi_item'
        ) t where rn = 1
        """
    ).fetchone()[0]
    assert score == 2
