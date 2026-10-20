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


class MotorNoDisponible(Exception):
    """El motor principal (Zetaris) no pudo responder; se usa DuckDB como respaldo."""


MOTORES = ("duckdb", "zetaris")


def _config():
    return {
        "db": Path(os.getenv("IO_DUCKDB", "datos/juguete.duckdb")),
        "log": Path(os.getenv("IO_LOG", "logs/consultar.jsonl")),
        "limite": int(os.getenv("IO_LIMITE_FILAS", "100")),
        "timeout_s": float(os.getenv("IO_TIMEOUT_S", "10")),
        "run_id": os.getenv("IO_RUN_ID", ""),
        # Quién intenta responder primero. Hoy solo existe DuckDB; "zetaris" queda
        # previsto para el adaptador del paso 8 (JPTRS-63).
        "motor": os.getenv("IO_MOTOR", "duckdb").strip().lower(),
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
# Los motores: cada uno recibe SQL ya validado y devuelve (columnas, filas crudas)
# ---------------------------------------------------------------------------
def _ejecutar_duckdb(sql_limpio: str, cfg: dict):
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
        return [d[0] for d in cur.description], cur.fetchall()
    finally:
        reloj.cancel()
        con.close()


def _ejecutar_zetaris(sql_limpio: str, cfg: dict):
    # Lugar reservado para el adaptador (JPTRS-63). Mientras no exista, Zetaris
    # "no está disponible" y responde DuckDB con respaldo=true: el mismo camino
    # que se verá en la DoD 3 con Zetaris apagado.
    raise MotorNoDisponible("El adaptador de Zetaris todavía no está implementado (JPTRS-63).")


def _ejecutar(sql_limpio: str, cfg: dict, estado: dict):
    """Devuelve (columnas, filas). Va anotando en `estado` qué motor está respondiendo,
    para que el log lo registre aunque la consulta termine en error."""
    if cfg["motor"] == "zetaris":
        estado["motor"] = "zetaris"
        try:
            return _ejecutar_zetaris(sql_limpio, cfg)
        except MotorNoDisponible as e:
            estado.update(respaldo=True, motivo_respaldo=str(e))
    estado["motor"] = "duckdb"
    return _ejecutar_duckdb(sql_limpio, cfg)


# ---------------------------------------------------------------------------
# La herramienta
# ---------------------------------------------------------------------------
def consultar(sql: str) -> dict:
    cfg = _config()
    inicio = time.perf_counter()
    resultado: dict
    # motor = None mientras ningún motor haya intentado responder (p. ej. consulta rechazada).
    estado = {"motor": None, "respaldo": False, "motivo_respaldo": None}

    try:
        if cfg["motor"] not in MOTORES:
            raise ConsultaRechazada(
                f"IO_MOTOR debe ser {' o '.join(MOTORES)}; se recibió: {cfg['motor']!r}."
            )
        sql_limpio = validar_sql(sql)
        columnas, crudas = _ejecutar(sql_limpio, cfg, estado)

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

    resultado["motor"], resultado["respaldo"] = estado["motor"], estado["respaldo"]
    if estado["motivo_respaldo"]:
        resultado["motivo_respaldo"] = estado["motivo_respaldo"]
    resultado["ms"] = round((time.perf_counter() - inicio) * 1000, 1)

    _escribir_log(cfg["log"], {
        "ts": datetime.now(timezone.utc).isoformat(),
        "herramienta": "consultar",
        "run_id": cfg["run_id"],
        "sql": " ".join((sql or "").split()),
        "motor": resultado["motor"],
        "respaldo": resultado["respaldo"],
        "motivo_respaldo": resultado.get("motivo_respaldo"),
        "ok": resultado["ok"],
        "error": resultado.get("error"),
        "n_filas": resultado.get("n_filas", 0),
        "truncado": resultado.get("truncado", False),
        "ms": resultado["ms"],
        "filas": resultado.get("filas", []),
    })
    return resultado
