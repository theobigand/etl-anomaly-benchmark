-- one row per order, nesting kept: only the customer struct is read for its two fields
select
    order_id,
    customer.id as customer_id,
    customer.tier as tier,
    items,
    ts,
    amount
from {{ source('elt', 'raw_orders') }}
