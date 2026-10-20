"""Seller analytics: concentration, leaders, delivery/review association."""

from __future__ import annotations

import plotly.graph_objects as go

from ._common import base_layout, fmt_int, fmt_pct, load_df, save_fig

SELLERS_SQL = """
select seller_id, seller_state, items, orders, revenue, revenue_share_pct,
       avg_item_revenue, avg_delivery_days, late_rate_pct, avg_review_score,
       has_min_sample
from marts.mart_seller_performance
order by revenue desc
"""


def run(conn) -> str:
    df = load_df(conn, SELLERS_SQL)
    df["revenue"] = df["revenue"].astype(float)
    df["revenue_share_pct"] = df["revenue_share_pct"].astype(float)
    df = df.sort_values("revenue", ascending=False).reset_index(drop=True)
    df["cum_share"] = df["revenue_share_pct"].cumsum()

    # --- Concentration curve ---------------------------------------------------
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df.index + 1,
            y=df["cum_share"],
            mode="lines",
            line=dict(color="#1f77b4", width=2),
            hovertemplate="Top %{x} sellers<br>%{y:.1f}% of revenue<extra></extra>",
        )
    )
    n = len(df)
    for pct in (50, 80):
        k = int((df["cum_share"] >= pct).idxmax()) + 1
        fig.add_vline(x=k, line_dash="dot", line_color="grey")
        fig.add_annotation(
            x=k,
            y=pct,
            text=f"top {k} sellers = {pct}%",
            showarrow=False,
            xanchor="left",
        )
    fig = base_layout(
        fig,
        "Seller revenue concentration (cumulative share)",
        yaxis_title="Cumulative revenue share (%)",
    )
    fig.update_layout(xaxis_title="Sellers (ranked by revenue)", xaxis_type="log")
    save_fig(fig, "sellers_concentration_curve")

    # --- Top 15 sellers --------------------------------------------------------
    top15 = df.head(15).iloc[::-1]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=top15["revenue"],
            y=top15["seller_id"].str[:10] + "…",
            orientation="h",
            marker_color="#2ca02c",
            customdata=top15[["seller_state", "orders", "revenue_share_pct"]],
            hovertemplate=(
                "%{y} (%{customdata[0]})<br>R$ %{x:,.0f}<br>"
                "%{customdata[1]} orders<br>share %{customdata[2]:.3f}%<extra></extra>"
            ),
        )
    )
    fig = base_layout(fig, "Top 15 sellers by revenue", yaxis_title="")
    fig.update_layout(height=480)
    save_fig(fig, "sellers_top15")

    # --- Delivery vs review for representative sellers ------------------------
    sample = df[
        df["has_min_sample"] & df["avg_delivery_days"].notna() & df["avg_review_score"].notna()
    ].copy()
    sample["avg_delivery_days"] = sample["avg_delivery_days"].astype(float)
    sample["avg_review_score"] = sample["avg_review_score"].astype(float)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=sample["avg_delivery_days"],
            y=sample["avg_review_score"],
            mode="markers",
            marker=dict(
                size=sample["orders"].astype(float).clip(lower=20) / 8 + 4,
                color=sample["late_rate_pct"].astype(float),
                colorscale="Reds",
                reversescale=True,
                colorbar=dict(title="Late rate (%)"),
                line=dict(width=0.5, color="white"),
            ),
            customdata=sample[["seller_state", "orders"]],
            hovertemplate=(
                "%{customdata[0]}<br>avg delivery %{x:.1f} d<br>"
                "avg score %{y:.2f}<br>%{customdata[1]} orders<extra></extra>"
            ),
        )
    )
    fig = base_layout(
        fig,
        "Sellers with >=30 orders: delivery time vs review score",
        yaxis_title="Avg review score of containing orders",
    )
    fig.update_layout(xaxis_title="Avg delivery days of containing orders")
    save_fig(fig, "sellers_delivery_vs_reviews")

    hhi = float((df["revenue_share_pct"] ** 2).sum())
    k50 = int((df["cum_share"] >= 50).idxmax()) + 1
    k80 = int((df["cum_share"] >= 80).idxmax()) + 1
    corr = float(sample["avg_delivery_days"].corr(sample["avg_review_score"]))

    return f"""## Sellers

- {fmt_int(n)} sellers generated revenue; top 50% of revenue comes from only
  {fmt_int(k50)} sellers ({fmt_pct(100 * k50 / n)} of sellers), 80% from {fmt_int(k80)}.
- Herfindahl-Hirschman index on revenue shares: {hhi:,.0f} (0-10,000 scale) —
  moderate concentration, not a monopoly tail.
- Among sellers with >=30 orders, the correlation between average delivery time
  and average review score of their orders is r = {corr:.2f}
  (association only; multi-seller orders share one delivery outcome).
- Charts: analysis/output/sellers_concentration_curve.html, sellers_top15.html,
  sellers_delivery_vs_reviews.html.
"""
