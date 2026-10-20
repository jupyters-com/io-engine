select
    ticket                                          as mensaje_id,
    lower(trim(solicitante))                        as correo,         -- se une al cliente por correo
    'ORD-' || ltrim(pedido, '#')                    as pedido_id,      -- #1001 -> ORD-1001
    cast(creado as timestamptz) at time zone 'UTC'  as creado_en,
    categoria,
    mensaje                                         as texto,
    estado
from {{ ref('org_soporte__tickets') }}
