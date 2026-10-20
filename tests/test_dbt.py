"""Pruebas del esquema canónico en dbt (JPTRS-62).

1. `dbt build` pasa (modelos y pruebas de dbt) sobre los datos sintéticos.
2. Ningún modelo canónico menciona una fuente: solo lee del mapeo.
3. Las definiciones dan la respuesta esperada en los tres casos plantados.
"""

import json
import re
from pathlib import Path

import duckdb
import pytest
import os
import subprocess
import sys

from motor.carga import cargar
from motor.generador import generar

RAIZ = Path(__file__).resolve().parents[1]
PROYECTO = RAIZ / "dbt_io"
PALABRAS_DE_FUENTE = ["source(", "crudo", "org_", "stripe", "logistica", "charges", "customers", "tickets"]


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("dbt")
    generar(tmp / "sintetico")
    db = tmp / "io.duckdb"
    cargar(tmp / "sintetico", db, pipelines_dir=str(tmp / "dlt"))
    # dbt corre en un proceso aparte, como desde la terminal (así no deja la base abierta)
    resultado = subprocess.run(
        [sys.executable, "-c", "from dbt.cli.main import cli; cli()", "build",
         "--project-dir", str(PROYECTO), "--profiles-dir", str(PROYECTO), "--target-path", str(tmp / "target")],
        env={**os.environ, "IO_DUCKDB": str(db)}, capture_output=True, text=True)
    hoja = json.loads((tmp / "sintetico" / "casos_plantados.json").read_text(encoding="utf-8"))
    return db, resultado, hoja


def test_dbt_build_pasa(base):
    _, resultado, _ = base
    assert resultado.returncode == 0, resultado.stdout[-3000:]
    assert "ERROR=0" in resultado.stdout


def test_la_capa_canonica_no_menciona_fuentes():
    for sql in (PROYECTO / "models" / "canonico").glob("*.sql"):
        texto = sql.read_text(encoding="utf-8").lower()
        encontradas = [p for p in PALABRAS_DE_FUENTE if p in texto]
        assert not encontradas, f"{sql.name} menciona {encontradas}"
        assert re.findall(r"ref\('([^']+)'\)", texto), f"{sql.name} no usa ref()"


def decision(db, disputa_id):
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute(
            "SELECT decision, razon_decision, causa_operativa FROM canonico.disputas WHERE disputa_id = ?",
            [disputa_id]).fetchone()
    finally:
        con.close()


def test_casos_plantados(base):
    db, _, hoja = base
    assert decision(db, hoja["caso1"]["disputa"]) == ("pelear", "entrega_confirmada_sin_reclamo", False)
    assert decision(db, hoja["caso2"]["disputa"]) == ("no_pelear", "sospecha_de_fraude", False)
    razones = {"tarde_con_reclamo": "reclamo_previo", "tarde_sin_reclamo": "entrega_confirmada_sin_reclamo",
               "extraviado": "sin_entrega"}
    for f in hoja["caso3"]:
        assert decision(db, f["disputa"]) == (f["decision"], razones[f["grupo"]], True), f["grupo"]
