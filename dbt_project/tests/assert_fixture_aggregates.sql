-- Synthetic fixture checks (seeds/fixture_*.csv). These numbers are invented
-- for testing and are never presented as Olist findings. They pin the
-- aggregation patterns that prevent double counting:
--   * item totals per order (multi-item order)
--   * payment totals per order (multi-payment order)
--   * the size of the items x payments fan-out on a known order
--   * canceled orders excluded from revenue populations
--   * review dedup keeps the latest answered review
--   * missing delivery timestamps stay NULL
with item_totals as (
    select order_id, sum(price + freight_value) as total
    from {{ ref('fixture_order_items') }}
    group by order_id
),

payment_totals as (
    select order_id, sum(payment_value) as total
    from {{ ref('fixture_order_payments') }}
    group by order_id
),

latest_review as (
    select order_id, review_score
    from (
        select
            order_id,
            review_score,
            row_number() over (
                partition by order_id
                order by review_answer_timestamp desc, review_id desc
            ) as rn
        from {{ ref('fixture_order_reviews') }}
    ) t
    where rn = 1
),

checks as (
    select
        'multi-item order total = 170'                          as check_name,
        (select total from item_totals where order_id = 'o_multi_item') as actual,
        170.0                                                   as expected

    union all
    select
        'multi-payment order payments = 35',
        (select total from payment_totals where order_id = 'o_multi_pay'),
        35.0

    union all
    select
        'naive items x payments join inflates o_multi_pay to 70',
        (
            select sum(i.price + i.freight_value)
            from {{ ref('fixture_order_items') }} i
            join {{ ref('fixture_order_payments') }} p on i.order_id = p.order_id
            where i.order_id = 'o_multi_pay'
        ),
        70.0

    union all
    select
        'revenue population excludes canceled (205 not 285)',
        (
            select sum(i.price + i.freight_value)
            from {{ ref('fixture_order_items') }} i
            join {{ ref('fixture_orders') }} o on i.order_id = o.order_id
            where o.order_status not in ('canceled', 'unavailable')
        ),
        205.0

    union all
    select
        'deduped review for o_multi_item is the latest (score 2)',
        (select review_score from latest_review where order_id = 'o_multi_item'),
        2.0

    union all
    select
        'delivered order with missing timestamp kept as NULL',
        (
            select count(*)
            from {{ ref('fixture_orders') }}
            where order_id = 'o_missing_ts'
              and nullif(cast(order_delivered_customer_date as varchar), '') is null
        ),
        1.0
)

select check_name, actual, expected
from checks
where actual is null
   or abs(actual - expected) > 0.0001
