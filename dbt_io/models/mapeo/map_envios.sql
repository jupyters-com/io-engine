select
    guia                                            as envio_id,
    'ORD-' || nro_pedido                            as pedido_id,      -- 1001 -> ORD-1001
    transportista,
    region,
    strptime(fecha_despacho, '%d/%m/%Y')::date      as despachado_en,
    strptime(fecha_prometida, '%d/%m/%Y')::date     as prometido_en,
    try_strptime(nullif(fecha_entrega, ''), '%d/%m/%Y')::date as entregado_en,
    lower(estado)                                   as estado,         -- entregado, en_transito, extraviado, devuelto
    lower(prueba_entrega)                           as prueba_entrega, -- firma, foto, ninguna
    lower(tipo_destino)                             as tipo_destino    -- domicilio, punto_retiro
from {{ ref('org_logistica__envios') }}
