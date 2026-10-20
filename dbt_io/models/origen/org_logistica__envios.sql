-- Capa de origen: exportación del operador logístico tal cual viene.
select guia, nro_pedido, transportista, region, fecha_despacho, fecha_prometida,
       fecha_entrega, estado, prueba_entrega, tipo_destino
from {{ source('crudo', 'envios') }}
