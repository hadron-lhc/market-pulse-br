"""Payment analytics: method mix, order values, installment association."""

from __future__ import annotations

import plotly.graph_objects as go
from scipy.stats import spearmanr

from ._common import base_layout, fmt_brl, fmt_int, fmt_pct, load_df, save_fig

MIX_SQL = """
select payment_type,
       sum(orders) as orders,
       sum(payment_value) as payment_value
from marts.mart_payment_mix
group by payment_type
order by orders desc
"""

INSTALLMENTS_SQL = """
select installment_bin, bin_order, orders, avg_order_value, median_order_value
from marts.mart_payment_installments
order by bin_order
"""

INSTALLMENT_CORR_SQL = """
select max_installments, order_revenue
from intermediate.int_order_facts f
where is_revenue_order
  and has_credit_card
  and max_installments is not null
"""

ORDER_VALUE_BY_TYPE_SQL = """
select primary_payment_type,
       count(*) as orders,
       percentile_cont(0.5) within group (order by order_revenue)::numeric as median_order_value,
       round(avg(order_revenue), 2) as avg_order_value
from intermediate.int_order_facts
where is_revenue_order
group by primary_payment_type
order by orders desc
"""


def run(conn) -> str:
    mix = load_df(conn, MIX_SQL)
    mix["orders"] = mix["orders"].astype(float)
    mix["share"] = 100 * mix["orders"] / mix["orders"].sum()

    by_type = load_df(conn, ORDER_VALUE_BY_TYPE_SQL)
    for col in ("median_order_value", "avg_order_value"):
        by_type[col] = by_type[col].astype(float)

    # --- Payment mix -----------------------------------------------------------
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=mix["payment_type"],
            y=mix["share"],
            text=mix["share"].map(lambda v: f"{v:.1f}%"),
            textposition="outside",
            marker_color="#1f77b4",
            hovertemplate="%{x}<br>%{y:.1f}% of payment-type order mentions<extra></extra>",
        )
    )
    fig = base_layout(
        fig,
        "Payment methods: share of orders containing the type",
        yaxis_title="Share of orders (%)",
    )
    fig.update_layout(showlegend=False)
    save_fig(fig, "payments_method_mix")

    # --- Median vs average order value by primary payment type -----------------
    order = by_type["primary_payment_type"].tolist()
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="Median order value",
            x=order,
            y=by_type["median_order_value"],
            marker_color="#1f77b4",
        )
    )
    fig.add_trace(
        go.Bar(
            name="Average order value",
            x=order,
            y=by_type["avg_order_value"],
            marker_color="#ff7f0e",
        )
    )
    fig = base_layout(fig, "Order value by primary payment method", yaxis_title="Order value (BRL)")
    fig.update_layout(barmode="group")
    save_fig(fig, "payments_order_value_by_type")

    # --- Installments ----------------------------------------------------------
    inst = load_df(conn, INSTALLMENTS_SQL)
    for col in ("avg_order_value", "median_order_value"):
        inst[col] = inst[col].astype(float)
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="Median order value",
            x=inst["installment_bin"],
            y=inst["median_order_value"],
            marker_color="#2ca02c",
        )
    )
    fig.add_trace(
        go.Bar(
            name="Average order value",
            x=inst["installment_bin"],
            y=inst["avg_order_value"],
            marker_color="#8c564b",
        )
    )
    fig = base_layout(
        fig,
        "Credit-card orders: order value by installment bin",
        yaxis_title="Order value (BRL)",
    )
    fig.update_layout(barmode="group", xaxis_title="Max installments on the order")
    save_fig(fig, "payments_installments_vs_value")

    corr_df = load_df(conn, INSTALLMENT_CORR_SQL)
    rho, pvalue = spearmanr(
        corr_df["max_installments"].astype(float),
        corr_df["order_revenue"].astype(float),
    )
    p_text = "p < 1e-16" if pvalue < 1e-16 else f"p = {pvalue:.3g}"

    credit_share = float(mix.loc[mix["payment_type"] == "credit_card", "share"].iloc[0])
    return f"""## Payments

- Credit cards appear on {fmt_pct(credit_share)} of orders (boleto second);
  vouchers are present on a small minority.
- Median order value by primary payment method differs materially
  (boleto median {fmt_brl(float(by_type.loc[by_type.primary_payment_type == "boleto", "median_order_value"].iloc[0]))}
  vs credit card {fmt_brl(float(by_type.loc[by_type.primary_payment_type == "credit_card", "median_order_value"].iloc[0]))}).
- Installments and order value: Spearman rho = {rho:.2f} ({p_text} on n={fmt_int(len(corr_df))})
  — a strong monotone ASSOCIATION, not evidence that installments cause larger
  baskets; product mix and price drive both.
- Charts: analysis/output/payments_method_mix.html, payments_order_value_by_type.html,
  payments_installments_vs_value.html.
"""
