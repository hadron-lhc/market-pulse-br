-- Grain: customer_state.
-- Population: is_delivered_measured. Delivery experience of customers in each state.
select
    customer_state,
    count(*)                                                as delivered_orders,
    round(avg(delivery_days), 1)                            as avg_delivery_days,
    round(percentile_cont(0.5) within group (order by delivery_days)::numeric, 1)
                                                            as median_delivery_days,
    count(*) filter (where is_late)                         as late_orders,
    round(100.0 * count(*) filter (where is_late) / count(*), 2)
                                                            as late_rate_pct,
    (count(*) >= 100)                                       as has_min_sample
from {{ ref('int_order_facts') }}
where is_delivered_measured
group by customer_state
