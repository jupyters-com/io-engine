-- MAPEO de este cliente (contracargos sintéticos) a los nombres de IO.
-- Es la única capa que cambia cuando entra otro cliente.
select
    id                                              as cliente_id,
    lower(trim(email))                              as correo,
    to_timestamp(created) at time zone 'UTC'        as creado_en
from {{ ref('org_stripe__clientes') }}
