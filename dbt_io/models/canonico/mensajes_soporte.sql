-- Un mensaje de soporte por fila, ya unido a su cliente.
select
    m.mensaje_id,
    c.cliente_id,
    m.pedido_id,
    m.creado_en,
    m.categoria,
    m.texto,
    m.estado
from {{ ref('map_mensajes_soporte') }} m
left join {{ ref('clientes') }} c using (correo)
