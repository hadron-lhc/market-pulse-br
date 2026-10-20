-- Grain: seller_id (all-time summary).
-- Revenue is the seller's own items (price + freight) on non-canceled orders.
-- Delivery and review figures are ORDER-level (orders containing this seller's
-- items) and are therefore associative, not a quality score of the seller:
-- multi-seller orders share the same delivery/review outcome.
with seller_items as (
    select
        i.seller_id,
        i.order_id,
        i.product_id,
        i.price,
        i.freight_value,
        i.item_revenue
    from {{ ref('stg_order_items') }} i
    join {{ ref('int_order_facts') }} f on i.order_id = f.order_id
    where f.is_revenue_order
),

seller_agg as (
    select
        s.seller_id,
        s.seller_state,
        s.seller_city,
        count(*)                                              as items,
        count(distinct si.order_id)                           as orders,
        count(distinct si.product_id)                         as products,
        sum(si.price)                                         as goods_revenue,
        sum(si.freight_value)                                 as freight_revenue,
        sum(si.item_revenue)                                  as revenue
    from seller_items si
    join {{ ref('stg_sellers') }} s on si.seller_id = s.seller_id
    group by s.seller_id, s.seller_state, s.seller_city
),

order_link as (
    select distinct si.seller_id, si.order_id
    from seller_items si
),

seller_delivery as (
    select
        sl.seller_id,
        count(*)                                              as delivered_orders,
        round(avg(f.delivery_days), 1)                        as avg_delivery_days,
        round(percentile_cont(0.5) within group (order by f.delivery_days)::numeric, 1)
                                                              as median_delivery_days,
        round(100.0 * avg(case when f.is_late then 1 else 0 end), 2)
                                                              as late_rate_pct
    from order_link sl
    join {{ ref('int_order_facts') }} f on sl.order_id = f.order_id
    where f.is_delivered_measured
    group by sl.seller_id
),

seller_reviews as (
    select
        sl.seller_id,
        count(*)                                              as reviewed_orders,
        round(avg(f.review_score), 2)                         as avg_review_score
    from order_link sl
    join {{ ref('int_order_facts') }} f on sl.order_id = f.order_id
    where f.has_review
    group by sl.seller_id
)

select
    a.seller_id,
    a.seller_state,
    a.seller_city,
    a.items,
    a.orders,
    a.products,
    a.revenue,
    a.goods_revenue,
    a.freight_revenue,
    round(a.revenue / a.items, 2)                             as avg_item_revenue,
    round(100.0 * a.revenue / sum(a.revenue) over (), 4)      as revenue_share_pct,
    d.delivered_orders,
    d.avg_delivery_days,
    d.median_delivery_days,
    d.late_rate_pct,
    r.reviewed_orders,
    r.avg_review_score,
    (a.orders >= 30)                                          as has_min_sample
from seller_agg a
left join seller_delivery d using (seller_id)
left join seller_reviews r using (seller_id)
