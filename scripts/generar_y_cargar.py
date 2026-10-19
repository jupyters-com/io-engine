"""UN comando que genera los datos sintéticos, los carga en DuckDB con dlt y muestra una consulta por caso.

    python scripts/generar_y_cargar.py

Resultado: datos/io.duckdb con 5 tablas crudas en el esquema "crudo"
(pagos_customers, pagos_charges, pagos_disputes, envios, soporte_tickets).
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # para importar "motor" desde scripts/

import duckdb
import pandas as pd

from motor.carga import cargar
from motor.generador import generar
from motor.verificacion import verificar

CARPETA, DB = "samples/sintetico", "datos/io.duckdb"
os.environ.setdefault("SAMPLE_MODE", "true")

print("1/3 Generando datos sintéticos (semilla 2026)...")
resumen = generar(CARPETA)
print(f"    {resumen['clientes']} clientes, {resumen['pedidos']} pedidos, "
      f"{resumen['disputas']} disputas, {resumen['tickets']} tickets -> {CARPETA}/")

print("2/3 Cargando con dlt en DuckDB...")
cargar(CARPETA, DB)
con = duckdb.connect(DB, read_only=True)
for (tabla,) in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'crudo' "
        "AND table_name NOT LIKE '_dlt%' ORDER BY 1").fetchall():
    n = con.execute(f"SELECT count(*) FROM crudo.{tabla}").fetchone()[0]
    print(f"    crudo.{tabla:<18} {n:>4} filas")
con.close()

print("3/3 Una consulta por caso:")
pd.set_option("display.width", 200, "display.max_columns", 30)
for titulo, df in verificar(DB, CARPETA).items():
    print(f"\n--- {titulo} ---")
    print(df.T.to_string(header=False) if len(df) == 1 else df.to_string(index=False))
print(f"\nListo. Base: {DB}")
