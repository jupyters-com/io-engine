select id, charge, reason, status, amount, currency, created, evidence_due_by
from {{ source('crudo', 'pagos_disputes') }}
