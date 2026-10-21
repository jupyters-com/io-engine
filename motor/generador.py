"""Generador de datos SINTÉTICOS de contracargos (JPTRS-61), según el plan de JPTRS-54.

Escribe tres fuentes, cada una con su propio formato y su propia forma de nombrar las cosas:
    samples/sintetico/pagos.json    -> estilo Stripe: customers, charges, disputes
    samples/sintetico/envios.csv    -> exportación del operador logístico
    samples/sintetico/soporte.json  -> exportación del sistema de tickets
y además casos_plantados.json, la "hoja de respuestas" (no se carga en la base).

Con la misma semilla genera siempre exactamente los mismos datos.
"""

import csv
import json
import random
import string
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

SEMILLA = 2026
INICIO, CORTE = date(2026, 7, 1), date(2026, 9, 30)  # período de los datos
N_CLIENTES, N_PEDIDOS, N_TICKETS = 300, 800, 150

TRANSPORTISTAS = {"RapidEnvio": "RE-7", "CargoSur": "CS-3", "PaqueteYa": "PY-8"}
REGIONES = ["Norte", "Centro", "Sur"]
# Caso 3: RapidEnvio se atrasa en el Norte para entregas prometidas en esta ventana
ATRASO_DESDE, ATRASO_HASTA = date(2026, 9, 8), date(2026, 9, 25)
TARJETAS_PRUEBA = ["4242", "0077", "5556", "4444", "0005"]  # últimos 4 de tarjetas de prueba de Stripe

MENSAJES = {
    "donde_esta_mi_pedido": ["Hola, mi pedido todavía no llega y ya pasó la fecha.",
                             "¿Dónde está mi pedido? El seguimiento no se actualiza.",
                             "Mi compra debía llegar hace días, ¿me ayudan?"],
    "producto_danado": ["El producto llegó con la caja rota.", "Llegó dañado, ¿cómo lo cambio?"],
    "cargo_no_reconocido": ["Veo un cargo que no reconozco en mi tarjeta."],
    "consulta": ["¿Tienen otra talla disponible?", "¿Puedo cambiar la dirección de envío?",
                 "¿Cuánto tarda el envío a mi ciudad?"],
}


