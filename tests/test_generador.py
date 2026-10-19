"""Pruebas del generador y la carga (JPTRS-61): reproducible, privado y con los tres casos del plan."""

import csv
import json
from datetime import date, datetime, timezone

import duckdb
import pytest

from motor.carga import cargar
from motor.generador import generar
from motor.verificacion import verificar


@pytest.fixture(scope="module")
def datos(tmp_path_factory):
    carpeta = tmp_path_factory.mktemp("sintetico")
    generar(carpeta)
    pagos = json.loads((carpeta / "pagos.json").read_text(encoding="utf-8"))
    soporte = json.loads((carpeta / "soporte.json").read_text(encoding="utf-8"))
    with open(carpeta / "envios.csv", encoding="utf-8") as f:
        envios = {r["nro_pedido"]: r for r in csv.DictReader(f)}
    hoja = json.loads((carpeta / "casos_plantados.json").read_text(encoding="utf-8"))
    return carpeta, pagos, envios, soporte, hoja


def dia(unix):
    return datetime.fromtimestamp(unix, timezone.utc).date()


def ddmm(texto):
    return datetime.strptime(texto, "%d/%m/%Y").date() if texto else None


def test_es_reproducible(tmp_path, datos):
    generar(tmp_path)
    for nombre in ["pagos.json", "envios.csv", "soporte.json", "casos_plantados.json"]:
        assert (tmp_path / nombre).read_bytes() == (datos[0] / nombre).read_bytes()


def test_volumen_del_plan(datos):
    _, pagos, envios, soporte, _ = datos
    assert len(pagos["customers"]) == 300
    assert len(pagos["charges"]) == len(envios) == 800
    assert len(soporte["tickets"]) == 150
    assert 40 <= len(pagos["disputes"]) <= 45
    por_cliente = {}
    for c in pagos["charges"]:
        por_cliente[c["customer"]] = por_cliente.get(c["customer"], 0) + 1
    assert sum(n > 1 for n in por_cliente.values()) == 180  # 60 % compra más de una vez


def test_sin_datos_personales_y_etiquetado(datos):
    _, pagos, _, soporte, _ = datos
    assert pagos["_synthetic"] is True and soporte["_synthetic"] is True
    assert all(c["email"].endswith("@ejemplo.test") for c in pagos["customers"])
    assert all(t["solicitante"].strip().lower().endswith("@ejemplo.test") for t in soporte["tickets"])
    assert set(pagos["customers"][0]) == {"id", "email", "created"}  # sin nombres ni direcciones


def test_fechas_de_2026(datos):
    _, pagos, _, _, _ = datos
    assert all(date(2026, 7, 1) <= dia(c["created"]) <= date(2026, 9, 30) for c in pagos["charges"])


def test_identificadores_distintos_entre_fuentes(datos):
    _, pagos, envios, soporte, _ = datos
    assert pagos["charges"][0]["metadata"]["order_id"].startswith("ORD-")
    assert next(iter(envios)).isdigit()
    assert soporte["tickets"][0]["pedido"].startswith("#")
    assert any(t["solicitante"] != t["solicitante"].strip().lower() for t in soporte["tickets"])


def test_caso1(datos):
    _, pagos, envios, soporte, hoja = datos
    h = hoja["caso1"]
    cargo = next(c for c in pagos["charges"] if c["id"] == h["cargo"])
    previos = [c for c in pagos["charges"] if c["customer"] == cargo["customer"] and c["created"] < cargo["created"]]
    e = envios[h["pedido"].removeprefix("ORD-")]
    assert len(previos) == 4 and cargo["risk_level"] == "normal"
    assert e["estado"] == "ENTREGADO" and e["prueba_entrega"] == "FIRMA"
    assert ddmm(e["fecha_entrega"]) < ddmm(e["fecha_prometida"])
    assert not [t for t in soporte["tickets"] if t["solicitante"].strip().lower() == h["correo"]]


def test_caso2(datos):
    _, pagos, envios, _, hoja = datos
    h = hoja["caso2"]
    cargo = next(c for c in pagos["charges"] if c["id"] == h["cargo"])
    assert cargo["risk_level"] == "highest" and cargo["ip_country"] != cargo["billing_country"]
    assert sum(c["customer"] == cargo["customer"] for c in pagos["charges"]) == 1
    assert envios[h["pedido"].removeprefix("ORD-")]["tipo_destino"] == "PUNTO_RETIRO"


def test_caso3_el_pico(datos):
    _, pagos, envios, soporte, hoja = datos
    cargos = {c["id"]: c for c in pagos["charges"]}
    pico = [d for d in pagos["disputes"] if date(2026, 9, 16) <= dia(d["created"]) <= date(2026, 9, 30)]
    antes = [d for d in pagos["disputes"] if date(2026, 9, 1) <= dia(d["created"]) <= date(2026, 9, 15)]
    assert len(pico) == 18 and len(antes) == 4
    assert sum(d["reason"] in ("fraudulent", "unrecognized") for d in pico) == 10

    def envio(d):
        return envios[cargos[d["charge"]]["metadata"]["order_id"].removeprefix("ORD-")]

    re_norte = [d for d in pico if envio(d)["transportista"] == "RapidEnvio" and envio(d)["region"] == "Norte"]
    assert len(re_norte) == 14
    extraviados = [d for d in re_norte if envio(d)["estado"] == "EXTRAVIADO"]
    tarde = [d for d in re_norte if d not in extraviados]
    assert len(extraviados) == 4
    assert all(ddmm(envio(d)["fecha_entrega"]) > ddmm(envio(d)["fecha_prometida"]) for d in tarde)
    reclamos = [d for d in re_norte if any(t["pedido"] == "#" + envio(d)["nro_pedido"]
                and datetime.fromisoformat(t["creado"]) < datetime.fromtimestamp(d["created"], timezone.utc)
                for t in soporte["tickets"])]
    assert len(reclamos) == 12
    # RapidEnvio fuera del Norte entrega a tiempo en el mismo período
    for e in envios.values():
        if e["transportista"] == "RapidEnvio" and e["region"] != "Norte" and e["fecha_entrega"]:
            assert ddmm(e["fecha_entrega"]) <= ddmm(e["fecha_prometida"])
    assert [f["decision"] for f in hoja["caso3"]].count("pelear") == 2


def test_carga_en_duckdb_y_una_consulta_por_caso(tmp_path, datos):
    carpeta = datos[0]
    db = tmp_path / "io.duckdb"
    cargar(carpeta, db, pipelines_dir=str(tmp_path / "dlt"))
    con = duckdb.connect(str(db), read_only=True)
    filas = dict(con.execute(
        "SELECT table_name, estimated_size FROM duckdb_tables() WHERE schema_name = 'crudo' "
        "AND table_name NOT LIKE '_dlt%'").fetchall())
    con.close()
    assert set(filas) == {"pagos_customers", "pagos_charges", "pagos_disputes", "envios", "soporte_tickets"}

    caso1, caso2, caso3 = verificar(db, carpeta).values()
    assert caso1.iloc[0]["cargos_previos"] == 4 and caso1.iloc[0]["tickets_antes_de_la_disputa"] == 0
    assert caso2.iloc[0]["riesgo"] == "highest" and caso2.iloc[0]["tipo_destino"] == "PUNTO_RETIRO"
    top = caso3.iloc[0]
    assert (top["transportista"], top["region"], top["disputas"]) == ("RapidEnvio", "Norte", 14)
    assert top["tarde_o_extraviado"] == 14 and top["con_reclamo_previo"] == 12
