-- Grain: customer_state (all-time summary of reviewed orders).
-- Population: orders with a deduped review. late_rate is computed on the subset
-- of reviewed orders that were delivered with a timestamp.
select
    customer_state,
    count(*)                                                as reviews,
    round(avg(review_score), 2)                             as avg_review_score,
    round(100.0 * count(*) filter (where review_score <= 2) / count(*), 2)
                                                            as pct_low_reviews,
    count(*) filter (where is_delivered_measured)           as delivered_reviews,
    round(100.0 * count(*) filter (where is_late and is_delivered_measured)
        / nullif(count(*) filter (where is_delivered_measured), 0), 2)
                                                            as late_rate_pct,
    (count(*) >= 50)                                        as has_min_sample
from {{ ref('int_order_facts') }}
where has_review
group by customer_state
