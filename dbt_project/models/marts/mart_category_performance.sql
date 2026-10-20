-- Grain: product_category (all-time summary).
-- Item-level revenue metrics; order-level counts come from distinct
-- order-category pairs so multi-category orders are counted once per category
-- (orders are therefore NOT additive across categories).
with cat_items as (
    select
        p.product_category,
        i.order_id,
        i.seller_id,
        i.product_id,
        i.price,
        i.freight_value,
        i.item_revenue
    from {{ ref('stg_order_items') }} i
    join {{ ref('stg_products') }} p on i.product_id = p.product_id
    join {{ ref('int_order_facts') }} f on i.order_id = f.order_id
    where f.is_revenue_order
),

cat_orders as (
    select distinct product_category, order_id
    from cat_items
),

order_cat_reviews as (
    select
        co.product_category,
        f.review_score
    from cat_orders co
    join {{ ref('int_order_facts') }} f on co.order_id = f.order_id
    where f.has_review
),

agg as (
    select
        product_category,
        count(*)                                              as items,
        sum(price)                                            as goods_revenue,
        sum(freight_value)                                    as freight_revenue,
        sum(item_revenue)                                     as revenue,
        count(distinct order_id)                              as orders,
        count(distinct seller_id)                             as sellers,
        count(distinct product_id)                            as products
    from cat_items
    group by product_category
),

review_agg as (
    select
        product_category,
        count(*)                                              as reviewed_orders,
        round(avg(review_score), 2)                           as avg_review_score
    from order_cat_reviews
    group by product_category
)

select
    a.product_category,
    a.items,
    a.orders,
    a.revenue,
    a.goods_revenue,
    a.freight_revenue,
    round(a.revenue / a.items, 2)                             as avg_item_revenue,
    round(100.0 * a.revenue / sum(a.revenue) over (), 2)      as revenue_share_pct,
    round(100.0 * a.items / sum(a.items) over (), 2)          as item_share_pct,
    a.sellers,
    a.products,
    r.reviewed_orders,
    r.avg_review_score
from agg a
left join review_agg r using (product_category)
