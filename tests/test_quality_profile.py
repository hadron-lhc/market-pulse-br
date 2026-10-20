"""Quality report generation against the synthetic fixture schema."""

from __future__ import annotations

from ecommerce_intel.quality_profile import build_report


def test_build_report_runs_on_fixture_schema(fixture_conn):
    report = build_report(fixture_conn)
    assert "# Data Quality Report" in report
    assert "raw.orders" in report
    assert "orders with more than 1 item" in report
    # Fixture: exactly one order has 2 items.
    assert "| orders with more than 1 item | 1 |" in report
