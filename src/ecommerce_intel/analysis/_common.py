"""Shared helpers for the analysis scripts."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import psycopg

from ..config import REPO_ROOT, Settings, load_settings
from ..db import connect

log = logging.getLogger("ecommerce_intel.analysis")

OUTPUT_DIR = REPO_ROOT / "analysis" / "output"


def get_conn(settings: Settings | None = None) -> psycopg.Connection:
    return connect(settings or load_settings())


def load_df(conn: psycopg.Connection, sql: str, params: tuple | None = None) -> pd.DataFrame:
    """Run a query and return a DataFrame (column names from the cursor)."""
    with conn.cursor() as cur:
        cur.execute(sql, params)
        columns = [d.name for d in cur.description]
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=columns)


def save_fig(fig: go.Figure, name: str) -> Path:
    """Write an interactive Plotly figure to analysis/output/<name>.html."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{name}.html"
    fig.write_html(path, include_plotlyjs="cdn", full_html=True)
    log.info("wrote %s", path.relative_to(REPO_ROOT))
    return path


def base_layout(fig: go.Figure, title: str, yaxis_title: str = "") -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        title=title,
        font=dict(family="Arial", size=13),
        margin=dict(l=60, r=30, t=60, b=60),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        yaxis_title=yaxis_title or None,
    )
    return fig


def fmt_pct(value: float) -> str:
    return f"{value:.2f}%"


def fmt_brl(value: float) -> str:
    return f"R$ {value:,.2f}"


def fmt_int(value: float) -> str:
    return f"{int(value):,}"
