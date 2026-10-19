"""Carga las tres fuentes en DuckDB con dlt (JPTRS-61).

Con SAMPLE_MODE=true (por defecto) lee los archivos sintéticos locales; no necesita claves.
Los datos quedan CRUDOS, tal como vienen, en el esquema "crudo". Traducirlos es trabajo de dbt (paso 7).
"""

import csv
import json
import os
from pathlib import Path

import dlt


def _fuentes_locales(carpeta: Path):
    pagos = json.loads((carpeta / "pagos.json").read_text(encoding="utf-8"))
    soporte = json.loads((carpeta / "soporte.json").read_text(encoding="utf-8"))
    with open(carpeta / "envios.csv", encoding="utf-8", newline="") as f:
        envios = list(csv.DictReader(f))  # todo como texto, tal cual viene en el CSV

    reemplazar = {"write_disposition": "replace"}  # cada carga deja la base igual: reproducible
    return [
        dlt.resource(pagos["customers"], name="pagos_customers", **reemplazar),
        dlt.resource(pagos["charges"], name="pagos_charges", **reemplazar),
        dlt.resource(pagos["disputes"], name="pagos_disputes", **reemplazar),
        dlt.resource(envios, name="envios", **reemplazar),
        dlt.resource(soporte["tickets"], name="soporte_tickets", **reemplazar),
    ]


def cargar(carpeta="samples/sintetico", db="datos/io.duckdb", pipelines_dir=None):
    if os.getenv("SAMPLE_MODE", "true").lower() != "true":
        raise SystemExit("Solo existe el modo de muestra: los conectores reales (Stripe, operador "
                         "logístico, tickets) no están implementados. Usa SAMPLE_MODE=true.")
    db = Path(db).resolve()
    db.parent.mkdir(parents=True, exist_ok=True)
    # dlt guarda el "estado" del pipeline, incluida la ruta de la base. Si lo guarda en la carpeta
    # del usuario (por defecto), una corrida en otra carpeta reutiliza la ruta vieja. Por eso lo
    # guardamos junto a la base: cada copia del proyecto tiene su propio estado.
    pipelines_dir = pipelines_dir or str(db.parent / ".dlt_pipelines")
    pipeline = dlt.pipeline(
        pipeline_name="io_motor",
        destination=dlt.destinations.duckdb(str(db)),
        dataset_name="crudo",
        pipelines_dir=pipelines_dir,
    )
    return pipeline.run(_fuentes_locales(Path(carpeta)))
