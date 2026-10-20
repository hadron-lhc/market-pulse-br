"""Smoke-test the Streamlit dashboard with the AppTest runner.

Requires the analytics marts to exist (run `make ingest dbt-build` first);
skips when they do not.
"""

from __future__ import annotations

import psycopg
import pytest
from streamlit.testing.v1 import AppTest

from ecommerce_intel.config import REPO_ROOT, load_settings
from ecommerce_intel.db import connect


def _marts_available() -> bool:
    try:
        with connect(load_settings()) as conn:
            conn.execute("select 1 from marts.mart_kpi_overview")
        return True
    except psycopg.Error:
        return False


@pytest.mark.skipif(not _marts_available(), reason="dbt marts not built")
def test_dashboard_renders_core_elements():
    at = AppTest.from_file(str(REPO_ROOT / "dashboard" / "app.py"), default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    assert at.title[0].value == "Market Pulse"
    assert [t.label for t in at.tabs] == [
        "Revenue",
        "Categories",
        "Sellers",
        "Delivery",
        "Payments",
        "Customers",
    ]
    labels = [m.label for m in at.metric]
    assert "Revenue (period)" in labels
    assert "Late rate (period)" in labels
