"""Shared pytest fixtures.

Database tests run against a dedicated database (``olist_analytics_pytest``)
loaded with the synthetic fixtures from ``dbt_project/seeds/``. They skip
automatically when PostgreSQL is unreachable; they never touch the real
``olist_analytics`` database.
"""

from __future__ import annotations

import dataclasses

import psycopg
import pytest

from ecommerce_intel import ingest
from ecommerce_intel.config import REPO_ROOT, Settings, load_settings
from ecommerce_intel.db import connect, ensure_database

SEEDS_DIR = REPO_ROOT / "dbt_project" / "seeds"
TEST_DBNAME = "olist_analytics_pytest"

# (raw table, seed file) in foreign-key-safe load order.
FIXTURE_TABLES = [
    ("customers", "fixture_customers.csv"),
    ("sellers", "fixture_sellers.csv"),
    ("products", "fixture_products.csv"),
    ("orders", "fixture_orders.csv"),
    ("order_items", "fixture_order_items.csv"),
    ("order_payments", "fixture_order_payments.csv"),
    ("order_reviews", "fixture_order_reviews.csv"),
]


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return dataclasses.replace(load_settings(), dbname=TEST_DBNAME)


@pytest.fixture(scope="session")
def seeds_dir():
    return SEEDS_DIR


@pytest.fixture(scope="session")
def fixture_conn(test_settings: Settings):
    """A connection to the fixture database, loaded with the synthetic CSVs."""
    try:
        ensure_database(test_settings)
        conn = connect(test_settings)
    except (psycopg.Error, SystemExit) as exc:  # pragma: no cover - env dependent
        pytest.skip(f"PostgreSQL unavailable: {exc}")

    conn.autocommit = True
    conn.execute(ingest.DDL_PATH.read_text(encoding="utf-8"))
    conn.execute("TRUNCATE " + ", ".join(f"raw.{t}" for t in ingest.LOAD_ORDER))
    for table, filename in FIXTURE_TABLES:
        spec = dataclasses.replace(ingest.TABLES[table], csv_file=filename)
        ingest.load_table(conn, spec, SEEDS_DIR)
    yield conn
    conn.close()
