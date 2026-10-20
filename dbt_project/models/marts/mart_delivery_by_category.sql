-- Grain: product_category.
-- Population: delivered orders with a timestamp that contain at least one item
-- of the category. Orders spanning several categories appear in each of them,
-- so delivered_orders is not additive across categories.
with order_category as (
    select distinct
        p.product_category,
        i.order_id
    from {{ ref('stg_order_items') }} i
    join {{ ref('stg_products') }} p on i.product_id = p.product_id
    join {{ ref('int_order_facts') }} f on i.order_id = f.order_id
    where f.is_delivered_measured
)

select
    oc.product_category,
    count(*)                                                as delivered_orders,
    round(avg(f.delivery_days), 1)                          as avg_delivery_days,
    round(percentile_cont(0.5) within group (order by f.delivery_days)::numeric, 1)
                                                            as median_delivery_days,
    count(*) filter (where f.is_late)                       as late_orders,
    round(100.0 * count(*) filter (where f.is_late) / count(*), 2)
                                                            as late_rate_pct,
    (count(*) >= 100)                                       as has_min_sample
from order_category oc
join {{ ref('int_order_facts') }} f on oc.order_id = f.order_id
group by oc.product_category
