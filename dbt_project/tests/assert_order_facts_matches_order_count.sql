-- Fan-out guard: the order backbone must have exactly one row per source order.
with counts as (
    select
        (select count(*) from {{ ref('int_order_facts') }}) as fact_rows,
        (select count(*) from {{ ref('stg_orders') }})      as order_rows
)

select fact_rows, order_rows
from counts
where fact_rows <> order_rows
