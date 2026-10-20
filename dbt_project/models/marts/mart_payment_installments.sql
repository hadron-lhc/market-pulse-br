-- Grain: installment_bin (credit-card revenue orders only).
-- max_installments is the largest credit-card installment count on the order.
-- Association only: larger orders may choose installments; nothing here
-- identifies a causal effect of installments on order value.
with credit_orders as (
    select
        order_id,
        max(payment_installments)                           as max_installments
    from {{ ref('stg_order_payments') }}
    where payment_type = 'credit_card'
    group by order_id
),

binned as (
    select
        case
            when co.max_installments <= 1 then '1 (no installment)'
            when co.max_installments <= 3 then '2-3 installments'
            when co.max_installments <= 6 then '4-6 installments'
            when co.max_installments <= 10 then '7-10 installments'
            else '11+ installments'
        end                                                 as installment_bin,
        case
            when co.max_installments <= 1 then 1
            when co.max_installments <= 3 then 2
            when co.max_installments <= 6 then 3
            when co.max_installments <= 10 then 4
            else 5
        end                                                 as bin_order,
        f.order_revenue
    from credit_orders co
    join {{ ref('int_order_facts') }} f on co.order_id = f.order_id
    where f.is_revenue_order
)

select
    installment_bin,
    bin_order,
    count(*)                                                as orders,
    sum(order_revenue)                                      as revenue,
    round(avg(order_revenue), 2)                            as avg_order_value,
    round(percentile_cont(0.5) within group (order by order_revenue)::numeric, 2)
                                                            as median_order_value
from binned
group by installment_bin, bin_order
