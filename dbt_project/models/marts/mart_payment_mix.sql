-- Grain: (payment_type, purchase_month).
-- Population: revenue orders (see int_order_facts.is_revenue_order).
-- orders counts distinct orders containing a record of the payment type; an
-- order paying with two types appears under both, so orders are not additive
-- across payment types. payment_value sums the payment records of that type.
select
    p.payment_type,
    f.purchase_month,
    count(distinct p.order_id)                              as orders,
    sum(p.payment_value)                                    as payment_value,
    round(avg(f.order_revenue), 2)                          as avg_order_value,
    round(100.0 * count(distinct p.order_id)
        / sum(count(distinct p.order_id)) over (partition by f.purchase_month), 2)
                                                            as order_share_pct
from {{ ref('stg_order_payments') }} p
join {{ ref('int_order_facts') }} f on p.order_id = f.order_id
where f.is_revenue_order
group by p.payment_type, f.purchase_month
