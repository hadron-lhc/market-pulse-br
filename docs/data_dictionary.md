# Data Dictionary

Source: Olist Brazilian E-Commerce Public Dataset (9 CSVs). Raw tables mirror
the CSVs with explicit types; analytics models add derived columns. Null rates
and quality checks are in [data_quality_report.md](data_quality_report.md).

## Raw tables (schema `raw`)

| Table | Grain (PK) | Rows | Notes |
|---|---|---:|---|
| `orders` | `order_id` | 99,441 | 8 statuses; 2,965 missing delivery timestamps |
| `customers` | `customer_id` | 99,441 | 96,096 distinct `customer_unique_id` |
| `order_items` | (`order_id`, `order_item_id`) | 112,650 | price excludes freight |
| `order_payments` | (`order_id`, `payment_sequential`) | 103,886 | installments only meaningful for credit card |
| `order_reviews` | *none* | 99,224 | `review_id` duplicated; 547 orders with >1 review |
| `products` | `product_id` | 32,951 | 610 missing category |
| `sellers` | `seller_id` | 3,095 | — |
| `geolocation` | *none* | 1,000,163 | duplicate zip/city rows by design |
| `product_category_name_translation` | `product_category_name` | 71 | PT→EN category map |

## Staging (`staging`, views)

Same grains as raw, plus: trimmed/normalized text, `stg_products.product_category`
(EN name, PT fallback, `unknown`), `stg_order_items.item_revenue`,
surrogate keys `order_item_key` / `payment_key`.

## Intermediate (`intermediate`, tables)

| Model | Grain | Key columns |
|---|---|---|
| `int_order_items_agg` | order | `items_count`, `goods_value`, `freight_value`, `order_revenue` |
| `int_payments_agg` | order | `total_payment_value`, `max_installments`, method flags, `primary_payment_type` |
| `int_reviews_agg` | order | deduped `review_score`, `review_count` |
| `int_order_facts` | order | everything above + geography, timestamps, `delivery_days`, `late_days`, `is_revenue_order`, `is_delivered_measured`, `has_review` |
| `int_zip_centroids` | zip | `avg_lat`, `avg_lng`, `observation_count` |

## Marts (`marts`, tables)

| Model | Grain | Purpose |
|---|---|---|
| `mart_monthly_revenue` | month | orders, customers, items, revenue, AOV/median |
| `mart_category_performance` | category | all-time revenue, shares, avg item price, reviews |
| `mart_category_monthly` | category × month | category trends |
| `mart_seller_performance` | seller | revenue, share, delivery/review associations, `has_min_sample` |
| `mart_delivery_monthly` | month | delivery duration + late rate |
| `mart_delivery_by_state` | customer state | delivery experience by region |
| `mart_delivery_by_category` | category | delivery experience by product type |
| `mart_payment_mix` | payment type × month | method adoption and value |
| `mart_payment_installments` | installment bin | order value vs installments |
| `mart_review_by_lateness` | lateness bucket × score | score distribution vs delays |
| `mart_review_by_state` | state | sentiment by region |
| `mart_review_by_category` | category | sentiment by product type |
| `mart_customer_cohorts` | cohort month × months since | repeat behaviour |
| `mart_kpi_overview` | single row | dashboard headline KPIs |

Column-level documentation for every model lives in the dbt `schema.yml` files
under `dbt_project/models/` and renders in the dbt docs website
(`dbt docs generate && dbt docs serve`).
