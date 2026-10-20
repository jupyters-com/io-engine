"""Prueba real contra Zetaris: manda UNA consulta y muestra quién respondió.

    python scripts/probar_zetaris.py
    python scripts/probar_zetaris.py "SELECT COUNT(*) AS n FROM io_pagos.disputes"

Lee ZETARIS_URL, ZETARIS_API_TOKEN y ZETARIS_ORG_ID de .env.local (en la raíz del repo).
Nunca imprime el token.
"""

import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)  # para que encuentre .env.local y escriba en logs/
os.environ["IO_MOTOR"] = "zetaris"
os.environ.setdefault("IO_RUN_ID", "prueba-zetaris")
os.environ.setdefault("IO_DUCKDB", "datos/io.duckdb")  # respaldo si Zetaris no responde

from motor.consultar import consultar  # noqa: E402  (carga .env.local al importar)

sql = sys.argv[1] if len(sys.argv) > 1 else "SELECT COUNT(*) AS n FROM io_pagos.disputes"
print("URL de Zetaris:", os.getenv("ZETARIS_URL") or "(falta)")
print("Token cargado: ", "sí" if os.getenv("ZETARIS_API_TOKEN") else "NO (falta en .env.local)")
print("Org ID:        ", os.getenv("ZETARIS_ORG_ID") or "(vacío)")
print("SQL:           ", sql)

r = consultar(sql)
print()
print("Respondió:", r["motor"], "| respaldo:", r["respaldo"], "|", r["ms"], "ms")
if r.get("motivo_respaldo"):
    print("Por qué no respondió Zetaris:", r["motivo_respaldo"])
print(json.dumps({k: r[k] for k in ("ok", "error", "columnas", "filas") if k in r},
                 ensure_ascii=False, indent=2))
