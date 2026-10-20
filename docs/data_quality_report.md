# Data Quality Report (raw schema)

Generated: 2026-10-19 22:19:34 — all values below are computed from the loaded Olist CSVs.

## Row counts and primary keys

| table | rows | primary key | duplicate pk rows |
|---|---:|---|---:|
| raw.orders | 99,441 | order_id | 0 |
| raw.customers | 99,441 | customer_id | 0 |
| raw.order_items | 112,650 | order_id, order_item_id | 0 |
| raw.order_payments | 103,886 | order_id, payment_sequential | 0 |
| raw.products | 32,951 | product_id | 0 |
| raw.sellers | 3,095 | seller_id | 0 |
| raw.product_category_name_translation | 71 | product_category_name | 0 |
| raw.order_reviews | 99,224 | _(none)_ | n/a |
| raw.geolocation | 1,000,163 | _(none)_ | n/a |

## Null rates by column (non-zero only)

| table | column | type | nulls | null % |
|---|---|---|---:|---:|
| raw.orders | order_approved_at | timestamp without time zone | 160 | 0.16% |
| raw.orders | order_delivered_carrier_date | timestamp without time zone | 1,783 | 1.79% |
| raw.orders | order_delivered_customer_date | timestamp without time zone | 2,965 | 2.98% |
| raw.products | product_category_name | text | 610 | 1.85% |
| raw.products | product_name_lenght | integer | 610 | 1.85% |
| raw.products | product_description_lenght | integer | 610 | 1.85% |
| raw.products | product_photos_qty | integer | 610 | 1.85% |
| raw.products | product_weight_g | integer | 2 | 0.01% |
| raw.products | product_length_cm | integer | 2 | 0.01% |
| raw.products | product_height_cm | integer | 2 | 0.01% |
| raw.products | product_width_cm | integer | 2 | 0.01% |
| raw.order_reviews | review_comment_title | text | 87,656 | 88.34% |
| raw.order_reviews | review_comment_message | text | 58,247 | 58.70% |

## Referential integrity (orphan child rows)

| foreign key | orphan rows |
|---|---:|
| orders.customer_id -> customers.customer_id | 0 |
| order_items.order_id -> orders.order_id | 0 |
| order_items.product_id -> products.product_id | 0 |
| order_items.seller_id -> sellers.seller_id | 0 |
| order_payments.order_id -> orders.order_id | 0 |
| order_reviews.order_id -> orders.order_id | 0 |

## Join fan-out risk (multi-record orders)

| condition | orders |
|---|---:|
| orders with more than 1 item | 9,803 |
| orders with more than 1 payment record | 2,961 |
| orders with more than 1 review record | 547 |
| orders with no items | 775 |
| orders with no payment record | 1 |
| orders with no review record | 768 |

These counts are the reason revenue and order metrics are computed at item or order grain in dedicated aggregation models instead of joining orders x items x payments x reviews directly.

## Revenue reconciliation: items vs payments

| measure | value |
|---|---:|
| sum(item price + freight) | 15,843,553.24 |
| sum(payment_value) | 16,008,872.12 |
| difference | 165,318.88 |
| orders present in both tables | 98,665 |
| orders where abs difference > 0.01 | 303 |
| max abs difference on a single order | 182.81 |

Payments can include vouchers and orders that have no items, so the two totals are expected to differ slightly. Item revenue (price + freight) is the project's revenue definition; payment totals are used for reconciliation only.

## Order status distribution

| status | orders |
|---|---:|
| delivered | 96,478 |
| shipped | 1,107 |
| canceled | 625 |
| unavailable | 609 |
| invoiced | 314 |
| processing | 301 |
| created | 5 |
| approved | 2 |

## Timestamp ranges

| column | min | max | nulls |
|---|---|---|---:|
| orders.order_purchase_timestamp | 2016-09-04 21:15:19 | 2018-10-17 17:30:18 | 0 |
| orders.order_approved_at | 2016-09-15 12:16:38 | 2018-09-03 17:40:06 | 160 |
| orders.order_delivered_customer_date | 2016-10-11 13:46:32 | 2018-10-17 13:22:46 | 2,965 |
| orders.order_estimated_delivery_date | 2016-09-30 00:00:00 | 2018-11-12 00:00:00 | 0 |

