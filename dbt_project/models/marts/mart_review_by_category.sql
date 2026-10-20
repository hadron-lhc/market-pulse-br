-- Grain: product_category (reviewed orders containing the category).
-- Orders spanning several categories appear in each of them; reviews are
-- associative (an order review reflects the whole order, not a single product).
with order_category as (
    select distinct
        p.product_category,
        i.order_id
    from {{ ref('stg_order_items') }} i
    join {{ ref('stg_products') }} p on i.product_id = p.product_id
    join {{ ref('int_order_facts') }} f on i.order_id = f.order_id
    where f.has_review
)

select
    oc.product_category,
    count(*)                                                as reviews,
    round(avg(f.review_score), 2)                           as avg_review_score,
    round(100.0 * count(*) filter (where f.review_score <= 2) / count(*), 2)
                                                            as pct_low_reviews,
    round(avg(f.delivery_days), 1)                          as avg_delivery_days,
    (count(*) >= 50)                                        as has_min_sample
from order_category oc
join {{ ref('int_order_facts') }} f on oc.order_id = f.order_id
group by oc.product_category
