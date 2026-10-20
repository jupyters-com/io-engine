-- Capa de origen: exportación del sistema de tickets tal cual viene.
select ticket, solicitante, pedido, creado, categoria, mensaje, estado
from {{ source('crudo', 'soporte_tickets') }}
