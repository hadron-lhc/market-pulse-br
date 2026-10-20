-- Grain: (lateness_bucket, review_score).
-- Population: orders with a deduped review (int_order_facts.has_review).
-- Orders without a delivery timestamp get their own bucket instead of being
-- silently dropped.
with bucketed as (
    select
        case
            when not is_delivered_measured then '0. no delivery timestamp'
            when is_late and late_days <= 7 then '2. late 1-7 days'
            when is_late and late_days <= 14 then '3. late 8-14 days'
            when is_late then '4. late 15+ days'
            else '1. on time'
        end                                                 as lateness_bucket,
        case
            when not is_delivered_measured then 0
            when is_late and late_days <= 7 then 2
            when is_late and late_days <= 14 then 3
            when is_late then 4
            else 1
        end                                                 as bucket_order,
        review_score
    from {{ ref('int_order_facts') }}
    where has_review
)

select
    lateness_bucket,
    bucket_order,
    review_score,
    count(*)                                                as reviews,
    round(100.0 * count(*) / sum(count(*)) over (partition by lateness_bucket), 2)
                                                            as pct_within_bucket
from bucketed
group by lateness_bucket, bucket_order, review_score
