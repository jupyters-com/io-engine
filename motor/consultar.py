"""consultar(sql): la única puerta del agente a los datos. Solo lectura y con log.

El contrato está en CONTRATO_consultar.md. Esta parte no sabe nada de MCP:
es una función normal de Python, fácil de probar. servidor_mcp.py la expone
como herramienta para el agente.
"""

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb


class ConsultaRechazada(Exception):
    """La consulta no cumple el contrato y no se ejecuta."""


def _config():
    return {
        "db": Path(os.getenv("IO_DUCKDB", "datos/juguete.duckdb")),
        "log": Path(os.getenv("IO_LOG", "logs/consultar.jsonl")),
        "limite": int(os.getenv("IO_LIMITE_FILAS", "100")),
        "timeout_s": float(os.getenv("IO_TIMEOUT_S", "10")),
        "run_id": os.getenv("IO_RUN_ID", ""),
    }


# ---------------------------------------------------------------------------
# Barrera 1: revisar la sentencia ANTES de ejecutarla
# ---------------------------------------------------------------------------
def validar_sql(sql: str) -> str:
    """Devuelve el SQL limpio si es UNA sola lectura; si no, lanza ConsultaRechazada."""
    if not sql or not sql.strip():
        raise ConsultaRechazada("La consulta está vacía.")

    try:
        # DuckDB analiza el texto y dice qué tipo de sentencia es cada una.
        sentencias = duckdb.connect().extract_statements(sql)
    except duckdb.Error as e:
        raise ConsultaRechazada(f"SQL inválido: {e}") from e

    if len(sentencias) != 1:
        raise ConsultaRechazada(
            f"Se permite una sola sentencia por llamada; se recibieron {len(sentencias)}."
        )
    tipo = sentencias[0].type
    if tipo != duckdb.StatementType.SELECT:
        raise ConsultaRechazada(
            f"Solo se permiten consultas de lectura (SELECT). Se recibió: {tipo.name}."
        )
    return sql.strip().rstrip(";").strip()


def _a_texto(valor):
    """Fechas, decimales, etc. -> texto, para que todo sea JSON."""
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor
    return str(valor)


def _escribir_log(ruta: Path, registro: dict):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# La herramienta
# ---------------------------------------------------------------------------
def consultar(sql: str) -> dict:
    cfg = _config()
    inicio = time.perf_counter()
    resultado: dict

    try:
        sql_limpio = validar_sql(sql)

        # Barreras 2 y 3: base en solo lectura y sin acceso a archivos externos.
        con = duckdb.connect(
            str(cfg["db"]), read_only=True, config={"enable_external_access": False}
        )
        # Límite de tiempo: si se pasa, se interrumpe la consulta.
        reloj = threading.Timer(cfg["timeout_s"], con.interrupt)
        reloj.start()
        try:
            # Pedimos una fila de más para saber si hubo que cortar.
            cur = con.execute(f"SELECT * FROM ({sql_limpio}) AS q LIMIT {cfg['limite'] + 1}")
            columnas = [d[0] for d in cur.description]
            crudas = cur.fetchall()
        finally:
            reloj.cancel()
            con.close()

        truncado = len(crudas) > cfg["limite"]
        filas = [
            {c: _a_texto(v) for c, v in zip(columnas, fila)} for fila in crudas[: cfg["limite"]]
        ]
        resultado = {"ok": True, "columnas": columnas, "filas": filas,
                     "n_filas": len(filas), "truncado": truncado}

    except ConsultaRechazada as e:
        resultado = {"ok": False, "error": str(e)}
    except duckdb.InterruptException:
        resultado = {"ok": False, "error": f"La consulta superó el límite de {cfg['timeout_s']} s."}
    except duckdb.Error as e:
        resultado = {"ok": False, "error": f"Error de SQL: {e}"}

    resultado["ms"] = round((time.perf_counter() - inicio) * 1000, 1)

    _escribir_log(cfg["log"], {
        "ts": datetime.now(timezone.utc).isoformat(),
        "herramienta": "consultar",
        "run_id": cfg["run_id"],
        "sql": " ".join((sql or "").split()),
        "ok": resultado["ok"],
        "error": resultado.get("error"),
        "n_filas": resultado.get("n_filas", 0),
        "truncado": resultado.get("truncado", False),
        "ms": resultado["ms"],
        "filas": resultado.get("filas", []),
    })
    return resultado
