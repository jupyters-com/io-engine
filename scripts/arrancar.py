"""UN comando que deja el motor de IO listo (es lo que corre Docker):

    python scripts/arrancar.py              # genera, carga, dbt, consulta de prueba y sirve MCP
    python scripts/arrancar.py --sin-servir # lo mismo, pero termina después de la consulta de prueba

Pasos:
  1. Genera los datos sintéticos (semilla 2026)      -> samples/sintetico/
  2. Los carga crudos en DuckDB con dlt               -> datos/io.duckdb, esquema crudo
  3. Corre dbt (origen -> mapeo -> canonico + pruebas) -> esquema canonico
  4. Hace una consulta de prueba con consultar(sql)   -> deja su línea en logs/consultar.jsonl
  5. Sirve consultar(sql) por MCP                     -> http://localhost:8000/mcp
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

DB = Path(os.environ.setdefault("IO_DUCKDB", "datos/io.duckdb")).resolve()
os.environ["IO_DUCKDB"] = str(DB)  # dbt corre en otra carpeta: ruta absoluta
os.environ.setdefault("SAMPLE_MODE", "true")
os.environ.setdefault("IO_RUN_ID", "arranque")

CONSULTA_DE_PRUEBA = """
SELECT transportista, region,
       count(*) AS disputas,
       sum(CASE WHEN entrega_tarde OR extraviado THEN 1 ELSE 0 END) AS tarde_o_extraviado,
       sum(CASE WHEN reclamo_previo THEN 1 ELSE 0 END)              AS con_reclamo_previo
FROM canonico.disputas
WHERE abierta_en >= TIMESTAMP '2026-09-16 00:00:00'
  AND abierta_en <  TIMESTAMP '2026-10-01 00:00:00'
GROUP BY transportista, region
ORDER BY disputas DESC, transportista, region
"""


def paso(n, texto):
    print(f"\n[{n}/5] {texto}", flush=True)
    return time.perf_counter()


def main():
    from motor.carga import cargar
    from motor.generador import generar

    t = paso(1, "Generando datos sintéticos (semilla 2026)...")
    r = generar("samples/sintetico")
    print(f"      {r['clientes']} clientes, {r['pedidos']} pedidos, {r['disputas']} disputas, "
          f"{r['tickets']} tickets ({time.perf_counter() - t:.1f} s)")

    t = paso(2, "Cargando las fuentes crudas en DuckDB con dlt...")
    cargar("samples/sintetico", DB)
    print(f"      {DB} · esquema crudo ({time.perf_counter() - t:.1f} s)")

    t = paso(3, "Corriendo dbt: origen -> mapeo -> canonico, con sus pruebas...")
    dbt = subprocess.run(
        [sys.executable, "-c", "from dbt.cli.main import cli; cli()", "build",
         "--project-dir", "dbt_io", "--profiles-dir", "dbt_io", "--quiet"],
        capture_output=True, text=True)
    if dbt.returncode != 0:
        print(dbt.stdout[-3000:], dbt.stderr[-3000:])
        sys.exit("      dbt falló; el motor no arranca.")
    print(f"      dbt build OK ({time.perf_counter() - t:.1f} s)")

    t = paso(4, "Consulta de prueba con consultar(sql) (caso 3, el pico de septiembre)...")
    from motor.consultar import consultar
    r = consultar(CONSULTA_DE_PRUEBA)
    print(f"      motor={r['motor']} respaldo={r['respaldo']} ok={r['ok']} {r['ms']} ms")
    if r.get("motivo_respaldo"):
        print(f"      (Zetaris no respondió: {r['motivo_respaldo']})")
    if not r["ok"]:
        sys.exit(f"      La consulta falló: {r['error']}")
    for f in r["filas"]:
        print("      " + " · ".join(str(v) for v in f.values()))
    log = Path(os.getenv("IO_LOG", "logs/consultar.jsonl"))
    ultima = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    print(f"      Evidencia: {log} (run_id={ultima['run_id']}, motor={ultima['motor']}, "
          f"{ultima['n_filas']} filas)")

    if "--sin-servir" in sys.argv:
        print("\nListo (sin servidor MCP).")
        return
    os.environ.setdefault("IO_MCP_TRANSPORTE", "http")
    host, puerto = os.getenv("IO_MCP_HOST", "127.0.0.1"), os.getenv("IO_MCP_PUERTO", "8000")
    paso(5, f"Sirviendo consultar(sql) por MCP en http://localhost:{puerto}/mcp (Ctrl+C para parar)")
    from motor.servidor_mcp import servir
    servir()


if __name__ == "__main__":
    main()
