-- Grain: purchase_month (calendar month of the order purchase).
-- Population: int_order_facts where is_revenue_order (has >= 1 item and status
-- not in canceled/unavailable). Revenue = item price + freight at item grain,
-- aggregated to orders before summing (no fan-out).
select
    purchase_month,
    count(*)                                        as orders,
    count(distinct customer_unique_id)              as customers,
    sum(items_count)                                as items_sold,
    sum(goods_value)                                as goods_revenue,
    sum(freight_value)                              as freight_revenue,
    sum(order_revenue)                              as revenue,
    round(sum(order_revenue) / count(*), 2)         as avg_order_value,
    round(percentile_cont(0.5) within group (order by order_revenue)::numeric, 2)
                                                    as median_order_value
from {{ ref('int_order_facts') }}
where is_revenue_order
group by purchase_month
