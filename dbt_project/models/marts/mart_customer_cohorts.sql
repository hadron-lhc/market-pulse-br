-- Grain: (cohort_month, months_since_first_purchase).
-- cohort_month = first purchase month of the customer_unique_id.
-- months_since_first_purchase = 0 in the acquisition month, then calendar
-- months. Population: revenue orders only.
-- Limitation: customer_unique_id is an Olist pseudonymous identifier; the
-- dataset ends in Oct-2018, so late cohorts have censored observation windows.
with cohorts as (
    select
        customer_unique_id,
        min(purchase_month)                                 as cohort_month
    from {{ ref('int_order_facts') }}
    where is_revenue_order
    group by customer_unique_id
),

activity as (
    select
        c.cohort_month,
        ((extract(year from f.purchase_month) * 12 + extract(month from f.purchase_month))
            - (extract(year from c.cohort_month) * 12 + extract(month from c.cohort_month)))::int
                                                            as months_since_first_purchase,
        f.customer_unique_id,
        f.order_id
    from {{ ref('int_order_facts') }} f
    join cohorts c on f.customer_unique_id = c.customer_unique_id
    where f.is_revenue_order
)

select
    cohort_month,
    months_since_first_purchase,
    count(distinct customer_unique_id)                      as customers_with_order,
    count(*)                                                as orders
from activity
group by cohort_month, months_since_first_purchase
