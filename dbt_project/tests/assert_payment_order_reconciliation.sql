-- Data expectation (dataset-specific, from the Olist CSVs): on revenue orders,
-- payment totals and item totals match within 1 BRL for all but a few hundred
-- orders (vouchers / rounding), and no single order differs by more than 200
-- BRL. Thresholds have headroom over the observed values (303 orders >0.01 BRL,
-- max diff 182.81) so the test flags real regressions, not noise.
with m as (
    select
        count(*) filter (
            where abs(order_revenue - total_payment_value) > 1.0
        )                                                   as mismatched_orders,
        max(abs(order_revenue - total_payment_value))       as max_abs_diff
    from {{ ref('int_order_facts') }}
    where is_revenue_order
      and total_payment_value is not null
)

select mismatched_orders, max_abs_diff
from m
where mismatched_orders > 500
   or max_abs_diff > 200
