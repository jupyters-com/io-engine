-- Esquema canónico de IO dentro de Zetaris (JPTRS-63).
--
-- Crea el contenedor "canonico" con las mismas 5 tablas y columnas que dbt crea en DuckDB
-- (dbt_io/models/canonico). Así el mismo SQL funciona en los dos motores:
--     SELECT ... FROM canonico.disputas
--
-- Lee de las 3 fuentes crudas registradas en Zetaris: io_pagos (customers, charges, disputes),
-- io_logistica (envios) e io_soporte (tickets).
--
-- Cómo correrlo: en el SQL Workspace, UNA sentencia a la vez, en orden (cada una termina en ";").
-- Los umbrales son los mismos de dbt_io/dbt_project.yml: fecha_corte 2026-09-30, 3 días de gracia,
-- ventana de zona ±7 días y umbral de zona 0.5. Si cambias uno allá, cámbialo aquí.
--
-- Se evitan subconsultas correlacionadas (la guía de Zetaris las marca como poco confiables):
-- todo se resuelve con JOIN y GROUP BY.

-- 1 · Contenedor (solo la primera vez; no tiene IF NOT EXISTS)
CREATE SCHEMASTORE CONTAINER canonico;

-- 2 · pagos: un cobro por pedido
CREATE OR REPLACE SCHEMASTORE VIEW pagos WITH CONTAINER canonico AS
SELECT
    CAST(id AS STRING)                                AS pago_id,
    CAST(order_id AS STRING)                          AS pedido_id,
    CAST(customer AS STRING)                          AS cliente_id,
    CAST(amount AS DOUBLE) / 100.0                    AS monto,
    upper(currency)                                   AS moneda,
    timestamp_seconds(CAST(created AS BIGINT))        AS pagado_en,
    CAST(billing_country AS STRING)                   AS pais_facturacion,
    CAST(ip_country AS STRING)                        AS pais_ip,
    CAST(risk_level AS STRING)                        AS nivel_riesgo,
    lpad(CAST(card_last4 AS STRING), 4, '0')          AS tarjeta_ultimos4
FROM io_pagos.charges;

-- 3 · clientes: un cliente por fila
CREATE OR REPLACE SCHEMASTORE VIEW clientes WITH CONTAINER canonico AS
SELECT
    CAST(c.id AS STRING)                              AS cliente_id,
    lower(trim(c.email))                              AS correo,
    timestamp_seconds(CAST(c.created AS BIGINT))      AS creado_en,
    p.primer_pago_en,
    coalesce(p.pagos_totales, 0)                      AS pagos_totales
FROM io_pagos.customers c
LEFT JOIN (
    SELECT customer,
           min(timestamp_seconds(CAST(created AS BIGINT))) AS primer_pago_en,
           count(*)                                        AS pagos_totales
    FROM io_pagos.charges
    GROUP BY customer
) p ON p.customer = c.id;

