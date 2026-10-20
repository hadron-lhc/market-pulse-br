# Analytical Insights — Olist Brazilian E-Commerce (2016-09 → 2018-08)

All numbers below are computed from the dbt marts built on the full Olist
dataset by `python -m ecommerce_intel.analysis.run_all` (see
`analysis/output/computed_findings.md`, which is regenerated on every run).
Charts referenced here live in `analysis/output/*.html`. Metric definitions
and populations are specified in [docs/metric_definitions.md](../docs/metric_definitions.md).

---

## 1. Revenue is growing, but order value is not

**Question.** Is the marketplace growing on volume or on basket size?

**Metrics.** Revenue orders and revenue (item price + freight, canceled and
unavailable excluded); average order value (AOV) and median order value.

**Result.** 98,199 revenue orders worth R$ 15.74M. Revenue in 2018 was 21.2%
above 2017 (Jan–Aug comparable window), driven by order volume. AOV is
R$ 160.24 while the median order is R$ 105.28 — 4.3% of orders exceed R$ 500
and pull the mean up. November 2017 alone contributed R$ 1.17M (7,421 orders).

**Why it matters.** Growth is a volume story. Any initiative that assumes
"customers are trading up" is not supported by the data.

**Limitations.** The dataset effectively starts Jan-2017 (Sep–Dec 2016 has
almost no orders) and ends Aug-2018; there are no costs, so this is revenue,
not margin.

**Recommendation.** Track volume and AOV as separate KPIs; use the median, not
the mean, when reasoning about a "typical" order.

## 2. The category head is stable — and health & beauty leads

**Question.** Which categories drive item sales, and do volume leaders equal
value leaders?

**Metrics.** Category revenue and item share (`mart_category_performance`).

**Result.** `health_beauty` leads with R$ 1.44M (9.1% of revenue). The top 10
categories concentrate 62.3% of item revenue while the tail (>60 categories)
is thin. Volume share and revenue share diverge systematically: categories
above the diagonal in `categories_volume_vs_value.html` (e.g. computers,
`home_appliances_2`) sell few items at high average prices, categories below
it (e.g. `bed_bath_table`, `sports_leisure`) move volume at modest prices.

**Why it matters.** Catalog and marketing decisions should be made per value
profile, not per raw unit volume.

**Limitations.** Category assignment is per product; multi-category orders
count once per category, so category order counts are not additive.

**Recommendation.** Manage the two profiles separately: availability and price
competition for high-volume/low-value categories, assortment depth and margin
for low-volume/high-value ones.

## 3. Seller base: long tail, moderate concentration

**Question.** How concentrated is supply, and can seller-level delivery or
reviews be compared fairly?

**Metrics.** Cumulative revenue share, HHI (`mart_seller_performance`).

**Result.** 3,053 sellers earned revenue; 135 sellers (4.4%) account for half
of it, 558 for 80%. HHI ≈ 35 — moderate concentration. Among sellers with at
least 30 orders, average delivery time of containing orders correlates with
average review score at r = −0.50.

**Why it matters.** A small operational core carries the marketplace; seller
scorecards are usable only above a sample threshold.

**Limitations.** Delivery and review figures are order-level: multi-seller
orders share one outcome, so they are associations, not seller quality
scores. The dataset carries no cost or return data.

**Recommendation.** Set explicit minimum-sample rules (we flag `has_min_sample`
at 30 orders) before ranking sellers on delivery or reviews.

## 4. Lateness is episodic — peak periods break the promise

**Question.** How stable is delivery performance over time?

**Metrics.** Late rate by purchase month (late = delivered on a later calendar
day than estimated; delivered orders with timestamps only).

**Result.** Overall late rate is 6.77%, median delivery 10.2 days, p90 23.1
days. The monthly rate is ~3% in calm periods but spikes exactly when volume
peaks: Nov-2017 (12.4%), Feb-2018 (14.1%), Mar-2018 (19.0%).

**Why it matters.** Delivery promises degrade at peak load — the same months
that contribute the most revenue. Lateness risk is predictable from the
calendar, not random.

**Limitations.** Estimated dates are Olist's own promises; a "late" label is
relative to a promise that itself varies by region and period.

**Recommendation.** Treat peak months as capacity events: plan carrier
commitments and set more conservative promised dates before Nov/Feb spikes.

## 5. Geography: lateness is not the same as slowness

**Question.** Where are deliveries failing relative to promises?

**Metrics.** Late rate and median delivery days by customer state
(`mart_delivery_by_state`, ≥100 delivered orders).

**Result.** The Northeast carries the highest late rates — AL 21.4%, MA 17.4%,
SE 15.2%, CE 13.8% — while SP (4.5%) and PR (4.0%) are the most reliable among
large states; RJ (12.1%) is an outlier among the big three. Crucially, AM is
the *most* on-time state (2.8%) while being the *slowest* (median 25.9 days vs
SP 7.2): promised dates for remote regions are padded, so being "on time" there
means meeting a much longer promise.

