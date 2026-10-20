-- Un pago (cobro) por pedido.
select pago_id, pedido_id, cliente_id, monto, moneda, pagado_en,
       pais_facturacion, pais_ip, nivel_riesgo, tarjeta_ultimos4
from {{ ref('map_pagos') }}
