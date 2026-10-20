-- Grain: order_id (one row per order that has at least one item).
-- Safe to join to orders 1:1; never join back to order_items for order metrics.
select
    order_id,
    count(*)                                        as items_count,
    count(distinct product_id)                      as distinct_products,
    count(distinct seller_id)                       as distinct_sellers,
    sum(price)                                      as goods_value,
    sum(freight_value)                              as freight_value,
    sum(price + freight_value)                      as order_revenue,
    min(shipping_limit_date)                        as first_shipping_limit_date,
    max(shipping_limit_date)                        as last_shipping_limit_date
from {{ ref('stg_order_items') }}
group by order_id
