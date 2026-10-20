-- Additivity guard: item counts must agree across layers. Items belong to
-- exactly one category, so item counts are additive; order counts are not.
with cat as (
    select sum(items) as items from {{ ref('mart_category_performance') }}
),

monthly as (
    select sum(items_sold) as items from {{ ref('mart_monthly_revenue') }}
),

facts as (
    select sum(items_count) as items
    from {{ ref('int_order_facts') }}
    where is_revenue_order
)

select cat.items as category_items, monthly.items as monthly_items, facts.items as facts_items
from cat
cross join monthly
cross join facts
where cat.items <> monthly.items
   or monthly.items <> facts.items
