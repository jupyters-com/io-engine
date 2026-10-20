-- Una disputa por fila con TODO lo que el agente necesita para decidir, y la decisión de IO.
with contexto as (
    select
        d.disputa_id, d.pago_id, d.pedido_id, d.cliente_id,
        d.motivo, d.estado, d.monto, d.abierta_en, d.vence_en,
        p.nivel_riesgo, p.pais_facturacion, p.pais_ip,
        e.envio_id, e.transportista, e.region, e.estado as estado_envio,
        e.prueba_entrega, e.tipo_destino, e.prometido_en, e.entregado_en,
        coalesce(e.entrega_confirmada, false) as entrega_confirmada,
        coalesce(e.entrega_tarde, false)      as entrega_tarde,
        coalesce(e.extraviado, false)         as extraviado,
        e.dias_atraso,
        coalesce(e.zona_con_atrasos, false)   as zona_con_atrasos,
        (select count(*) from {{ ref('pagos') }} p2
          where p2.cliente_id = d.cliente_id and p2.pagado_en < p.pagado_en)        as pedidos_previos,
        (select count(*) from {{ ref('map_disputas') }} d2
          where d2.cliente_id = d.cliente_id and d2.abierta_en < d.abierta_en)      as disputas_previas,
        exists (select 1 from {{ ref('mensajes_soporte') }} m
                 where m.cliente_id = d.cliente_id and m.pedido_id = d.pedido_id
                   and m.creado_en < d.abierta_en)                                   as reclamo_previo
    from {{ ref('map_disputas') }} d
    join {{ ref('pagos') }} p using (pago_id)
    left join {{ ref('envios') }} e on e.pedido_id = d.pedido_id
),
senales as (
    select
        *,
        pedidos_previos = 0                 as senal_cliente_nuevo,
        nivel_riesgo = 'highest'            as senal_riesgo_alto,
        pais_ip <> pais_facturacion         as senal_pais_distinto,
        tipo_destino = 'punto_retiro'       as senal_punto_retiro
    from contexto
),
definiciones as (
    select
        *,
        senal_cliente_nuevo::int + senal_riesgo_alto::int
          + senal_pais_distinto::int + senal_punto_retiro::int              as senales_fraude
    from senales
)
select
    *,
    senales_fraude >= 2                                                      as sospecha_fraude,
    (entrega_tarde or extraviado) and zona_con_atrasos                      as causa_operativa,
    entrega_confirmada and not reclamo_previo and senales_fraude < 2        as vale_pelear,
    case when entrega_confirmada and not reclamo_previo and senales_fraude < 2
         then 'pelear' else 'no_pelear' end                                  as decision,
    case
        -- Si el pedido nunca llegó, esa es la razón principal, aunque además haya señales de fraude
        when extraviado or entregado_en is null      then 'sin_entrega'
        when senales_fraude >= 2                     then 'sospecha_de_fraude'
        when not entrega_confirmada                  then 'sin_prueba_de_entrega'
        when reclamo_previo                          then 'reclamo_previo'
        else 'entrega_confirmada_sin_reclamo'
    end                                                                      as razon_decision
from definiciones
