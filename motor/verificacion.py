"""Una consulta por caso, sobre las tablas CRUDAS (criterio de aceptación de JPTRS-61).

Fíjate que, sin capa semántica, cada consulta tiene que traducir a mano:
'ORD-' || nro_pedido para unir pagos con envíos, '#' || nro_pedido para soporte,
lower(trim(...)) para el correo y strptime para las fechas dd/mm/aaaa.
Eso es justo lo que dbt hará una sola vez en el paso 7.
"""

import json
from pathlib import Path

import duckdb

DETALLE_DISPUTA = """
SELECT d.id AS disputa, d.reason AS motivo, to_timestamp(d.created)::DATE AS abierta,
       c.metadata__order_id AS pedido, c.amount / 100.0 AS monto_usd, c.risk_level AS riesgo,
       c.billing_country AS facturacion, c.ip_country AS pais_ip,
       e.transportista, e.region, e.fecha_prometida, e.fecha_entrega, e.estado,
       e.prueba_entrega, e.tipo_destino,
       (SELECT count(*) FROM crudo.pagos_charges c2
         WHERE c2.customer = c.customer AND c2.created < c.created) AS cargos_previos,
       (SELECT count(*) FROM crudo.pagos_disputes d2 JOIN crudo.pagos_charges c3 ON c3.id = d2.charge
         WHERE c3.customer = c.customer AND d2.created < d.created) AS disputas_previas,
       (SELECT count(*) FROM crudo.soporte_tickets t
         WHERE lower(trim(t.solicitante)) = cu.email AND t.creado::TIMESTAMPTZ < to_timestamp(d.created))
         AS tickets_antes_de_la_disputa
FROM crudo.pagos_disputes d
JOIN crudo.pagos_charges c    ON c.id = d.charge
JOIN crudo.pagos_customers cu ON cu.id = c.customer
JOIN crudo.envios e           ON 'ORD-' || e.nro_pedido = c.metadata__order_id
WHERE d.id = '{disputa}'
"""

PICO_POR_TRANSPORTISTA = """
WITH pico AS (
    SELECT d.id, to_timestamp(d.created) AS abierta, c.metadata__order_id AS pedido
    FROM crudo.pagos_disputes d JOIN crudo.pagos_charges c ON c.id = d.charge
    WHERE to_timestamp(d.created)::DATE BETWEEN DATE '2026-09-16' AND DATE '2026-09-30'
)
SELECT e.transportista, e.region,
       count(*) AS disputas,
       count(*) FILTER (WHERE e.estado = 'EXTRAVIADO'
           OR try_strptime(e.fecha_entrega, '%d/%m/%Y') > try_strptime(e.fecha_prometida, '%d/%m/%Y'))
           AS tarde_o_extraviado,
       count(*) FILTER (WHERE EXISTS (
           SELECT 1 FROM crudo.soporte_tickets t
           WHERE t.pedido = '#' || e.nro_pedido AND t.creado::TIMESTAMPTZ < pico.abierta))
           AS con_reclamo_previo
FROM pico JOIN crudo.envios e ON 'ORD-' || e.nro_pedido = pico.pedido
GROUP BY 1, 2
ORDER BY disputas DESC
"""


def consultas_por_caso(carpeta="samples/sintetico"):
    hoja = json.loads((Path(carpeta) / "casos_plantados.json").read_text(encoding="utf-8"))
    return {
        "Caso 1 · disputa que vale la pena pelear": DETALLE_DISPUTA.format(disputa=hoja["caso1"]["disputa"]),
        "Caso 2 · fraude real": DETALLE_DISPUTA.format(disputa=hoja["caso2"]["disputa"]),
        "Caso 3 · pico del 16 al 30-sep, por transportista y región": PICO_POR_TRANSPORTISTA,
    }


def verificar(db="datos/io.duckdb", carpeta="samples/sintetico"):
    con = duckdb.connect(str(db), read_only=True)
    try:
        return {titulo: con.execute(sql).df() for titulo, sql in consultas_por_caso(carpeta).items()}
    finally:
        con.close()
