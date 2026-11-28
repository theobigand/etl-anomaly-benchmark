select
    order_id,
    tier,
    amount,
    coalesce(list_aggregate(list_transform(items, lambda i: i.qty), 'sum'), 0)::bigint as units
from {{ ref('stg_orders') }}
