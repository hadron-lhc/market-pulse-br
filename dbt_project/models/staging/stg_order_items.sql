select
    order_id,
    order_item_id,
    order_id || '-' || order_item_id::text        as order_item_key,
    product_id,
    seller_id,
    shipping_limit_date,
    price,
    freight_value,
    price + freight_value                         as item_revenue
from {{ source('raw', 'order_items') }}
