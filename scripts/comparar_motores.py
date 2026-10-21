"""DoD 3: la MISMA consulta, una vez con Zetaris y otra con DuckDB, y se comparan las filas.

    python scripts/comparar_motores.py

Necesita: datos/io.duckdb con dbt corrido, las vistas de zetaris/canonico.sql creadas en Zetaris
y las credenciales en .env.local. Cada consulta deja dos líneas en logs/consultar.jsonl
(motor=zetaris y motor=duckdb) con el mismo run_id.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)
os.environ.setdefault("IO_DUCKDB", "datos/io.duckdb")
os.environ["IO_RUN_ID"] = "comparar-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

from motor.consultar import consultar  # noqa: E402

CONSULTAS = {
    "Decisiones de IO": """
        SELECT decision, razon_decision, count(*) AS n
        FROM canonico.disputas
        GROUP BY decision, razon_decision
        ORDER BY n DESC, razon_decision""",
    "Caso 3 · pico del 16 al 30-sep": """
        SELECT transportista, region,
               count(*) AS disputas,
               sum(CASE WHEN entrega_tarde OR extraviado THEN 1 ELSE 0 END) AS tarde_o_extraviado,
               sum(CASE WHEN reclamo_previo THEN 1 ELSE 0 END)              AS con_reclamo_previo
        FROM canonico.disputas
        WHERE abierta_en >= TIMESTAMP '2026-09-16 00:00:00'
          AND abierta_en <  TIMESTAMP '2026-10-01 00:00:00'
        GROUP BY transportista, region
        ORDER BY disputas DESC, transportista, region""",
    "Filas por tabla": """
        SELECT 'clientes' AS tabla, count(*) AS n FROM canonico.clientes
        UNION ALL SELECT 'pagos', count(*) FROM canonico.pagos
        UNION ALL SELECT 'envios', count(*) FROM canonico.envios
        UNION ALL SELECT 'mensajes_soporte', count(*) FROM canonico.mensajes_soporte
        UNION ALL SELECT 'disputas', count(*) FROM canonico.disputas
        ORDER BY tabla""",
}


def como_texto(filas):
    # Zetaris devuelve todo como texto; DuckDB con su tipo. Se comparan como texto.
    return [{c: (str(v).lower() if isinstance(v, bool) else str(v)) for c, v in f.items()} for f in filas]


def correr(sql, motor):
    os.environ["IO_MOTOR"] = motor
    return consultar(sql)


iguales = True
for titulo, sql in CONSULTAS.items():
    z, d = correr(sql, "zetaris"), correr(sql, "duckdb")
    print(f"\n=== {titulo}")
    print(f"  zetaris: motor={z['motor']} respaldo={z['respaldo']} ok={z['ok']} {z['ms']} ms")
    print(f"  duckdb : motor={d['motor']} respaldo={d['respaldo']} ok={d['ok']} {d['ms']} ms")
    if not (z["ok"] and d["ok"]):
        print("  ERROR:", z.get("error") or z.get("motivo_respaldo") or d.get("error"))
        iguales = False
        continue
    if z["motor"] != "zetaris":
        print("  Zetaris no respondió:", z.get("motivo_respaldo"))
        iguales = False
    misma = como_texto(z["filas"]) == como_texto(d["filas"])
    iguales = iguales and misma
    print("  Mismas filas:", "SÍ" if misma else "NO")
    for f in como_texto(d["filas"]):
        print("   ", " · ".join(f.values()))
    if not misma:
        print("  Zetaris devolvió:")
        for f in como_texto(z["filas"]):
            print("   ", " · ".join(f.values()))

print("\nResultado:", "los dos motores dan lo mismo" if iguales else "hay diferencias (ver arriba)")
print("Log:", os.getenv("IO_LOG", "logs/consultar.jsonl"), "· run_id", os.environ["IO_RUN_ID"])
sys.exit(0 if iguales else 1)