-- 4 · envios: un envío por pedido, con las definiciones de entrega
CREATE OR REPLACE SCHEMASTORE VIEW envios WITH CONTAINER canonico AS
WITH base AS (
    SELECT
        CAST(guia AS STRING)                                          AS envio_id,
        concat('ORD-', CAST(nro_pedido AS STRING))                    AS pedido_id,
        CAST(transportista AS STRING)                                 AS transportista,
        CAST(region AS STRING)                                        AS region,
        to_date(CAST(fecha_despacho AS STRING), 'dd/MM/yyyy')         AS despachado_en,
        to_date(CAST(fecha_prometida AS STRING), 'dd/MM/yyyy')        AS prometido_en,
        CASE WHEN fecha_entrega IS NULL OR trim(CAST(fecha_entrega AS STRING)) = '' THEN NULL
             ELSE to_date(CAST(fecha_entrega AS STRING), 'dd/MM/yyyy') END AS entregado_en,
        lower(estado)                                                 AS estado,
        lower(prueba_entrega)                                         AS prueba_entrega,
        lower(tipo_destino)                                           AS tipo_destino
    FROM io_logistica.envios
),
definido AS (
    SELECT
        *,
        (estado = 'entregado' AND prueba_entrega IN ('firma', 'foto'))           AS entrega_confirmada,
        (estado = 'extraviado')                                                   AS extraviado,
        CASE WHEN entregado_en IS NOT NULL THEN entregado_en > prometido_en
             ELSE DATE '2026-09-30' > date_add(prometido_en, 3) END               AS entrega_tarde,
        greatest(0, datediff(coalesce(entregado_en, DATE '2026-09-30'), prometido_en)) AS dias_atraso
    FROM base
),
zona AS (
    SELECT a.envio_id,
           count(*)                                                AS envios_zona,
           avg(CASE WHEN b.entrega_tarde THEN 1.0 ELSE 0.0 END)    AS tasa_tarde_zona
    FROM definido a
    JOIN definido b
      ON  b.transportista = a.transportista
      AND b.region = a.region
      AND b.prometido_en BETWEEN date_sub(a.prometido_en, 7) AND date_add(a.prometido_en, 7)
    GROUP BY a.envio_id
)
SELECT
    d.*,
    z.envios_zona,
    round(z.tasa_tarde_zona, 3)       AS tasa_tarde_zona,
    z.tasa_tarde_zona >= 0.5          AS zona_con_atrasos
FROM definido d
JOIN zona z ON z.envio_id = d.envio_id;

-- 5 · mensajes_soporte: un mensaje por fila, unido a su cliente por correo
CREATE OR REPLACE SCHEMASTORE VIEW mensajes_soporte WITH CONTAINER canonico AS
SELECT
    CAST(t.ticket AS STRING)                                      AS mensaje_id,
    CAST(c.id AS STRING)                                          AS cliente_id,
    concat('ORD-', regexp_replace(CAST(t.pedido AS STRING), '^#', '')) AS pedido_id,
    CAST(t.creado AS TIMESTAMP)                                   AS creado_en,
    CAST(t.categoria AS STRING)                                   AS categoria,
    CAST(t.mensaje AS STRING)                                     AS texto,
    CAST(t.estado AS STRING)                                      AS estado
FROM io_soporte.tickets t
LEFT JOIN io_pagos.customers c ON lower(trim(c.email)) = lower(trim(t.solicitante));