class _Generador:
    def __init__(self, semilla):
        self.r = random.Random(semilla)
        self.pedidos, self.disputas, self.tickets = [], [], []
        self.casos = {}

    # --- utilidades ------------------------------------------------------
    def id_stripe(self, prefijo):
        return prefijo + "".join(self.r.choices(string.ascii_letters + string.digits, k=14))

    def fecha_entre(self, a: date, b: date) -> date:
        return a + timedelta(days=self.r.randint(0, (b - a).days))

    def momento(self, d: date) -> datetime:
        return datetime.combine(d, time(self.r.randint(9, 21), self.r.randint(0, 59)))

    # --- clientes ---------------------------------------------------------
    def crear_clientes(self):
        self.clientes = [{"id": self.id_stripe("cus_"), "email": f"cliente{i:03d}@ejemplo.test"}
                         for i in range(1, N_CLIENTES + 1)]
        orden = list(range(N_CLIENTES))
        self.r.shuffle(orden)
        self.c_caso1, self.c_caso2 = orden[0], orden[1]
        self.c_caso3 = orden[2:16]                 # 14 clientes del pico
        self.c_fondo = orden[16:]                  # 284 clientes de relleno

    # --- pedidos ----------------------------------------------------------
    def pedido(self, cliente, fecha, *, transportista=None, region=None, monto=None, despacho=None,
               prometida=None, entrega="auto", estado=None, prueba=None, destino=None,
               riesgo=None, ip=None, etiqueta=None):
        r = self.r
        transportista = transportista or r.choice(list(TRANSPORTISTAS))
        region = region or r.choice(REGIONES)
        despacho = despacho or fecha + timedelta(days=1)
        prometida = prometida or despacho + timedelta(days=4)
        if entrega == "auto":
            atrasado = (transportista == "RapidEnvio" and region == "Norte"
                        and ATRASO_DESDE <= prometida <= ATRASO_HASTA)
            entrega = prometida + timedelta(days=r.randint(5, 9) if atrasado else r.choice([-1, 0, 0, 0]))
        if estado is None:
            if entrega is None or entrega > CORTE:
                estado, entrega = "EN_TRANSITO", None
            else:
                estado = r.choices(["ENTREGADO", "DEVUELTO"], [98, 2])[0]
        if prueba is None:
            prueba = "NINGUNA" if estado != "ENTREGADO" else r.choices(["FIRMA", "FOTO", "NINGUNA"], [5, 4, 1])[0]
        p = {
            "cliente": cliente, "fecha": fecha, "momento": self.momento(fecha),
            "monto": monto if monto is not None else r.randint(1500, 25000),
            "transportista": transportista, "region": region,
            "despacho": despacho, "prometida": prometida, "entrega": entrega,
            "estado": estado, "prueba": prueba,
            "destino": destino or r.choices(["DOMICILIO", "PUNTO_RETIRO"], [85, 15])[0],
            "riesgo": riesgo or r.choices(["normal", "elevated", "highest"], [93, 5, 2])[0],
            "facturacion": "CO",
            "ip": ip or ("CO" if r.random() < 0.97 else r.choice(["US", "MX", "ES"])),
            "tarjeta": r.choice(TARJETAS_PRUEBA), "etiqueta": etiqueta,
        }
        self.pedidos.append(p)
        return p

    def pedidos_previos(self, cliente, n):
        """Pedidos normales, a tiempo, en julio y agosto."""
        for _ in range(n):
            self.pedido(cliente, self.fecha_entre(date(2026, 7, 1), date(2026, 8, 25)),
                        transportista=self.r.choice(["CargoSur", "PaqueteYa"]), estado="ENTREGADO",
                        riesgo="normal", ip="CO", destino="DOMICILIO")

    def disputa(self, pedido, fecha, motivo, etiqueta=None):
        d = {"pedido": pedido, "fecha": fecha, "motivo": motivo, "etiqueta": etiqueta}
        self.disputas.append(d)
        return d

    def ticket(self, cliente, pedido, fecha, categoria):
        t = {"cliente": cliente, "pedido": pedido, "momento": self.momento(fecha), "categoria": categoria}
        self.tickets.append(t)
        return t

    # --- caso 1: disputa que vale la pena pelear ---------------------------
    def plantar_caso1(self):
        c = self.c_caso1
        self.pedidos_previos(c, 4)
        p = self.pedido(c, date(2026, 9, 3), transportista="CargoSur", region="Centro", monto=12990,
                        despacho=date(2026, 9, 3), prometida=date(2026, 9, 7), entrega=date(2026, 9, 6),
                        estado="ENTREGADO", prueba="FIRMA", destino="DOMICILIO", riesgo="normal", ip="CO",
                        etiqueta="caso1")
        self.disputa(p, date(2026, 9, 29), "unrecognized", "caso1")

    # --- caso 2: fraude real ------------------------------------------------
    def plantar_caso2(self):
        c = self.c_caso2
        p = self.pedido(c, date(2026, 9, 10), transportista="PaqueteYa", region="Sur", monto=48900,
                        prometida=date(2026, 9, 15), entrega=date(2026, 9, 13), estado="ENTREGADO",
                        prueba="FOTO", destino="PUNTO_RETIRO", riesgo="highest", ip="NL", etiqueta="caso2")
        self.clientes[c]["creado"] = date(2026, 9, 10)
        self.disputa(p, date(2026, 9, 18), "fraudulent", "caso2")

    # --- caso 3: pico con causa operativa -----------------------------------
    def plantar_caso3(self):
        r = self.r
        # Índices 0-7: tarde con reclamo previo · 8-9: tarde, con firma, sin reclamo · 10-13: extraviados
        motivos = ["fraudulent", "unrecognized", "fraudulent", "product_not_received", "unrecognized",
                   "product_not_received", "fraudulent", "unrecognized", "fraudulent",
                   "product_not_received"] + ["product_not_received"] * 4
        nuevos = {5, 9, 11}  # clientes sin pedidos previos; el 11 además con riesgo "highest"
        for i, c in enumerate(self.c_caso3):
            if i not in nuevos:
                self.pedidos_previos(c, 3 if i == 0 else r.randint(1, 4))
            fecha = date(2026, 9, 7) if i == 0 else self.fecha_entre(date(2026, 9, 3), date(2026, 9, 13))
            prometida = fecha + timedelta(days=5)
            extraviado = i >= 10
            if extraviado:
                entrega, estado, prueba = None, "EXTRAVIADO", "NINGUNA"
            else:
                atraso = 7 if i == 0 else r.randint(5, 9)
                entrega, estado = prometida + timedelta(days=atraso), "ENTREGADO"
                prueba = "FIRMA" if i in (8, 9) else r.choice(["FIRMA", "FOTO"])
            p = self.pedido(c, fecha, transportista="RapidEnvio", region="Norte",
                            despacho=fecha + timedelta(days=1), prometida=prometida, entrega=entrega,
                            estado=estado, prueba=prueba, destino="DOMICILIO",
                            riesgo="highest" if i == 11 else "normal", ip="CO", etiqueta=f"caso3_{i}")
            if i == 0:
                f_disputa = date(2026, 9, 22)
            elif extraviado:
                f_disputa = max(date(2026, 9, 16), prometida + timedelta(days=r.randint(4, 8)))
            else:
                f_disputa = max(date(2026, 9, 16), entrega + timedelta(days=r.randint(1, 3)))
            f_disputa = min(f_disputa, date(2026, 9, 30))
            self.disputa(p, f_disputa, motivos[i], f"caso3_{i}")
            if i < 8 or extraviado:  # 12 reclamos previos
                tope = (entrega if entrega else f_disputa) - timedelta(days=1)
                f_ticket = date(2026, 9, 15) if i == 0 else self.fecha_entre(prometida + timedelta(days=1), tope)
                self.ticket(c, p, f_ticket, "donde_esta_mi_pedido")

    # --- relleno -------------------------------------------------------------
    def relleno(self):
        r = self.r
        n_restantes = N_PEDIDOS - len(self.pedidos)
        clientes = list(self.c_fondo)
        r.shuffle(clientes)
        # 60 % de los 300 compra más de una vez: ya hay 12 recurrentes plantados -> faltan 168
        recurrentes, unicos = clientes[:168], clientes[168:]
        cuentas = {c: 1 for c in unicos} | {c: 2 for c in recurrentes}
        for _ in range(n_restantes - sum(cuentas.values())):
            cuentas[r.choice(recurrentes)] += 1
        for c in clientes:
            for _ in range(cuentas[c]):
                self.pedido(c, self.fecha_entre(INICIO, CORTE - timedelta(days=2)))

    def disputas_de_relleno(self):
        """26 disputas de fondo: 20 en jul-ago, 4 del 1 al 15-sep, 2 del 16 al 30-sep."""
        r = self.r
        fondo = set(self.c_fondo)
        usados = set()
        ventanas = ([(date(2026, 7, 10), date(2026, 8, 31))] * 20 + [(date(2026, 9, 1), date(2026, 9, 15))] * 4
                    + [(date(2026, 9, 16), date(2026, 9, 30))] * 2)
        motivos_ultimos = ["fraudulent", "product_not_received"]
        for k, (a, b) in enumerate(ventanas):
            while True:
                p = r.choice(self.pedidos)
                if (p["cliente"] not in fondo or id(p) in usados or p["etiqueta"]
                        or (p["transportista"] == "RapidEnvio" and p["region"] == "Norte")):
                    continue
                inicio = max(a, p["fecha"] + timedelta(days=5))
                fin = min(b, p["fecha"] + timedelta(days=60))
                if inicio <= fin:
                    break
            usados.add(id(p))
            motivo = (motivos_ultimos[k - 24] if k >= 24
                      else r.choices(["fraudulent", "product_not_received", "unrecognized"], [4, 3, 3])[0])
            self.disputa(p, self.fecha_entre(inicio, fin), motivo)

    def tickets_de_relleno(self):
        r = self.r
        excluidos = {self.c_caso1, self.c_caso2, *self.c_caso3}
        candidatos = [p for p in self.pedidos if p["cliente"] not in excluidos]
        # Otros clientes de RapidEnvio·Norte atrasados también preguntan (el patrón no es solo de los que disputan)
        atrasados = [p for p in candidatos if p["transportista"] == "RapidEnvio" and p["region"] == "Norte"
                     and ATRASO_DESDE <= p["prometida"] <= ATRASO_HASTA]
        for p in atrasados[:8]:
            self.ticket(p["cliente"], p, min(CORTE, p["prometida"] + timedelta(days=2)), "donde_esta_mi_pedido")
        while len(self.tickets) < N_TICKETS:
            p = r.choice(candidatos)
            cat = r.choices(list(MENSAJES), [30, 20, 10, 40])[0]
            f = min(CORTE, p["fecha"] + timedelta(days=r.randint(1, 15)))
            self.ticket(p["cliente"], p, f, cat)

    # --- escribir las tres fuentes -----------------------------------------------
    def escribir(self, carpeta: Path):
        r = self.r
        carpeta.mkdir(parents=True, exist_ok=True)
        unix = lambda d, h=15: int(datetime.combine(d, time(h)).replace(tzinfo=timezone.utc).timestamp())

        # Números de pedido en orden cronológico, como en un sistema real
        self.pedidos.sort(key=lambda p: p["momento"])
        for n, p in enumerate(self.pedidos, start=1001):
            p["nro"], p["charge_id"] = n, self.id_stripe("ch_")
        primeros = {}
        for p in self.pedidos:
            primeros.setdefault(p["cliente"], p["fecha"])

        customers = []
        for i, c in enumerate(self.clientes):
            if i not in primeros:
                continue
            creado = c.get("creado") or primeros[i] - timedelta(days=r.randint(0, 120))
            customers.append({"id": c["id"], "email": c["email"], "created": unix(creado, 12)})

        charges = [{
            "id": p["charge_id"], "customer": self.clientes[p["cliente"]]["id"], "amount": p["monto"],
            "currency": "usd", "created": int(p["momento"].replace(tzinfo=timezone.utc).timestamp()),
            "metadata": {"order_id": f"ORD-{p['nro']}"}, "billing_country": p["facturacion"],
            "ip_country": p["ip"], "risk_level": p["riesgo"], "card_last4": p["tarjeta"],
        } for p in self.pedidos]

        self.disputas.sort(key=lambda d: (d["fecha"], d["pedido"]["nro"]))
        disputes = []
        for d in self.disputas:
            d["id"] = self.id_stripe("du_")
            vence = d["fecha"] + timedelta(days=14)
            status = r.choice(["won", "lost"]) if vence < CORTE else "needs_response"
            disputes.append({"id": d["id"], "charge": d["pedido"]["charge_id"], "reason": d["motivo"],
                             "status": status, "amount": d["pedido"]["monto"], "currency": "usd",
                             "created": unix(d["fecha"]), "evidence_due_by": unix(vence, 23)})

        pagos = {"_synthetic": True, "_generador": f"IO · semilla {SEMILLA}",
                 "customers": customers, "charges": charges, "disputes": disputes}
        (carpeta / "pagos.json").write_text(json.dumps(pagos, ensure_ascii=False, indent=1), encoding="utf-8")

        fmt = lambda d: d.strftime("%d/%m/%Y") if d else ""
        with open(carpeta / "envios.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")  # LF siempre, igual en Windows y Linux
            w.writerow(["guia", "nro_pedido", "transportista", "region", "fecha_despacho", "fecha_prometida",
                        "fecha_entrega", "estado", "prueba_entrega", "tipo_destino"])
            for p in self.pedidos:
                w.writerow([TRANSPORTISTAS[p["transportista"]] + str(p["nro"]), p["nro"], p["transportista"],
                            p["region"], fmt(p["despacho"]), fmt(p["prometida"]), fmt(p["entrega"]),
                            p["estado"], p["prueba"], p["destino"]])

        self.tickets.sort(key=lambda t: t["momento"])
        tickets = []
        for n, t in enumerate(self.tickets, start=5001):
            t["id"] = f"T-{n}"
            email = self.clientes[t["cliente"]]["email"]
            variante = r.choice([email, email.capitalize(), email.upper(), email + " "])
            local = t["momento"].replace(tzinfo=timezone(timedelta(hours=-4)))
            tickets.append({"ticket": t["id"], "solicitante": variante, "pedido": f"#{t['pedido']['nro']}",
                            "creado": local.isoformat(), "categoria": t["categoria"],
                            "mensaje": r.choice(MENSAJES[t["categoria"]]),
                            "estado": "resuelto" if t["momento"].date() < CORTE - timedelta(days=5) else "abierto"})
        soporte = {"_synthetic": True, "_generador": f"IO · semilla {SEMILLA}", "tickets": tickets}
        (carpeta / "soporte.json").write_text(json.dumps(soporte, ensure_ascii=False, indent=1), encoding="utf-8")

        (carpeta / "casos_plantados.json").write_text(
            json.dumps(self.hoja_de_respuestas(), ensure_ascii=False, indent=2), encoding="utf-8")

    def hoja_de_respuestas(self):
        def ficha(d):
            p = d["pedido"]
            return {"disputa": d["id"], "cargo": p["charge_id"], "cliente": self.clientes[p["cliente"]]["id"],
                    "correo": self.clientes[p["cliente"]]["email"], "pedido": f"ORD-{p['nro']}",
                    "guia": TRANSPORTISTAS[p["transportista"]] + str(p["nro"]),
                    "motivo": d["motivo"], "abierta": d["fecha"].isoformat()}
        por_etiqueta = {d["etiqueta"]: d for d in self.disputas if d["etiqueta"]}
        caso3 = []
        for i in range(14):
            f = ficha(por_etiqueta[f"caso3_{i}"])
            f["grupo"] = ("tarde_con_reclamo" if i < 8 else "tarde_sin_reclamo" if i < 10 else "extraviado")
            f["decision"] = "pelear" if 8 <= i < 10 else "no_pelear"
            tk = [t["id"] for t in self.tickets if t["pedido"] is por_etiqueta[f"caso3_{i}"]["pedido"]]
            f["ticket"] = tk[0] if tk else None
            caso3.append(f)
        return {
            "_nota": "Hoja de respuestas del generador. NO se carga en la base: el agente no debe verla.",
            "caso1": {**ficha(por_etiqueta["caso1"]), "decision": "pelear"},
            "caso2": {**ficha(por_etiqueta["caso2"]), "decision": "no_pelear"},
            "caso3": caso3,
        }


def generar(carpeta="samples/sintetico", semilla=SEMILLA) -> dict:
    g = _Generador(semilla)
    g.crear_clientes()
    g.plantar_caso1()
    g.plantar_caso2()
    g.plantar_caso3()
    g.relleno()
    g.disputas_de_relleno()
    g.tickets_de_relleno()
    g.escribir(Path(carpeta))
    return {"pedidos": len(g.pedidos), "disputas": len(g.disputas), "tickets": len(g.tickets),
            "clientes": len({p["cliente"] for p in g.pedidos})}
