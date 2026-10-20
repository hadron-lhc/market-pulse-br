"""Review analytics: score distribution, lateness association (with effect size)."""

from __future__ import annotations

import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import mannwhitneyu

from ._common import base_layout, fmt_int, fmt_pct, load_df, save_fig

LATENESS_SQL = """
select lateness_bucket, bucket_order, review_score, reviews
from marts.mart_review_by_lateness
"""

SCORES_SQL = """
select review_score, is_late, is_delivered_measured
from intermediate.int_order_facts
where has_review
"""

STATE_SQL = """
select customer_state, reviews, avg_review_score, pct_low_reviews,
       late_rate_pct, has_min_sample
from marts.mart_review_by_state
where has_min_sample
order by avg_review_score
"""


def run(conn) -> str:
    lateness = load_df(conn, LATENESS_SQL)
    lateness["reviews"] = lateness["reviews"].astype(float)
    states = load_df(conn, STATE_SQL)
    for col in ("avg_review_score", "pct_low_reviews", "late_rate_pct"):
        states[col] = states[col].astype(float)

    # --- Score distribution ----------------------------------------------------
    score_totals = lateness.groupby("review_score", as_index=False)["reviews"].sum()
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=score_totals["review_score"],
            y=score_totals["reviews"],
            text=(100 * score_totals["reviews"] / score_totals["reviews"].sum()).map(
                lambda v: f"{v:.1f}%"
            ),
            textposition="outside",
            marker_color=["#d62728", "#ff7f0e", "#bcbd22", "#2ca02c", "#1f77b4"],
        )
    )
    fig = base_layout(fig, "Review score distribution (deduped reviews)", yaxis_title="Reviews")
    fig.update_layout(showlegend=False, xaxis_title="Review score")
    save_fig(fig, "reviews_score_distribution")

    # --- Scores by lateness bucket ---------------------------------------------
    pivot = lateness.pivot_table(
        index="bucket_order",
        columns="review_score",
        values="reviews",
        aggfunc="sum",
        fill_value=0,
    ).sort_index()
    bucket_labels = (
        lateness.drop_duplicates("bucket_order")
        .set_index("bucket_order")["lateness_bucket"]
        .to_dict()
    )
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Counts", "Within-bucket %"))
    for score in pivot.columns:
        fig.add_trace(
            go.Bar(
                name=f"Score {score}", x=[bucket_labels[i] for i in pivot.index], y=pivot[score]
            ),
            row=1,
            col=1,
        )
    pct = pivot.div(pivot.sum(axis=1), axis=0) * 100
    for score in pct.columns:
        fig.add_trace(
            go.Bar(
                name=f"Score {score}",
                x=[bucket_labels[i] for i in pct.index],
                y=pct[score],
                showlegend=False,
            ),
            row=1,
            col=2,
        )
    fig.update_layout(
        barmode="stack",
        template="plotly_white",
        title="Review scores by delivery lateness",
        height=480,
    )
    fig.update_yaxes(title_text="Reviews", row=1, col=1)
    fig.update_yaxes(title_text="% within bucket", row=1, col=2)
    save_fig(fig, "reviews_scores_by_lateness")

    # --- State view --------------------------------------------------------------
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=states["customer_state"],
            y=states["avg_review_score"],
            marker_color="#1f77b4",
            customdata=states[["reviews", "late_rate_pct"]],
            hovertemplate=(
                "%{x}<br>avg score %{y:.2f}<br>%{customdata[0]} reviews<br>"
                "late rate %{customdata[1]:.1f}%<extra></extra>"
            ),
        )
    )
    overall = float(
        (states["avg_review_score"] * states["reviews"]).sum() / states["reviews"].sum()
    )
    fig.add_hline(
        y=overall,
        line_dash="dash",
        line_color="grey",
        annotation_text=f"review-weighted avg {overall:.2f}",
    )
    fig = base_layout(
        fig, "Average review score by state (>=50 reviews)", yaxis_title="Average review score"
    )
    fig.update_layout(xaxis_title="State")
    save_fig(fig, "reviews_avg_score_by_state")

    # --- Statistical test: late vs on time ---------------------------------------
    raw = load_df(conn, SCORES_SQL)
    raw["review_score"] = raw["review_score"].astype(int)
    raw["is_late"] = raw["is_late"].astype(bool)
    measured = raw[raw["is_delivered_measured"].astype(bool)]
    late = measured.loc[measured["is_late"], "review_score"].astype(int)
    on_time = measured.loc[~measured["is_late"], "review_score"].astype(int)
    stat, pvalue = mannwhitneyu(late, on_time, alternative="two-sided")
    rank_biserial = 2 * stat / (len(late) * len(on_time)) - 1
    p_text = "p < 1e-16" if pvalue < 1e-16 else f"p = {pvalue:.3g}"
    p1_late = float((late <= 2).mean())
    p1_ontime = float((on_time <= 2).mean())
    risk_ratio = p1_late / p1_ontime
    pct_five_star = 100 * float((raw["review_score"] == 5).mean())
    avg_score = float(raw["review_score"].mean())

    return f"""## Reviews and customer experience

- Score distribution is top-heavy: {fmt_pct(pct_five_star)} five-star reviews;
  average score {avg_score:.2f}.
- Late deliveries carry much more low-scoring mass: {fmt_pct(100 * p1_late)} of
  reviews on late orders are <=2 stars vs {fmt_pct(100 * p1_ontime)} on time
  (risk ratio {risk_ratio:.1f}x).
- Mann-Whitney U on scores (late n={fmt_int(len(late))} vs on-time n={fmt_int(len(on_time))}):
  {p_text}, rank-biserial correlation {rank_biserial:.2f} — a large,
  practically meaningful association. This remains associational: late orders
  can differ in region and category mix.
- Regional spread: worst reviewed states (>=50 reviews) are
  {", ".join(states["customer_state"].head(3))}.
- Charts: analysis/output/reviews_score_distribution.html, reviews_scores_by_lateness.html,
  reviews_avg_score_by_state.html.
"""
