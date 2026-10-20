-- Sanity: measured delivery time can never be negative. If this test fails,
-- timestamps were corrupted or the delivery_days expression changed.
select order_id, purchase_date, order_delivered_customer_date, delivery_days
from {{ ref('int_order_facts') }}
where is_delivered_measured
  and delivery_days < 0
