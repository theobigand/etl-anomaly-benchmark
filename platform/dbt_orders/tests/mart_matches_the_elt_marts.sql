-- the dbt mart and the DuckDB ELT mart must agree on every tier (a failing test returns rows)
select m.tier, m.orders as dbt_orders, e.orders as elt_orders
from {{ ref('mart_tier_summary') }} as m
full outer join read_parquet('{{ env_var("ELT_MARTS") }}') as e
    on m.tier is not distinct from e.tier
where m.orders is distinct from e.orders
   or m.units is distinct from e.units
   or abs(coalesce(m.amount, 0) - coalesce(e.amount, 0)) > 0.005
