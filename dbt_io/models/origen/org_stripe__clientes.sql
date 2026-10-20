-- Capa de origen: Stripe tal cual viene (sin renombrar ni interpretar).
select id, email, created
from {{ source('crudo', 'pagos_customers') }}
