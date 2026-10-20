"""Revenue and order performance: trends, order-value distribution, exclusions."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ._common import base_layout, fmt_brl, fmt_int, fmt_pct, load_df, save_fig

MONTHLY_SQL = """
select purchase_month, orders, customers, items_sold, revenue, avg_order_value,
       median_order_value
from marts.mart_monthly_revenue
order by purchase_month
"""

VALUE_DISTRIBUTION_SQL = """
select order_revenue
from intermediate.int_order_facts
where is_revenue_order
"""

STATUS_SQL = """
select
    case
        when order_status in ('canceled', 'unavailable') then 'excluded: canceled/unavailable'
        when items_count = 0 then 'excluded: no items recorded'
        else 'revenue population'
    end as population,
    count(*) as orders,
    round(sum(order_revenue), 2) as order_value
from intermediate.int_order_facts
group by 1
order by orders desc
"""


def run(conn) -> str:
    monthly = load_df(conn, MONTHLY_SQL)
    monthly["purchase_month"] = pd.to_datetime(monthly["purchase_month"])
    values = load_df(conn, VALUE_DISTRIBUTION_SQL)["order_revenue"].astype(float)
    status = load_df(conn, STATUS_SQL)

    # --- Monthly trend: revenue bars + order line ----------------------------
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=monthly["purchase_month"],
            y=monthly["revenue"],
            name="Revenue (BRL)",
            marker_color="#1f77b4",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=monthly["purchase_month"],
            y=monthly["orders"],
            name="Orders",
            mode="lines+markers",
            line=dict(color="#ff7f0e", width=2),
        ),
        secondary_y=True,
    )
    fig = base_layout(
        fig,
        "Monthly revenue and orders (revenue population)",
        yaxis_title="Revenue (BRL)",
    )
    fig.update_yaxes(title_text="Orders", secondary_y=True)
    save_fig(fig, "revenue_monthly_trend")

    # --- Order value distribution -------------------------------------------
    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=values,
            nbinsx=80,
            name="Orders",
            marker_color="#1f77b4",
            hovertemplate="R$ %{x}<br>%{y} orders<extra></extra>",
        )
    )
    median = float(values.median())
    aov = float(values.mean())
    fig.add_vline(
        x=median, line_dash="dash", line_color="green", annotation_text=f"Median {fmt_brl(median)}"
    )
    fig.add_vline(x=aov, line_dash="dash", line_color="red", annotation_text=f"AOV {fmt_brl(aov)}")
    fig = base_layout(fig, "Distribution of order value (price + freight)", yaxis_title="Orders")
    fig.update_xaxes(title_text="Order value (BRL)", range=[0, 1500])
    save_fig(fig, "revenue_order_value_distribution")

    # --- Population exclusions ----------------------------------------------
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=status["population"],
            y=status["orders"],
            text=status["orders"].map(fmt_int),
            textposition="outside",
            marker_color=["#2ca02c", "#d62728", "#7f7f7f"][: len(status)],
        )
    )
    fig = base_layout(
        fig, "Order population: what the revenue metrics include", yaxis_title="Orders"
    )
    fig.update_layout(showlegend=False)
    save_fig(fig, "revenue_population_exclusions")

    top_month = monthly.loc[monthly["revenue"].idxmax()]
    bottom_month = monthly.loc[monthly["orders"].idxmin()]
    growth = (
        monthly[monthly["purchase_month"] >= "2017-01-01"]
        .groupby(monthly["purchase_month"].dt.year)["revenue"]
        .sum()
    )
    yoy = (growth.get(2018, 0) / growth.get(2017, float("nan")) - 1) * 100

    return f"""## Revenue and order performance

- Revenue population: {fmt_int(status.loc[status.population == "revenue population", "orders"].iloc[0])} orders,
  {fmt_brl(status.loc[status.population == "revenue population", "order_value"].iloc[0])} in item revenue
  (price + freight, canceled/unavailable excluded).
- Peak month: {top_month["purchase_month"]:%Y-%m} with {fmt_brl(top_month["revenue"])}
  across {fmt_int(top_month["orders"])} orders.
- AOV {fmt_brl(float(values.mean()))} vs median order value {fmt_brl(median)}:
  the distribution is right-skewed ({fmt_pct(100 * float((values > 500).mean()))} of orders above R$ 500).
- 2018 vs 2017 revenue (Jan-Dec where comparable): {yoy:+.1f}%.
- Thinnest month: {bottom_month["purchase_month"]:%Y-%m} with {fmt_int(bottom_month["orders"])} orders
  (the dataset starts Sep-2016 and effectively ends Aug-2018).
- Charts: analysis/output/revenue_monthly_trend.html, revenue_order_value_distribution.html,
  revenue_population_exclusions.html.
"""
