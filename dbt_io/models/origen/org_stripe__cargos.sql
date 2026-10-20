select id, customer, amount, currency, created, metadata__order_id,
       billing_country, ip_country, risk_level, card_last4
from {{ source('crudo', 'pagos_charges') }}
