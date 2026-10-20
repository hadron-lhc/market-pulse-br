"""Executive dashboard over the dbt marts.

Run from the repository root:

    streamlit run dashboard/app.py

Every number shown here comes from the analytics marts; the app contains no
business logic of its own beyond presentation-time filtering of aggregates.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ecommerce_intel.analysis._common import get_conn, load_df

st.set_page_config(
    page_title="E-commerce Intelligence Platform",
    page_icon="📊",
    layout="wide",
)

MONTHLY_REVENUE = """
select purchase_month, orders, customers, items_sold, revenue, avg_order_value
from marts.mart_monthly_revenue order by purchase_month
"""
MONTHLY_DELIVERY = """
select purchase_month, delivered_orders, median_delivery_days, p90_delivery_days,
       late_rate_pct
from marts.mart_delivery_monthly order by purchase_month
"""
CATEGORY_PERF = """
select product_category, items, orders, revenue, revenue_share_pct,
       avg_item_revenue, avg_review_score
from marts.mart_category_performance
where product_category <> 'unknown'
order by revenue desc limit 20
"""
CATEGORY_DELIVERY = """
select product_category, delivered_orders, median_delivery_days, late_rate_pct
from marts.mart_delivery_by_category where has_min_sample
"""
CATEGORY_REVIEWS = """
select product_category, reviews, avg_review_score, pct_low_reviews
from marts.mart_review_by_category where reviews >= 50
"""
SELLERS = """
select seller_id, seller_state, orders, revenue, revenue_share_pct,
       avg_delivery_days, late_rate_pct, avg_review_score, has_min_sample
