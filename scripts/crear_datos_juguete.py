"""Crea datos/juguete.duckdb con dos tablas pequeñas y SINTÉTICAS para probar consultar(sql).

No son los datos del paso 6: solo sirven para probar la herramienta.
    python scripts/crear_datos_juguete.py
"""

from pathlib import Path

import duckdb

ruta = Path("datos/juguete.duckdb")
ruta.parent.mkdir(exist_ok=True)
ruta.unlink(missing_ok=True)

con = duckdb.connect(str(ruta))
con.execute("""
CREATE TABLE disputas AS SELECT * FROM (VALUES
    ('du_001', 'ORD-1001', 'fraudulent',           DATE '2026-09-22'),
    ('du_002', 'ORD-1002', 'product_not_received', DATE '2026-09-23'),
    ('du_003', 'ORD-1003', 'unrecognized',         DATE '2026-09-25'),
    ('du_004', 'ORD-1004', 'fraudulent',           DATE '2026-09-18')
) AS t(disputa_id, pedido_id, motivo, abierta_en)
""")
con.execute("""
CREATE TABLE envios AS SELECT * FROM (VALUES
    ('ORD-1001', 'RapidEnvio', 'Norte',  DATE '2026-09-12', DATE '2026-09-19'),
    ('ORD-1002', 'RapidEnvio', 'Norte',  DATE '2026-09-13', NULL),
    ('ORD-1003', 'RapidEnvio', 'Norte',  DATE '2026-09-14', DATE '2026-09-21'),
    ('ORD-1004', 'PaqueteYa',  'Sur',    DATE '2026-09-12', DATE '2026-09-13')
) AS t(pedido_id, transportista, region, prometido_en, entregado_en)
""")
con.execute("COMMENT ON TABLE disputas IS 'SINTETICO · datos de juguete para JPTRS-52'")
con.close()
print(f"Base creada: {ruta}")
