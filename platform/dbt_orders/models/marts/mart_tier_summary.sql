-- the same aggregation as the SQL of research/elt_duckdb.py, built by dbt
select
    tier,
    count(*) as orders,
    sum(units)::bigint as units,
    sum(amount) as amount
from {{ ref('int_order_units') }}
group by tier
order by tier