**Why it matters.** Operations should manage two different problems: genuine
promise failures (Northeast, RJ) and structurally long transit times (North).

**Limitations.** Regional differences mix carrier networks, seller geography
(sellers are concentrated in the Southeast) and estimate-setting policy; no
causal claim is made here.

**Recommendation.** Track both metrics per state — late rate *and* absolute
transit time — and renegotiate estimates where lateness is high despite padded
promises.

## 6. Category-level lateness is a logistics signal

**Question.** Are late deliveries concentrated in specific product types?

**Metrics.** Late rate by category (`mart_delivery_by_category`, ≥100
delivered orders).

**Result.** Category late rates span roughly 3%–12%: `audio` (11.8%),
`home_confort` (9.4%) and `office_furniture` (8.1%) — bulky goods — sit at the
top, while most services/digital-adjacent and light goods categories are far
below the 6.8% average. Baby (8.1%, n=2,809) is notable for combining volume
with elevated lateness.

**Why it matters.** Bulky categories have a logistics cost profile that the
platform can act on (carrier selection, seller SLAs), unlike generic delays.

**Limitations.** Category lateness also reflects seller location and stock
practices; multi-category orders count in each category.

**Recommendation.** Segment carrier SLAs and handling rules by physical
product profile, starting with bulky categories.

## 7. Installments are a price signal, not a proven cause

**Question.** How do payment methods relate to order value?

**Metrics.** Payment-method mix (`mart_payment_mix`), installment bins
(`mart_payment_installments`), Spearman correlation.

**Result.** Credit cards appear on 75.3% of orders; boleto is second. Median
order value is R$ 109.50 for credit-card-primary orders vs R$ 93.82 for
boleto. Within credit-card orders, max installments and order revenue are
monotonically associated (Spearman ρ = 0.46, n = 75,614, p < 1e-16).

**Why it matters.** Installments plausibly enable higher-ticket purchases — but
the same product mix drives both installment count and price, so the
association is not a causal estimate. No experiment or identification strategy
is available in this dataset.

**Limitations.** Vouchers distort payment totals slightly (see reconciliation
test); there is no interest or credit data.

**Recommendation.** Present the installment–value relationship as descriptive
evidence only; a causal claim would need an experiment (e.g. eligibility
variation) we do not have.

## 8. Late delivery is the dominant driver of poor reviews

**Question.** Are low review scores associated with delivery failures?

**Metrics.** Review score distribution by lateness bucket
(`mart_review_by_lateness`); Mann-Whitney U with rank-biserial effect size.

**Result.** 57.8% of reviews are 5-star (average 4.09). On late orders, 62.4%
of reviews are ≤2 stars, versus 9.3% on on-time orders — a 6.7× risk ratio.
Scores are ordinally much lower for late orders (Mann-Whitney p < 1e-16,
rank-biserial r = −0.64, a large effect). The worst-reviewed states (MA, AL,
SE) overlap with the worst-delivering states.

**Why it matters.** Delivery reliability is the clearest lever on customer
sentiment available in this data; review recovery should prioritize late
orders.

**Limitations.** Observational: lateness co-varies with region and category,
and review propensity is unknown (only ~24% of delivered orders have a review
row in the raw file). Effect size is large enough that confounding would have
to be extreme to erase the association, but causality is not claimed.

**Recommendation.** Trigger proactive service recovery (status updates,
compensation vouchers) on orders that cross their promised date.

## 9. The marketplace is almost entirely one-shot: retention is the gap

**Question.** Is there repeat purchasing?

**Metrics.** Repeat-customer rate on `customer_unique_id`; cohort activity
(`mart_customer_cohorts`).

**Result.** Only 3.04% of customers (2,887 of 94,983) placed two or more
orders inside the observed window; 97.0% ordered exactly once. Repeat
customers nevertheless contribute 5.66% of revenue. Those who did return came
back after a median of 28 days (p90 247 days).

**Why it matters.** Marketplace growth has been acquisition-driven; there is
almost no observed loyalty loop to optimize.

**Limitations.** `customer_unique_id` is Olist's pseudonymous identifier — it
cannot be assumed to equal a person; a household or a user clearing cookies
would look like two one-shot customers. The window is ~2 years with heavy
right-censoring for recent cohorts.

**Recommendation.** Instrument identity resolution and launch a post-purchase
retention program; measure it on the 28-day median-return window, not on
annual metrics.

---

## Cross-cutting caveats

- **No margin data.** Freight is part of revenue collected, but seller costs,
  COGS, returns and refunds are absent — no profit claims anywhere.
- **Populations differ per metric** (revenue orders vs delivered-with-timestamp
  vs reviewed orders). Mixing them silently is the fastest way to produce
  wrong numbers; each metric's population is fixed in
  `docs/metric_definitions.md` and encoded once in `int_order_facts`.
- **Association vs causation.** Findings 3, 7 and 8 are explicitly
  associational. The dataset offers no experimental variation.
