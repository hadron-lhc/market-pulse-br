-- Grain: order_id (one row per order, aggregated from payment records).
-- payment_value sums can differ slightly from item totals (vouchers, refunds
-- not represented); see the reconciliation test and docs/metric_definitions.md.
with payment_totals as (
    select
        order_id,
        count(*)                                    as payment_count,
        sum(payment_value)                          as total_payment_value,
        max(payment_installments)                   as max_installments,
        bool_or(payment_type = 'credit_card')       as has_credit_card,
        bool_or(payment_type = 'boleto')            as has_boleto,
        bool_or(payment_type = 'voucher')           as has_voucher,
        bool_or(payment_type = 'debit_card')        as has_debit_card
    from {{ ref('stg_order_payments') }}
    group by order_id
),

primary_type as (
    select order_id, payment_type
    from (
        select
            order_id,
            payment_type,
            row_number() over (
                partition by order_id
                order by payment_value desc, payment_sequential asc
            ) as rn
        from {{ ref('stg_order_payments') }}
    ) ranked
    where rn = 1
)

select
    t.order_id,
    t.payment_count,
    t.total_payment_value,
    t.max_installments,
    t.has_credit_card,
    t.has_boleto,
    t.has_voucher,
    t.has_debit_card,
    p.payment_type                                  as primary_payment_type
from payment_totals t
left join primary_type p using (order_id)
