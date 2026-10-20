-- Grain: purchase_month.
-- Population: is_delivered_measured (delivered status + delivery timestamp).
-- delivery_days: elapsed calendar days between purchase and delivery timestamps.
-- late: delivery DATE after estimated DATE (same-day counts as on time).
select
    purchase_month,
    count(*)                                                as delivered_orders,
    round(avg(delivery_days), 1)                            as avg_delivery_days,
    round(percentile_cont(0.5) within group (order by delivery_days)::numeric, 1)
                                                            as median_delivery_days,
    round(percentile_cont(0.9) within group (order by delivery_days)::numeric, 1)
                                                            as p90_delivery_days,
    count(*) filter (where is_late)                         as late_orders,
    round(100.0 * count(*) filter (where is_late) / count(*), 2)
                                                            as late_rate_pct,
    round(avg(late_days), 1)                                as avg_days_vs_estimate
from {{ ref('int_order_facts') }}
where is_delivered_measured
group by purchase_month
