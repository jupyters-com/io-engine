-- Capa canónica de IO: un cliente por fila. No menciona ninguna fuente: solo lee del mapeo.
with pagos_por_cliente as (
    select cliente_id, min(pagado_en) as primer_pago_en, count(*) as pagos_totales
    from {{ ref('map_pagos') }}
    group by cliente_id
)
select
    c.cliente_id,
    c.correo,
    c.creado_en,
    p.primer_pago_en,
    coalesce(p.pagos_totales, 0) as pagos_totales
from {{ ref('map_clientes') }} c
left join pagos_por_cliente p using (cliente_id)
