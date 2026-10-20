select
    id                                              as pago_id,
    metadata__order_id                              as pedido_id,
    customer                                        as cliente_id,
    amount / 100.0                                  as monto,          -- centavos -> unidades
    upper(currency)                                 as moneda,
    to_timestamp(created) at time zone 'UTC'        as pagado_en,
    billing_country                                 as pais_facturacion,
    ip_country                                      as pais_ip,
    risk_level                                      as nivel_riesgo,
    card_last4                                      as tarjeta_ultimos4
from {{ ref('org_stripe__cargos') }}
