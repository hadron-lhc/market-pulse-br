select
    order_id,
    payment_sequential,
    order_id || '-' || payment_sequential::text   as payment_key,
    lower(trim(payment_type))                     as payment_type,
    payment_installments,
    payment_value
from {{ source('raw', 'order_payments') }}