-- 6 · disputas: una disputa por fila, con todo lo que el agente necesita y la decisión de IO
CREATE OR REPLACE SCHEMASTORE VIEW disputas WITH CONTAINER canonico AS
-- canonico.pagos se lee UNA sola vez (en "pg"): si una vista de Zetaris aparece dos veces en la
-- misma consulta, Zetaris falla con MISSING_ATTRIBUTES. Desde un CTE sí se puede repetir.
WITH pg AS (
    SELECT * FROM canonico.pagos
),
d AS (
    SELECT
        CAST(x.id AS STRING)                                   AS disputa_id,
        p.pago_id, p.pedido_id, p.cliente_id,
        CAST(x.reason AS STRING)                               AS motivo,
        CAST(x.status AS STRING)                               AS estado,
        CAST(x.amount AS DOUBLE) / 100.0                       AS monto,
        timestamp_seconds(CAST(x.created AS BIGINT))           AS abierta_en,
        timestamp_seconds(CAST(x.evidence_due_by AS BIGINT))   AS vence_en,
        p.nivel_riesgo, p.pais_facturacion, p.pais_ip, p.pagado_en
    FROM io_pagos.disputes x
    JOIN pg p ON p.pago_id = CAST(x.charge AS STRING)
),
previos AS (
    SELECT d.disputa_id, count(p2.pago_id) AS pedidos_previos
    FROM d LEFT JOIN pg p2
      ON p2.cliente_id = d.cliente_id AND p2.pagado_en < d.pagado_en
    GROUP BY d.disputa_id
),
disputas_antes AS (
    SELECT d.disputa_id, count(d2.disputa_id) AS disputas_previas
    FROM d LEFT JOIN d d2
      ON d2.cliente_id = d.cliente_id AND d2.abierta_en < d.abierta_en
    GROUP BY d.disputa_id
),
reclamos AS (
    SELECT DISTINCT d.disputa_id
    FROM d JOIN canonico.mensajes_soporte m
      ON m.cliente_id = d.cliente_id AND m.pedido_id = d.pedido_id AND m.creado_en < d.abierta_en
),
contexto AS (
    SELECT
        d.disputa_id, d.pago_id, d.pedido_id, d.cliente_id,
        d.motivo, d.estado, d.monto, d.abierta_en, d.vence_en,
        d.nivel_riesgo, d.pais_facturacion, d.pais_ip,
        e.envio_id, e.transportista, e.region, e.estado AS estado_envio,
        e.prueba_entrega, e.tipo_destino, e.prometido_en, e.entregado_en,
        coalesce(e.entrega_confirmada, false)  AS entrega_confirmada,
        coalesce(e.entrega_tarde, false)       AS entrega_tarde,
        coalesce(e.extraviado, false)          AS extraviado,
        e.dias_atraso,
        coalesce(e.zona_con_atrasos, false)    AS zona_con_atrasos,
        pv.pedidos_previos,
        da.disputas_previas,
        (r.disputa_id IS NOT NULL)             AS reclamo_previo
    FROM d
    JOIN previos pv        ON pv.disputa_id = d.disputa_id
    JOIN disputas_antes da ON da.disputa_id = d.disputa_id
    LEFT JOIN reclamos r   ON r.disputa_id = d.disputa_id
    LEFT JOIN canonico.envios e ON e.pedido_id = d.pedido_id
),
senales AS (
    SELECT
        *,
        pedidos_previos = 0               AS senal_cliente_nuevo,
        nivel_riesgo = 'highest'          AS senal_riesgo_alto,
        pais_ip <> pais_facturacion       AS senal_pais_distinto,
        tipo_destino = 'punto_retiro'     AS senal_punto_retiro
    FROM contexto
),
definiciones AS (
    SELECT
        *,
        CAST(senal_cliente_nuevo AS INT) + CAST(senal_riesgo_alto AS INT)
          + CAST(senal_pais_distinto AS INT) + CAST(senal_punto_retiro AS INT) AS senales_fraude
    FROM senales
)
SELECT
    *,
    senales_fraude >= 2                                                     AS sospecha_fraude,
    (entrega_tarde OR extraviado) AND zona_con_atrasos                     AS causa_operativa,
    entrega_confirmada AND NOT reclamo_previo AND senales_fraude < 2       AS vale_pelear,
    CASE WHEN entrega_confirmada AND NOT reclamo_previo AND senales_fraude < 2
         THEN 'pelear' ELSE 'no_pelear' END                                 AS decision,
    CASE
        WHEN extraviado OR entregado_en IS NULL THEN 'sin_entrega'
        WHEN senales_fraude >= 2                THEN 'sospecha_de_fraude'
        WHEN NOT entrega_confirmada             THEN 'sin_prueba_de_entrega'
        WHEN reclamo_previo                     THEN 'reclamo_previo'
        ELSE 'entrega_confirmada_sin_reclamo'
    END                                                                     AS razon_decision
FROM definiciones;

-- 7 · Verificación (debe dar lo mismo que DuckDB): 20 pelear · 12 reclamo_previo · 4 sin_entrega ·
--     3 sin_prueba_de_entrega · 3 sospecha_de_fraude
SELECT decision, razon_decision, count(*) AS n
FROM canonico.disputas
GROUP BY decision, razon_decision
ORDER BY n DESC;
