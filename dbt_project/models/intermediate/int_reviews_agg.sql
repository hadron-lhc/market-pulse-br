-- Grain: order_id (one row per order).
-- 547 orders carry more than one review; we keep the most recently answered
-- review per order (tie-break: latest creation date, then review_id).
with ranked as (
    select
        order_id,
        review_id,
        review_score,
        review_creation_date,
        review_answer_timestamp,
        count(*) over (partition by order_id)       as review_count,
        row_number() over (
            partition by order_id
            order by review_answer_timestamp desc nulls last,
                     review_creation_date desc nulls last,
                     review_id desc
        )                                           as rn
    from {{ ref('stg_order_reviews') }}
)

select
    order_id,
    review_id,
    review_score,
    review_creation_date,
    review_answer_timestamp,
    review_count
from ranked
where rn = 1
