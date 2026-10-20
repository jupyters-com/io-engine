select
    d.id                                            as disputa_id,
    d.charge                                        as pago_id,
    c.metadata__order_id                            as pedido_id,
    c.customer                                      as cliente_id,
    d.reason                                        as motivo,
    d.status                                        as estado,
    d.amount / 100.0                                as monto,
    to_timestamp(d.created) at time zone 'UTC'           as abierta_en,
    to_timestamp(d.evidence_due_by) at time zone 'UTC'   as vence_en
from {{ ref('org_stripe__disputas') }} d
left join {{ ref('org_stripe__cargos') }} c on c.id = d.charge
