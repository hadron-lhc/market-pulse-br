-- Grain: order_id (exactly one row per order in raw.orders).
-- Single source of truth for order-level flags used by every mart:
--   * is_revenue_order: order contributes to revenue metrics
--   * is_delivered_measured: order contributes to delivery-time metrics
--   * has_review: order contributes to review metrics
-- Never join this model to order_items / order_payments / order_reviews.
with orders as (
    select * from {{ ref('stg_orders') }}
),

customers as (
    select * from {{ ref('stg_customers') }}
),

items as (
    select * from {{ ref('int_order_items_agg') }}
),

payments as (
    select * from {{ ref('int_payments_agg') }}
),

reviews as (
    select * from {{ ref('int_reviews_agg') }}
),

final as (
    select
        o.order_id,
        o.customer_id,
        c.customer_unique_id,
        c.customer_state,
        c.customer_city,
        o.order_status,
        o.order_purchase_timestamp,
        o.order_approved_at,
        o.order_delivered_carrier_date,
        o.order_delivered_customer_date,
        o.order_estimated_delivery_date,
        o.order_purchase_timestamp::date                             as purchase_date,
        date_trunc('month', o.order_purchase_timestamp)::date        as purchase_month,

        -- Item-grain aggregates (0 when the order has no items)
        coalesce(i.items_count, 0)                                   as items_count,
        coalesce(i.distinct_products, 0)                             as distinct_products,
        coalesce(i.distinct_sellers, 0)                              as distinct_sellers,
        coalesce(i.goods_value, 0)                                   as goods_value,
        coalesce(i.freight_value, 0)                                 as freight_value,
        coalesce(i.order_revenue, 0)                                 as order_revenue,

        -- Payment-grain aggregates (null when the order has no payments)
        p.payment_count,
        p.total_payment_value,
        p.max_installments,
        p.primary_payment_type,
        coalesce(p.has_credit_card, false)                           as has_credit_card,
        coalesce(p.has_boleto, false)                                as has_boleto,
        coalesce(p.has_voucher, false)                               as has_voucher,
        coalesce(p.has_debit_card, false)                            as has_debit_card,

        -- Review (one deduped review per order)
        r.review_score,
        coalesce(r.review_count, 0)                                  as review_count,
        r.review_creation_date,
        (r.review_score is not null)                                 as has_review,

        -- Delivery metrics: only meaningful for delivered orders with a timestamp.
        -- Days are calendar-day differences; lateness compares delivery DATE to
        -- the estimated DATE (an order delivered on the estimated day is on time).
        case
            when o.order_status = 'delivered'
                 and o.order_delivered_customer_date is not null
            then round(
                extract(epoch from (o.order_delivered_customer_date - o.order_purchase_timestamp)) / 86400,
                1
            )
        end                                                          as delivery_days,
        case
            when o.order_status = 'delivered'
                 and o.order_delivered_customer_date is not null
            then (o.order_delivered_customer_date::date - o.order_estimated_delivery_date::date)
        end                                                          as late_days,
        case
            when o.order_status = 'delivered'
                 and o.order_delivered_customer_date is not null
            then (o.order_delivered_customer_date::date > o.order_estimated_delivery_date::date)
        end                                                          as is_late,

        -- Population flags (single source of truth for every mart)
        (o.order_status not in ('canceled', 'unavailable')
            and coalesce(i.items_count, 0) > 0)                     as is_revenue_order,
        (o.order_status = 'delivered'
            and o.order_delivered_customer_date is not null)         as is_delivered_measured
    from orders o
    left join customers c on o.customer_id = c.customer_id
    left join items i on o.order_id = i.order_id
    left join payments p on o.order_id = p.order_id
    left join reviews r on o.order_id = r.order_id
)

select * from final
