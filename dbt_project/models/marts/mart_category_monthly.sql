-- Grain: (product_category, purchase_month).
-- Item-grain revenue by category and month; used for category trend analysis.
-- orders counts distinct orders containing the category that month and are not
-- additive across categories.
select
    p.product_category,
    f.purchase_month,
    count(*)                                                as items,
    count(distinct i.order_id)                              as orders,
    sum(i.price + i.freight_value)                          as revenue,
    sum(i.price)                                            as goods_revenue,
    sum(i.freight_value)                                    as freight_revenue,
    count(distinct i.seller_id)                             as sellers
from {{ ref('stg_order_items') }} i
join {{ ref('stg_products') }} p on i.product_id = p.product_id
join {{ ref('int_order_facts') }} f on i.order_id = f.order_id
where f.is_revenue_order
group by p.product_category, f.purchase_month