from marts.mart_seller_performance
"""
DELIVERY_STATE = """
select customer_state, delivered_orders, median_delivery_days, late_rate_pct
from marts.mart_delivery_by_state where has_min_sample
order by late_rate_pct desc
"""
REVIEWS_STATE = """
select customer_state, reviews, avg_review_score, pct_low_reviews
from marts.mart_review_by_state where has_min_sample
order by avg_review_score
"""
PAYMENT_MIX = """
select payment_type, purchase_month, orders, payment_value
from marts.mart_payment_mix
"""
INSTALLMENTS = """
select installment_bin, bin_order, orders, median_order_value, avg_order_value
from marts.mart_payment_installments order by bin_order
"""
REVIEW_LATENESS = """
select lateness_bucket, bucket_order, review_score, reviews
from marts.mart_review_by_lateness
"""
COHORTS = """
select cohort_month, months_since_first_purchase, customers_with_order
from marts.mart_customer_cohorts
where cohort_month between '2017-01-01' and '2018-06-01'
"""
KPI_OVERVIEW = "select * from marts.mart_kpi_overview"


@st.cache_data(ttl=600, show_spinner="Loading marts from PostgreSQL…")
def load_data() -> dict[str, pd.DataFrame]:
    conn = get_conn()
    try:
        data = {
            "monthly_revenue": load_df(conn, MONTHLY_REVENUE),
            "monthly_delivery": load_df(conn, MONTHLY_DELIVERY),
            "category_perf": load_df(conn, CATEGORY_PERF),
            "category_delivery": load_df(conn, CATEGORY_DELIVERY),
            "category_reviews": load_df(conn, CATEGORY_REVIEWS),
            "sellers": load_df(conn, SELLERS),
            "delivery_state": load_df(conn, DELIVERY_STATE),
            "reviews_state": load_df(conn, REVIEWS_STATE),
            "payment_mix": load_df(conn, PAYMENT_MIX),
            "installments": load_df(conn, INSTALLMENTS),
            "review_lateness": load_df(conn, REVIEW_LATENESS),
            "cohorts": load_df(conn, COHORTS),
            "kpi": load_df(conn, KPI_OVERVIEW),
        }
    finally:
        conn.close()
    for frame in data.values():
        for col in frame.columns:
            if col.endswith("_month") or col == "cohort_month":
                frame[col] = pd.to_datetime(frame[col])
    return data


def fnum(value: float, decimals: int = 0) -> str:
    return f"{value:,.{decimals}f}"


try:
    data = load_data()
except Exception as exc:  # pragma: no cover - shown in the UI
    st.error(
        "Could not load the analytics marts. Is PostgreSQL running and "
        f"are PG* settings correct? ({exc})"
    )
    st.stop()

mr: pd.DataFrame = data["monthly_revenue"]
md: pd.DataFrame = data["monthly_delivery"]
kpi = data["kpi"].iloc[0]

# --- Sidebar filters ----------------------------------------------------------
st.sidebar.header("Filters")
month_min = pd.Timestamp(mr["purchase_month"].min())
month_max = pd.Timestamp(mr["purchase_month"].max())
month_range = st.sidebar.slider(
    "Purchase months",
    min_value=month_min.to_pydatetime(),
    max_value=month_max.to_pydatetime(),
    value=(pd.Timestamp("2017-06-01").to_pydatetime(), month_max.to_pydatetime()),
    format="YYYY-MM",
)
state_options = ["All"] + sorted(data["delivery_state"]["customer_state"].tolist())
state = st.sidebar.selectbox("Customer state (delivery & reviews)", state_options)
top_n = st.sidebar.slider("Top categories / sellers shown", 5, 20, 10)

period_mr = mr[
    (mr["purchase_month"] >= pd.Timestamp(month_range[0]))
    & (mr["purchase_month"] <= pd.Timestamp(month_range[1]))
]
period_md = md[
    (md["purchase_month"] >= pd.Timestamp(month_range[0]))
    & (md["purchase_month"] <= pd.Timestamp(month_range[1]))
]

st.title("E-commerce Intelligence Platform")
st.caption(
    "Olist Brazilian E-Commerce Public Dataset · revenue = item price + freight, "
    "canceled/unavailable excluded · delivery metrics use delivered orders with a "
    "timestamp · definitions in docs/metric_definitions.md"
)

if period_mr.empty:
    st.info("No orders in the selected month range.")
    st.stop()

# --- KPI row ------------------------------------------------------------------
c1, c2, c3, c4, c5, c6 = st.columns(6)
revenue = float(period_mr["revenue"].sum())
orders = int(period_mr["orders"].sum())
c1.metric("Revenue (period)", f"R$ {fnum(revenue)}")
c2.metric("Orders (period)", fnum(orders))
c3.metric("AOV (period)", f"R$ {fnum(revenue / orders, 2)}")
if not period_md.empty:
    late = float(
        (
            period_md["late_rate_pct"].astype(float) * period_md["delivered_orders"].astype(float)
        ).sum()
        / period_md["delivered_orders"].astype(float).sum()
    )
    c4.metric("Late rate (period)", f"{late:.1f}%")
    c5.metric(
        "Median delivery (period)",
        f"{float(period_md['median_delivery_days'].astype(float).median()):.1f} d",
    )
c6.metric("Repeat customers (all-time)", f"{float(kpi['repeat_customer_rate_pct']):.1f}%")
st.divider()

# --- Tabs ---------------------------------------------------------------------
tab_rev, tab_cat, tab_seller, tab_del, tab_pay, tab_cust = st.tabs(
    ["Revenue", "Categories", "Sellers", "Delivery", "Payments", "Customers"]
)

with tab_rev:
    left, right = st.columns(2)
    with left:
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=period_mr["purchase_month"],
                y=period_mr["revenue"],
                name="Revenue",
                marker_color="#1f77b4",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=period_mr["purchase_month"],
                y=period_mr["orders"],
                name="Orders",
                yaxis="y2",
                mode="lines+markers",
                line=dict(color="#ff7f0e"),
            )
        )
        fig.update_layout(
            template="plotly_white",
            height=380,
            title="Revenue and orders by month",
            yaxis2=dict(overlaying="y", side="right", title="Orders"),
            margin=dict(t=50, b=30),
        )
        st.plotly_chart(fig, width="stretch")
    with right:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=period_mr["purchase_month"],
                y=period_mr["avg_order_value"].astype(float),
                mode="lines+markers",
                line=dict(color="#2ca02c"),
            )
        )
        fig.update_layout(
            template="plotly_white",
            height=380,
            title="Average order value by month",
            yaxis_title="AOV (BRL)",
            margin=dict(t=50, b=30),
        )
        st.plotly_chart(fig, width="stretch")

with tab_cat:
    cats: pd.DataFrame = data["category_perf"].copy()
    cats["revenue"] = cats["revenue"].astype(float)
    top = cats.head(top_n).iloc[::-1]
    left, right = st.columns(2)
    with left:
        fig = px.bar(
            top,
            x="revenue",
            y="product_category",
            orientation="h",
            title=f"Top {len(top)} categories by revenue",
            labels={"revenue": "Revenue (BRL)", "product_category": ""},
            template="plotly_white",
            height=440,
        )
        st.plotly_chart(fig, width="stretch")
    with right:
        scatter = cats.head(20).copy()
        scatter["revenue_share_pct"] = scatter["revenue_share_pct"].astype(float)
        scatter["avg_review_score"] = scatter["avg_review_score"].astype(float)
        fig = px.scatter(
            scatter,
            x="revenue_share_pct",
            y="avg_review_score",
            size="orders",
            hover_name="product_category",
            template="plotly_white",
            height=440,
            title="Revenue share vs review score (top 20)",
            labels={
                "revenue_share_pct": "Revenue share (%)",
                "avg_review_score": "Avg review score",
                "orders": "Orders",
            },
        )
        st.plotly_chart(fig, width="stretch")

with tab_seller:
    sellers: pd.DataFrame = data["sellers"].copy()
    sellers["revenue_share_pct"] = sellers["revenue_share_pct"].astype(float)
    cum = sellers.sort_values("revenue", ascending=False)["revenue_share_pct"].cumsum()
    k80 = int((cum >= 80).idxmax()) + 1 if (cum >= 80).any() else len(cum)
    st.caption(
        f"{len(sellers):,} sellers with revenue · top {k80} sellers "
        f"({100 * k80 / len(sellers):.1f}%) produce 80% of revenue."
    )
    top = sellers.head(top_n).iloc[::-1].copy()
    top["revenue"] = top["revenue"].astype(float)
    fig = px.bar(
        top,
        x="revenue",
        y="seller_id",
        orientation="h",
        hover_data=["seller_state", "orders", "avg_review_score"],
        title=f"Top {len(top)} sellers by revenue",
        template="plotly_white",
        height=440,
        labels={"revenue": "Revenue (BRL)", "seller_id": ""},
    )
    st.plotly_chart(fig, width="stretch")

with tab_del:
    left, right = st.columns(2)
    with left:
        fig = px.line(
            period_md,
            x="purchase_month",
            y="late_rate_pct",
            markers=True,
            title="Late rate by purchase month",
            template="plotly_white",
            height=360,
            labels={"late_rate_pct": "Late rate (%)", "purchase_month": ""},
        )
        st.plotly_chart(fig, width="stretch")
    with right:
        states: pd.DataFrame = data["delivery_state"].copy()
        states["late_rate_pct"] = states["late_rate_pct"].astype(float)
        if state != "All":
            states = states[states["customer_state"] == state]
        fig = px.bar(
            states,
            x="customer_state",
            y="late_rate_pct",
            title="Late rate by state (≥100 delivered orders)",
            template="plotly_white",
            height=360,
            labels={"late_rate_pct": "Late rate (%)", "customer_state": ""},
            color_discrete_sequence=["#d62728"],
        )
        st.plotly_chart(fig, width="stretch")
    cats_d = data["category_delivery"].copy()
    cats_d["late_rate_pct"] = cats_d["late_rate_pct"].astype(float)
    fig = px.bar(
        cats_d.sort_values("late_rate_pct").tail(12),
        x="late_rate_pct",
        y="product_category",
        orientation="h",
        title="Categories with the highest late rate (≥100 delivered orders)",
        template="plotly_white",
        height=420,
        labels={"late_rate_pct": "Late rate (%)", "product_category": ""},
    )
    st.plotly_chart(fig, width="stretch")

with tab_pay:
    mix: pd.DataFrame = data["payment_mix"].copy()
    mix["orders"] = mix["orders"].astype(float)
    mix_period = (
        mix[
            (mix["purchase_month"] >= pd.Timestamp(month_range[0]))
            & (mix["purchase_month"] <= pd.Timestamp(month_range[1]))
        ]
        .groupby("payment_type", as_index=False)["orders"]
        .sum()
    )
    mix_period["share"] = 100 * mix_period["orders"] / mix_period["orders"].sum()
    left, right = st.columns(2)
    with left:
        fig = px.bar(
            mix_period,
            x="payment_type",
            y="share",
            title="Payment methods in selected period",
            template="plotly_white",
            height=360,
            labels={"share": "Share of orders mentioning type (%)", "payment_type": ""},
            color_discrete_sequence=["#1f77b4"],
        )
        st.plotly_chart(fig, width="stretch")
    with right:
        inst = data["installments"].copy()
        inst["median_order_value"] = inst["median_order_value"].astype(float)
        fig = px.bar(
            inst,
            x="installment_bin",
            y="median_order_value",
            title="Median order value by credit-card installments",
            template="plotly_white",
            height=360,
            labels={"median_order_value": "Median order value (BRL)", "installment_bin": ""},
            color_discrete_sequence=["#2ca02c"],
        )
        st.plotly_chart(fig, width="stretch")
    st.caption(
        "Association only: higher installments track higher order values; "
        "no causal claim (see analysis/insights.md, finding 7)."
    )

with tab_cust:
    left, right = st.columns(2)
    with left:
        lat: pd.DataFrame = data["review_lateness"].copy()
        lat["reviews"] = lat["reviews"].astype(float)
        pivot = lat.pivot_table(
            index="bucket_order",
            columns="review_score",
            values="reviews",
            aggfunc="sum",
            fill_value=0,
        )
        labels = (
            lat.drop_duplicates("bucket_order")
            .set_index("bucket_order")["lateness_bucket"]
            .to_dict()
        )
        fig = go.Figure()
        for score in pivot.columns:
            fig.add_trace(
                go.Bar(name=f"Score {score}", x=[labels[i] for i in pivot.index], y=pivot[score])
            )
        fig.update_layout(
            barmode="stack",
            template="plotly_white",
            height=380,
            title="Review scores by delivery lateness",
            xaxis_title="",
            yaxis_title="Reviews",
        )
        st.plotly_chart(fig, width="stretch")
    with right:
        rev_states: pd.DataFrame = data["reviews_state"].copy()
        rev_states["avg_review_score"] = rev_states["avg_review_score"].astype(float)
        if state != "All":
            rev_states = rev_states[rev_states["customer_state"] == state]
        fig = px.bar(
            rev_states,
            x="customer_state",
            y="avg_review_score",
            title="Average review score by state (≥50 reviews)",
            template="plotly_white",
            height=380,
            labels={"avg_review_score": "Average score", "customer_state": ""},
            color_discrete_sequence=["#9467bd"],
        )
        st.plotly_chart(fig, width="stretch")
    cohorts: pd.DataFrame = data["cohorts"].copy()
    pivot = cohorts.pivot_table(
        index="cohort_month",
        columns="months_since_first_purchase",
        values="customers_with_order",
        aggfunc="sum",
    )
    last_month = pd.Timestamp("2018-08-01")
    for cohort in pivot.index:
        horizon = (last_month.year - cohort.year) * 12 + (last_month.month - cohort.month)
        for col in pivot.columns:
            if col > horizon - 3:
                pivot.loc[cohort, col] = float("nan")
    fig = px.imshow(
        pivot,
        labels=dict(x="Months since first purchase", y="Cohort month", color="Active customers"),
        x=[str(int(c)) for c in pivot.columns],
        y=[d.strftime("%Y-%m") for d in pivot.index],
        color_continuous_scale="Blues",
        aspect="auto",
        title="Cohort activity (recent cells censored where the observation window is incomplete)",
    )
    fig.update_layout(height=420, template="plotly_white")
    st.plotly_chart(fig, width="stretch")

st.sidebar.divider()
st.sidebar.caption(
    "Data: Olist Brazilian E-Commerce Public Dataset (Kaggle). "
    "Pipeline: ingestion → dbt → marts. This app reads marts only."
)
