"""Delivery and operations: durations, lateness, regional and category cuts."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ._common import base_layout, fmt_pct, load_df, save_fig

MONTHLY_SQL = """
select purchase_month, delivered_orders, median_delivery_days, p90_delivery_days,
       late_rate_pct
from marts.mart_delivery_monthly
order by purchase_month
"""

STATE_SQL = """
select customer_state, delivered_orders, median_delivery_days, late_rate_pct,
       has_min_sample
from marts.mart_delivery_by_state
where has_min_sample
order by late_rate_pct desc
"""

CATEGORY_SQL = """
select product_category, delivered_orders, median_delivery_days, late_rate_pct
from marts.mart_delivery_by_category
where has_min_sample
order by late_rate_pct desc
"""

DAYS_SQL = """
select delivery_days
from intermediate.int_order_facts
where is_delivered_measured
"""


def run(conn) -> str:
    monthly = load_df(conn, MONTHLY_SQL)
    monthly["purchase_month"] = pd.to_datetime(monthly["purchase_month"])

    states = load_df(conn, STATE_SQL)
    categories = load_df(conn, CATEGORY_SQL)
    days = load_df(conn, DAYS_SQL)["delivery_days"].astype(float)

    # --- Delivery duration distribution ---------------------------------------
    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=days,
            nbinsx=60,
            marker_color="#1f77b4",
            hovertemplate="%{x} days<br>%{y} orders<extra></extra>",
        )
    )
    median = float(np.percentile(days, 50))
    p90 = float(np.percentile(days, 90))
    fig.add_vline(
        x=median, line_dash="dash", line_color="green", annotation_text=f"median {median:.1f} d"
    )
    fig.add_vline(x=p90, line_dash="dash", line_color="red", annotation_text=f"p90 {p90:.1f} d")
    fig = base_layout(
        fig, "Actual delivery time (delivered orders with timestamp)", yaxis_title="Orders"
    )
    fig.update_xaxes(title_text="Days from purchase to delivery")
    save_fig(fig, "delivery_days_distribution")

    # --- Lateness trend --------------------------------------------------------
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=monthly["purchase_month"],
            y=monthly["late_rate_pct"].astype(float),
            mode="lines+markers",
            name="Late rate",
            line=dict(color="#d62728", width=2),
        )
    )
    fig = base_layout(
        fig,
        "Late deliveries by purchase month (% of delivered orders)",
        yaxis_title="Late rate (%)",
    )
    fig.update_layout(xaxis_title="Purchase month")
    save_fig(fig, "delivery_late_rate_trend")

    # --- Late rate by state -----------------------------------------------------
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=states["customer_state"],
            y=states["late_rate_pct"].astype(float),
            marker_color="#ff7f0e",
            customdata=states[["delivered_orders", "median_delivery_days"]],
            hovertemplate=(
                "%{x}<br>late %{y:.1f}%<br>%{customdata[0]} delivered orders<br>"
                "median %{customdata[1]} d<extra></extra>"
            ),
        )
    )
    fig = base_layout(
        fig,
        "Late rate by customer state (states with >=100 delivered orders)",
        yaxis_title="Late rate (%)",
    )
    fig.update_layout(xaxis_title="State")
    save_fig(fig, "delivery_late_rate_by_state")

    # --- Late rate by category --------------------------------------------------
    worst = categories.head(15)
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=worst["late_rate_pct"].astype(float),
            y=worst["product_category"],
            orientation="h",
            marker_color="#8c564b",
            customdata=worst[["delivered_orders", "median_delivery_days"]],
            hovertemplate=(
                "%{y}<br>late %{x:.1f}%<br>%{customdata[0]} delivered orders<br>"
                "median %{customdata[1]} d<extra></extra>"
            ),
        )
    )
    fig = base_layout(
        fig, "15 categories with the highest late rate (>=100 delivered orders)", yaxis_title=""
    )
    fig.update_layout(height=480)
    save_fig(fig, "delivery_late_rate_by_category")

    worst_state = states.iloc[0]
    best_state = states.iloc[-1]
    worst_cat = categories.iloc[0]
    overall_late = float(
        load_df(conn, "select late_rate_pct from marts.mart_kpi_overview")["late_rate_pct"].iloc[0]
    )

    return f"""## Delivery and operations

- Population: delivered orders with a delivery timestamp; late = delivered on a
  later calendar day than estimated. Overall late rate {fmt_pct(overall_late)}.
- Median delivery {median:.1f} days, p90 {p90:.1f} days; the tail is long.
- Highest late rate among states with >=100 delivered orders:
  {worst_state["customer_state"]} ({fmt_pct(float(worst_state["late_rate_pct"]))});
  lowest: {best_state["customer_state"]} ({fmt_pct(float(best_state["late_rate_pct"]))}).
- Category spread is wider than the state spread: worst category
  {worst_cat["product_category"]} at {fmt_pct(float(worst_cat["late_rate_pct"]))} late.
- Charts: analysis/output/delivery_days_distribution.html, delivery_late_rate_trend.html,
  delivery_late_rate_by_state.html, delivery_late_rate_by_category.html.
"""
