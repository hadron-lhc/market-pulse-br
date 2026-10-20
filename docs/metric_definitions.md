# Metric Definitions

Every KPI below is implemented once — in `int_order_facts` (populations and
order-level measures) or in the named mart — and reused everywhere else.
"Revenue orders" always means `int_order_facts.is_revenue_order`.

## Populations

| Population | Rule | Encoded in |
|---|---|---|
| All orders | every row of `raw.orders` | `stg_orders` |
| Revenue orders | has ≥ 1 item AND status ∉ {canceled, unavailable} | `is_revenue_order` |
| Delivered measured | status = delivered AND delivered timestamp present | `is_delivered_measured` |
| Reviewed orders | a review exists after deduplication | `has_review` |

## Revenue and orders

| Metric | Definition | Grain | Null handling | Known limitations |
|---|---|---|---|---|
| `revenue` | Σ(item price + freight) over revenue orders | any (built from item-grain sums per order) | n/a | excludes costs; not margin |
| `goods_revenue` / `freight_revenue` | Σ price / Σ freight separately | as above | n/a | — |
| `orders` (revenue) | count of revenue orders | month / category / … | n/a | order counts are **not** additive across categories or payment types |
| `avg_order_value` (AOV) | revenue ÷ orders of the same population | same as orders | n/a | right-skewed distribution; pair with median |
| `median_order_value` | `percentile_cont(0.5)` of order revenue | order population | n/a | — |
| Payment totals | Σ `payment_value` per order | order | missing when no payment row (1 order) | differs from item totals (vouchers/refunds); reconciliation test with thresholds |

Order value is recognized at **purchase time** (item price), not at delivery —
the dataset has no returns/refund feed to support delivered-basis revenue.

## Delivery

| Metric | Definition | Population | Notes |
|---|---|---|---|
| `delivery_days` | epoch-seconds between purchase and delivered timestamps ÷ 86400, rounded to 0.1 | delivered measured | fractional days |
| `late` / `late_days` | delivered **calendar date** > estimated date (same day = on time); integer day difference | delivered measured | compares dates, not timestamps |
| `late_rate_pct` | late orders ÷ delivered measured × 100 | month / state / category | estimates vary by region — "late" is relative to Olist's promise |
| `median / p90_delivery_days` | continuous percentiles | as above | — |

Orders with status `delivered` but missing delivered timestamp (8 orders) are
excluded from delivery metrics and counted in the quality report.

## Payments

| Metric | Definition | Notes |
|---|---|---|
| Method mix | distinct revenue orders containing a `payment_type`, and Σ `payment_value` per type | an order with two types appears under both — shares across types exceed 100% by construction |
| `primary_payment_type` | type of the largest-value payment record (tie: lowest `payment_sequential`) | order grain |
| Installment bins | order's max credit-card `payment_installments` binned (1 / 2-3 / 4-6 / 7-10 / 11+), credit-card revenue orders only | association with order value is descriptive, never causal |

## Reviews

| Metric | Definition | Notes |
|---|---|---|
| Review dedup | one review per order: latest `review_answer_timestamp` (tie: latest `review_creation_date`, then `review_id`) | 547 orders have > 1 review row |
| `avg_review_score` | arithmetic mean of scores | ordinal scale averaged — reported together with distributions |
| `pct_low_reviews` | share of scores ≤ 2 | — |
| Lateness buckets | 0. no timestamp / on time / late 1-7 / late 8-14 / late 15+ days | association analysis only (Mann-Whitney + rank-biserial) |

## Customers

| Metric | Definition | Notes |
|---|---|---|
| Customer key | `customer_unique_id` (not `customer_id`, which is per-order) | pseudonymous; not verified as one person |
| Repeat-customer rate | customers with ≥ 2 revenue orders ÷ customers with ≥ 1, within the observation window | window-censored; not annualized |
| Cohort activity | `cohort_month` = first purchase month; activity by calendar months since first purchase | cells with < 3 months observable horizon are blanked in charts |
| `days_to_second_order` | purchase date of 2nd order − purchase date of 1st order, repeat customers only | — |

## Anti-double-counting invariants (dbt tests)

1. `int_order_facts` has exactly one row per source order
   (`assert_order_facts_matches_order_count.sql`).
2. `mart_monthly_revenue.revenue` equals the item-grain recomputation from
   staging (`assert_revenue_reconciliation.sql`).
3. Item counts agree across category mart, monthly mart and order facts
   (`assert_category_items_additivity.sql`).
4. Payment vs item totals per order stay within documented tolerances
   (`assert_payment_order_reconciliation.sql`; observed: 303 orders differ by
   > 0.01 BRL, max diff 182.81 BRL).
5. Delivery days are never negative (`assert_delivery_days_nonnegative.sql`).
6. Synthetic fixture expectations (multi-item, multi-payment, canceled,
   missing timestamps, review dedup) are pinned in
   `assert_fixture_aggregates.sql` against dbt seeds — invented numbers, never
   presented as Olist results.
