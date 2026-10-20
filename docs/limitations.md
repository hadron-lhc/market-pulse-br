# Limitations

## Dataset

- **Observation window.** Purchases span 2016-09-04 → 2018-10-17, but the
  first real month is 2017-01 and the last complete month is 2018-08
  (Sep-2018 has a single order). Trend statements cover ~20 months.
- **No financial costs.** There are no COGS, seller fees, returns, refunds or
  ad-spend tables. Revenue ≠ profit; no margin metric is computed anywhere.
- **Vouchers distort payment totals.** `payment_value` includes vouchers and
  diverges from item totals on 303 revenue orders (max R$ 182.81); 830 orders
  have payments but no items (R$ 162.6k, mostly canceled/unavailable). Revenue
  is therefore always measured on items, never on payments.
- **Customer identity is pseudonymous.** `customer_unique_id` is Olist's
  identifier; it cannot be asserted to be one natural person. Repeat-purchase
  rates are lower bounds if identity splits, upper bounds if it merges.
- **Seller profitability unknown.** Seller rankings are revenue-only.
- **Reviews are opt-in.** Only a subset of delivered orders carries a review
  (~24%); review analyses describe reviewers, not all customers.
- **Geolocation is unusable as a fact.** Duplicate zip observations; only zip
  centroids (`int_zip_centroids`) are exposed.

## Methodological

- **Associations, not effects.** Seller delivery/review columns, installment
  analysis and late-vs-score comparisons are observational. Confounders
  (region, category mix, seller size) are discussed in `analysis/insights.md`;
  no causal claim is made.
- **Non-additive dimensions.** Orders spanning multiple categories or payment
  types appear in each; sums across those dimensions exceed platform totals.
  Marked in mart documentation and enforced by the additivity test on items.
- **Lateness is promise-relative.** "Late" compares delivery date to Olist's
  estimated date; remote regions receive padded estimates, so slow regions can
  still be highly "on time".
- **Censoring.** Cohort analyses blank cells with less than 3 observable
  months; the repeat-rate is window-lifetime, not annual.
- **`created`/`approved`/`invoiced`/`processing` orders** are included in
  "all orders" counts but excluded from revenue (they mostly lack items).

## Engineering

- The pipeline targets local PostgreSQL (validated on 16). `docker-compose.yml`
  is provided but was not the development path in the authoring environment.
- dbt runs the full build in seconds at this scale; no incremental
  materialization is implemented because it would add complexity without
  benefit for a static public dataset.
