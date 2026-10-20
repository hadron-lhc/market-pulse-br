"""Customer behaviour: repeat purchasing and cohort activity."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from ._common import base_layout, fmt_int, fmt_pct, load_df, save_fig

FREQUENCY_SQL = """
select orders_per_customer
from (
    select customer_unique_id, count(*) as orders_per_customer
    from intermediate.int_order_facts
    where is_revenue_order
    group by customer_unique_id
) t
"""

COHORT_SQL = """
select cohort_month, months_since_first_purchase,
       customers_with_order, orders
from marts.mart_customer_cohorts
where cohort_month between '2017-01-01' and '2018-06-01'
"""

SECOND_ORDER_SQL = """
with ranked as (
    select
        customer_unique_id,
        purchase_date,
        row_number() over (
            partition by customer_unique_id order by order_purchase_timestamp
        ) as rn
    from intermediate.int_order_facts
    where is_revenue_order
),
pairs as (
    select
        a.customer_unique_id,
        (b.purchase_date - a.purchase_date) as days_to_second_order
    from ranked a
    join ranked b
      on a.customer_unique_id = b.customer_unique_id
     and a.rn = 1 and b.rn = 2
)
select
    count(*) as repeat_customers,
    percentile_cont(0.5) within group (order by days_to_second_order)::numeric as median_days,
    percentile_cont(0.9) within group (order by days_to_second_order)::numeric as p90_days
from pairs
"""


def run(conn) -> str:
    freq = load_df(conn, FREQUENCY_SQL)["orders_per_customer"].astype(int)

    # --- Orders per customer ----------------------------------------------------
    counts = freq.value_counts().sort_index().head(6)
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=[f"{k} order{'s' if k > 1 else ''}" for k in counts.index],
            y=counts.values,
            text=[fmt_pct(100 * v / len(freq)) for v in counts.values],
            textposition="outside",
            marker_color="#1f77b4",
        )
    )
    fig = base_layout(
        fig, "Orders per customer (customer_unique_id, revenue orders)", yaxis_title="Customers"
    )
    fig.update_layout(showlegend=False)
    save_fig(fig, "retention_orders_per_customer")

    # --- Cohort heatmap ----------------------------------------------------------
    cohorts = load_df(conn, COHORT_SQL)
    cohorts["cohort_month"] = pd.to_datetime(cohorts["cohort_month"])
    pivot = cohorts.pivot_table(
        index="cohort_month",
        columns="months_since_first_purchase",
        values="customers_with_order",
        aggfunc="sum",
    ).astype(float)
    # Censor cells whose observation window is not fully observable
    # (the dataset effectively ends Aug-2018; keep >=3 months of horizon).
    last_month = pd.Timestamp("2018-08-01")
    for cohort in pivot.index:
        horizon = (last_month.year - cohort.year) * 12 + (last_month.month - cohort.month)
        for col in pivot.columns:
            if col > horizon - 3:
                pivot.loc[cohort, col] = np.nan

    fig = px.imshow(
        pivot,
        labels=dict(x="Months since first purchase", y="Cohort month", color="Active customers"),
        x=[str(int(c)) for c in pivot.columns],
        y=[d.strftime("%Y-%m") for d in pivot.index],
        color_continuous_scale="Blues",
        aspect="auto",
        title="Cohort activity: customers with an order by months since first purchase",
    )
    fig.update_layout(height=520, template="plotly_white")
    save_fig(fig, "retention_cohort_heatmap")

    second = load_df(conn, SECOND_ORDER_SQL).iloc[0]
    repeat_rate = 100 * float((freq > 1).mean())
    one_and_done = fmt_pct(100 * float((freq == 1).mean()))

    return f"""## Customer behaviour

- {fmt_int(len(freq))} customers placed a revenue order;
  {one_and_done} of them ordered exactly once within the observed window.
- Repeat-customer rate: {fmt_pct(repeat_rate)} (>=2 orders).
- Repeat customers needed a median of {int(second["median_days"])} days to their
  second order (p90 {int(second["p90_days"])} days).
- Cohort heatmap shows activity decaying within the first months after the first
  purchase; late cohorts are censored (dataset ends Aug-2018) and marked blank.
- Charts: analysis/output/retention_orders_per_customer.html,
  retention_cohort_heatmap.html.
"""
