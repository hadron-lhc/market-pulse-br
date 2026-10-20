-- Grain: single row (headline KPIs).
-- Every metric below is defined in docs/metric_definitions.md; populations
-- differ by metric and are never mixed inside one indicator.
with revenue_orders as (
    select * from {{ ref('int_order_facts') }} where is_revenue_order
),

customer_frequency as (
    select
        customer_unique_id,
        count(*)                                            as orders
    from revenue_orders
    group by customer_unique_id
),

delivered as (
    select * from {{ ref('int_order_facts') }} where is_delivered_measured
),

reviewed as (
    select * from {{ ref('int_order_facts') }} where has_review
),

top_category as (
    select product_category
    from {{ ref('mart_category_performance') }}
    order by revenue desc
    limit 1
),

top_seller as (
    select seller_id
    from {{ ref('mart_seller_performance') }}
    order by revenue desc
    limit 1
)

select
    (select min(purchase_month) from revenue_orders)        as first_purchase_month,
    (select max(purchase_month) from revenue_orders)        as last_purchase_month,

    -- Revenue
    (select count(*) from revenue_orders)                   as orders,
    (select count(distinct customer_unique_id) from revenue_orders)
                                                            as customers,
    (select round(sum(order_revenue), 2) from revenue_orders)
                                                            as revenue,
    (select round(sum(order_revenue) / count(*), 2) from revenue_orders)
                                                            as avg_order_value,
    (select round(percentile_cont(0.5) within group (order by order_revenue)::numeric, 2)
     from revenue_orders)                                   as median_order_value,

    -- Repeat purchasing (within the observed window only)
    (select round(100.0 * avg(case when orders > 1 then 1 else 0 end), 2)
     from customer_frequency)                               as repeat_customer_rate_pct,

    -- Delivery
    (select count(*) from delivered)                        as delivered_orders,
    (select round(avg(delivery_days), 1) from delivered)    as avg_delivery_days,
    (select round(percentile_cont(0.5) within group (order by delivery_days)::numeric, 1)
     from delivered)                                        as median_delivery_days,
    (select round(100.0 * avg(case when is_late then 1 else 0 end), 2)
     from delivered)                                        as late_rate_pct,

    -- Reviews
    (select count(*) from reviewed)                         as reviewed_orders,
    (select round(avg(review_score), 2) from reviewed)      as avg_review_score,
    (select round(100.0 * avg(case when review_score <= 2 then 1 else 0 end), 2)
     from reviewed)                                         as pct_low_reviews,

    -- Leaders
    (select product_category from top_category)             as top_category_by_revenue,
    (select seller_id from top_seller)                      as top_seller_by_revenue
