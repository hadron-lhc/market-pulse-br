"""Product category analytics: revenue leaders, volume vs value, trends."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ._common import base_layout, fmt_brl, fmt_pct, load_df, save_fig

PERFORMANCE_SQL = """
select product_category, items, orders, revenue, avg_item_revenue,
       revenue_share_pct, item_share_pct, avg_review_score, sellers
from marts.mart_category_performance
where product_category <> 'unknown'
order by revenue desc
"""

MONTHLY_SQL = """
select product_category, purchase_month, revenue
from marts.mart_category_monthly
where product_category <> 'unknown'
  and purchase_month between '2017-06-01' and '2018-08-01'
"""


def run(conn) -> str:
    perf = load_df(conn, PERFORMANCE_SQL)
    for col in ("revenue", "avg_item_revenue"):
        perf[col] = perf[col].astype(float)

    top15 = perf.head(15).iloc[::-1]

    # --- Top categories by revenue -------------------------------------------
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=top15["revenue"],
            y=top15["product_category"],
            orientation="h",
            marker_color="#1f77b4",
            text=top15["revenue"].map(lambda v: f"{v / 1e6:.1f}M"),
            textposition="outside",
            hovertemplate="%{y}<br>R$ %{x:,.0f}<br>share %{customdata}%<extra></extra>",
            customdata=top15["revenue_share_pct"],
        )
    )
    fig = base_layout(fig, "Top product categories by revenue (price + freight)", yaxis_title="")
    fig.update_layout(height=520)
    save_fig(fig, "categories_top_revenue")

    # --- Volume share vs revenue share ---------------------------------------
    top20 = perf.head(20)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=top20["item_share_pct"],
            y=top20["revenue_share_pct"],
            mode="markers+text",
            text=top20["product_category"],
            textposition="top center",
            textfont=dict(size=9),
            marker=dict(
                size=top20["avg_item_revenue"] / top20["avg_item_revenue"].max() * 28 + 6,
                color=top20["avg_item_revenue"],
                colorscale="Viridis",
                showscale=True,
                colorbar=dict(title="Avg item<br>revenue (BRL)"),
            ),
            hovertemplate="%{text}<br>item share %{x:.1f}%<br>revenue share %{y:.1f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[0, top20["item_share_pct"].max()],
            y=[0, top20["item_share_pct"].max()],
            mode="lines",
            line=dict(dash="dash", color="grey"),
            name="equal share line",
            showlegend=True,
        )
    )
    fig = base_layout(
        fig, "Item share vs revenue share (top 20 categories)", yaxis_title="Revenue share (%)"
    )
    fig.update_layout(height=560, xaxis_title="Item share (%)")
    save_fig(fig, "categories_volume_vs_value")

    # --- Trend of the top 5 categories ---------------------------------------
    top5 = perf.head(5)["product_category"].tolist()
    monthly = load_df(conn, MONTHLY_SQL)
    monthly["purchase_month"] = pd.to_datetime(monthly["purchase_month"])
    monthly["revenue"] = monthly["revenue"].astype(float)
    fig = go.Figure()
    for category in top5:
        subset = monthly[monthly["product_category"] == category]
        fig.add_trace(
            go.Scatter(
                x=subset["purchase_month"],
                y=subset["revenue"],
                name=category,
                mode="lines",
            )
        )
    fig = base_layout(fig, "Monthly revenue of the top 5 categories", yaxis_title="Revenue (BRL)")
    save_fig(fig, "categories_top5_trend")

    # --- Highest average item price ------------------------------------------
    pricey = perf.nlargest(10, "avg_item_revenue").iloc[::-1]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=pricey["avg_item_revenue"],
            y=pricey["product_category"],
            orientation="h",
            marker_color="#9467bd",
            text=pricey["avg_item_revenue"].map(lambda v: f"R$ {v:,.0f}"),
            textposition="outside",
        )
    )
    fig = base_layout(
        fig, "Highest average item price (categories with >= 100 items)", yaxis_title=""
    )
    fig.update_layout(height=420)
    save_fig(fig, "categories_avg_item_price")

    small = perf[perf["items"] >= 100]
    pricey_small = small.nlargest(5, "avg_item_revenue")
    top_share = float(perf["revenue_share_pct"].head(10).sum())
    low_vol_high_price = pricey_small["product_category"].tolist()

    return f"""## Product categories

- Top category by revenue: {perf.iloc[0]["product_category"]}
  ({fmt_brl(perf.iloc[0]["revenue"])}, {fmt_pct(perf.iloc[0]["revenue_share_pct"])} of revenue).
- The 10 largest categories concentrate {fmt_pct(top_share)} of item revenue;
  the category long tail is real but the head dominates.
- Highest average item price (>=100 items): {", ".join(low_vol_high_price)}.
- Item share and revenue share diverge for several categories (points above the
  diagonal = value-heavy, below = volume-heavy): see categories_volume_vs_value.html.
- Charts: analysis/output/categories_top_revenue.html, categories_volume_vs_value.html,
  categories_top5_trend.html, categories_avg_item_price.html.
"""
