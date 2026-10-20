-- Fan-out guard: mart revenue must equal the item-grain revenue of the same
-- population (orders with >=1 item, status not canceled/unavailable).
with mart as (
    select round(sum(revenue), 2) as revenue
    from {{ ref('mart_monthly_revenue') }}
),

item_grain as (
    select round(sum(i.price + i.freight_value), 2) as revenue
    from {{ ref('stg_order_items') }} i
    join {{ ref('stg_orders') }} o on i.order_id = o.order_id
    where o.order_status not in ('canceled', 'unavailable')
)

select mart.revenue as mart_revenue, item_grain.revenue as item_grain_revenue
from mart
cross join item_grain
where abs(mart.revenue - item_grain.revenue) > 0.01
