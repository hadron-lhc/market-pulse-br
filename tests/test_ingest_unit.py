"""Unit tests for CSV parsing and casting (no database required)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ecommerce_intel import ingest
from ecommerce_intel.ingest import IngestError

ORDERS_HEADER = (
    "order_id,customer_id,order_status,order_purchase_timestamp,"
    "order_approved_at,order_delivered_carrier_date,"
    "order_delivered_customer_date,order_estimated_delivery_date\n"
)


def _write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "sample.csv"
    path.write_text(ORDERS_HEADER + content, encoding="utf-8")
    return path


def test_casts_and_nulls(tmp_path):
    path = _write(
        tmp_path,
        "o1,c1,delivered,2018-01-01 10:00:00,2018-01-01 11:00:00,"
        "2018-01-03 09:00:00,2018-01-10 12:00:00,2018-01-09 00:00:00\n"
        "o2,c2,canceled,2018-02-01 10:00:00,,2018-02-03 09:00:00,,2018-02-20 00:00:00\n",
    )
    rows = list(ingest.iter_casted_rows(ingest.TABLES["orders"], path))
    assert len(rows) == 2
    assert rows[0][0] == "o1"
    assert rows[0][3] == datetime(2018, 1, 1, 10, 0, 0)
    assert rows[1][4] is None  # empty timestamp -> NULL
    assert rows[1][6] is None


def test_numeric_types(tmp_path):
    items_csv = tmp_path / "items.csv"
    items_csv.write_text(
        "order_id,order_item_id,product_id,seller_id,shipping_limit_date,price,freight_value\n"
        "o1,1,p1,s1,2018-01-05 00:00:00,100.10,10.25\n",
        encoding="utf-8",
    )
    rows = list(ingest.iter_casted_rows(ingest.TABLES["order_items"], items_csv))
    assert rows[0][1] == 1
    assert rows[0][5] == Decimal("100.10")
    assert rows[0][6] == Decimal("10.25")


def test_bad_integer_reports_context(tmp_path):
    path = _write(
        tmp_path,
        "o1,c1,delivered,not-a-timestamp,2018-01-01 11:00:00,,2018-01-10 12:00:00,2018-01-09 00:00:00\n",
    )
    with pytest.raises(IngestError, match="order_purchase_timestamp"):
        list(ingest.iter_casted_rows(ingest.TABLES["orders"], path))


def test_header_mismatch_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("wrong,header,here\n1,2,3\n", encoding="utf-8")
    with pytest.raises(IngestError, match="unexpected header"):
        list(ingest.iter_casted_rows(ingest.TABLES["orders"], path))


def test_field_count_mismatch_rejected(tmp_path):
    path = _write(tmp_path, "o1,c1,delivered\n")
    with pytest.raises(IngestError, match="expected 8 fields"):
        list(ingest.iter_casted_rows(ingest.TABLES["orders"], path))


def test_count_csv_rows(tmp_path):
    path = _write(
        tmp_path,
        "o1,c1,delivered,2018-01-01 10:00:00,,2018-01-03 09:00:00,2018-01-10 12:00:00,2018-01-09 00:00:00\n",
    )
    assert ingest.count_csv_rows(path) == 1
