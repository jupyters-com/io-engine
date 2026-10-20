"""Pruebas del contrato de consultar(sql). Se escribieron antes que la implementación.
    python -m pytest -q
"""

import json

import duckdb
import pytest

from motor.consultar import consultar


@pytest.fixture(autouse=True)
def base_de_prueba(tmp_path, monkeypatch):
    db = tmp_path / "prueba.duckdb"
    con = duckdb.connect(str(db))
    con.execute("CREATE TABLE disputas AS SELECT range AS id, 'fraudulent' AS motivo FROM range(150)")
    con.close()
    monkeypatch.setenv("IO_DUCKDB", str(db))
    monkeypatch.setenv("IO_LOG", str(tmp_path / "consultar.jsonl"))
    monkeypatch.setenv("IO_LIMITE_FILAS", "100")
    monkeypatch.setenv("IO_RUN_ID", "test")
    monkeypatch.delenv("IO_MOTOR", raising=False)
    return tmp_path


def leer_log(tmp_path):
    lineas = (tmp_path / "consultar.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(l) for l in lineas]


def test_select_devuelve_filas(base_de_prueba):
    r = consultar("SELECT id, motivo FROM disputas WHERE id < 3 ORDER BY id;")
    assert r["ok"] is True
    assert r["columnas"] == ["id", "motivo"]
    assert r["filas"] == [{"id": 0, "motivo": "fraudulent"},
                          {"id": 1, "motivo": "fraudulent"},
                          {"id": 2, "motivo": "fraudulent"}]


def test_with_select_se_permite():
    r = consultar("WITH x AS (SELECT count(*) AS n FROM disputas) SELECT n FROM x")
    assert r["ok"] and r["filas"] == [{"n": 150}]


@pytest.mark.parametrize("sql, palabra", [
    ("DROP TABLE disputas", "DROP"),
    ("DELETE FROM disputas", "DELETE"),
    ("INSERT INTO disputas VALUES (999, 'x')", "INSERT"),
    ("UPDATE disputas SET motivo = 'x'", "UPDATE"),
    ("CREATE TABLE t (a INT)", "CREATE"),
])
def test_escrituras_se_rechazan_con_error_claro(sql, palabra):
    r = consultar(sql)
    assert r["ok"] is False
    assert "Solo se permiten consultas de lectura" in r["error"]
    assert palabra in r["error"]
    assert consultar("SELECT count(*) AS n FROM disputas")["filas"] == [{"n": 150}]  # nada cambió


def test_varias_sentencias_se_rechazan():
    r = consultar("SELECT 1; DROP TABLE disputas")
    assert r["ok"] is False and "una sola sentencia" in r["error"]


def test_no_puede_leer_archivos_externos(tmp_path):
    archivo = tmp_path / "secreto.csv"
    archivo.write_text("a\n1\n")
    r = consultar(f"SELECT * FROM read_csv('{archivo}')")
    assert r["ok"] is False


def test_limite_de_filas():
    r = consultar("SELECT id FROM disputas")
    assert r["ok"] and r["n_filas"] == 100 and r["truncado"] is True


def test_error_de_sql_no_rompe_la_herramienta():
    r = consultar("SELECT columna_que_no_existe FROM disputas")
    assert r["ok"] is False and "Error de SQL" in r["error"]


def test_cada_llamada_deja_una_linea_en_el_log(base_de_prueba):
    consultar("SELECT id FROM disputas WHERE id = 7")
    consultar("DROP TABLE disputas")
    aceptada, rechazada = leer_log(base_de_prueba)

    assert aceptada["ok"] is True and aceptada["n_filas"] == 1
    assert aceptada["filas"] == [{"id": 7}]
    assert aceptada["run_id"] == "test" and aceptada["ms"] >= 0

    assert rechazada["ok"] is False and "DROP" in rechazada["error"]
    assert rechazada["sql"] == "DROP TABLE disputas"


# --- Qué motor respondió (pedido de JPTRS-47: el video y la DoD 3 lo verifican en el log) ---

def test_log_registra_que_motor_respondio(base_de_prueba):
    r = consultar("SELECT id FROM disputas WHERE id = 1")
    assert r["motor"] == "duckdb" and r["respaldo"] is False
    linea = leer_log(base_de_prueba)[0]
    assert linea["motor"] == "duckdb" and linea["respaldo"] is False
    assert linea["motivo_respaldo"] is None


def test_consulta_rechazada_no_tiene_motor(base_de_prueba):
    r = consultar("DROP TABLE disputas")
    assert r["motor"] is None and r["respaldo"] is False
    assert leer_log(base_de_prueba)[0]["motor"] is None


def test_error_de_sql_registra_el_motor_que_lo_intento(base_de_prueba):
    consultar("SELECT columna_que_no_existe FROM disputas")
    linea = leer_log(base_de_prueba)[0]
    assert linea["ok"] is False and linea["motor"] == "duckdb"


def test_zetaris_no_disponible_responde_duckdb_como_respaldo(base_de_prueba, monkeypatch):
    # Mientras no exista el adaptador (JPTRS-63), pedir Zetaris equivale a "Zetaris apagado".
    monkeypatch.setenv("IO_MOTOR", "zetaris")
    r = consultar("SELECT count(*) AS n FROM disputas")
    assert r["ok"] and r["filas"] == [{"n": 150}]
    assert r["motor"] == "duckdb" and r["respaldo"] is True
    linea = leer_log(base_de_prueba)[0]
    assert linea["motor"] == "duckdb" and linea["respaldo"] is True
    assert "Zetaris" in linea["motivo_respaldo"]


def test_motor_desconocido_se_rechaza(monkeypatch):
    monkeypatch.setenv("IO_MOTOR", "postgres")
    r = consultar("SELECT 1")
    assert r["ok"] is False and "IO_MOTOR" in r["error"] and r["motor"] is None
