# io-engine · el motor de datos de IO

El motor junta tres sistemas que no se hablan (pagos, logística y soporte), los traduce a un solo idioma y le da al agente **una sola puerta** para leerlos: la herramienta `consultar(sql)`, de solo lectura y con evidencia de cada consulta.

Todo corre con **datos sintéticos** (semilla 2026, correos `@ejemplo.test`): no hay datos reales ni claves en el repo.

## Un solo comando

Necesitas Docker Desktop abierto.

```
docker compose up --build
```

Ese comando:

1. genera los datos sintéticos,
2. los carga crudos en DuckDB con dlt,
3. corre dbt (origen → mapeo → canónico, con sus 40 pruebas),
4. hace una consulta de prueba con `consultar(sql)` y deja su línea en `logs/consultar.jsonl`,
5. deja `consultar(sql)` servido por MCP en `http://localhost:8000/mcp`.

La primera vez tarda unos minutos porque descarga Python y las librerías. Debe terminar mostrando el caso 3 (`RapidEnvio · Norte · 14 · 14 · 12`) y `Uvicorn running on http://0.0.0.0:8000`.

Para comprobarlo desde otra terminal, como lo haría el agente:

```
python scripts/probar_mcp_http.py
```

Para parar: `Ctrl+C`, o `docker compose down`.

### Sin Docker

```
pip install -r requirements.txt
python scripts/arrancar.py
```

## Componentes

| Componente | Qué hace en IO | Dónde vive |
| --- | --- | --- |
| **Generador sintético** | Fabrica, siempre igual, 300 clientes, 800 pedidos, 42 disputas y 150 tickets, con tres casos plantados. Cada fuente trae sus propias manías (centavos, fechas `dd/mm/aaaa`, pedidos como `ORD-1574`, `1574` o `#1574`). | `motor/generador.py` |
| **dlt** | Carga las tres fuentes **tal cual vienen** en DuckDB, esquema `crudo`. No arregla nada. | `motor/carga.py` |
| **DuckDB** | La base local donde viven el esquema crudo y el canónico. Es el motor de respaldo de las consultas. | `datos/io.duckdb` (se crea al arrancar) |
| **dbt** | Define **una sola vez** qué significa cada dato: `origen` (copia 1 a 1), `mapeo` (formatos unificados) y `canonico` (las 5 tablas del agente, con señales y la decisión de IO). La capa canónica no nombra ninguna fuente. | `dbt_io/`, reglas en `dbt_io/models/canonico/definiciones.md` |
| **`consultar(sql)`** | La única puerta del agente a los datos: una sola `SELECT`, máximo 100 filas, tiempo límite y una línea JSONL por llamada (qué se preguntó, qué filas recibió, qué motor respondió). | `motor/consultar.py`, contrato en `CONTRATO_consultar.md` |
| **MCP** | Expone `consultar(sql)` como herramienta estándar para agentes: por stdio o por HTTP (`/mcp`). | `motor/servidor_mcp.py` |
| **Adaptador de Zetaris** | Con `IO_MOTOR=zetaris`, `consultar(sql)` le pregunta a Zetaris, que une las fuentes sin copiarlas. Si Zetaris no responde (sin credenciales, caído o token rechazado), responde DuckDB y el log lo marca con `respaldo: true` y el motivo. | `motor/consultar.py`, vistas en `zetaris/canonico.sql` |
| **Docker** | Empaqueta todo para que corra igual en cualquier máquina con un solo comando. | `Dockerfile`, `docker-compose.yml` |

## Las tablas que ve el agente

Las mismas cinco, con los mismos nombres y columnas, en los dos motores:

`canonico.clientes` · `canonico.pagos` · `canonico.envios` · `canonico.mensajes_soporte` · `canonico.disputas`

- En **DuckDB** las crea dbt.
- En **Zetaris** las crean las vistas de `zetaris/canonico.sql`, sobre las fuentes `io_pagos`, `io_logistica` e `io_soporte`.

Así, el mismo SQL funciona en los dos. Una diferencia que hay que tener en cuenta: Zetaris devuelve todos los valores como texto (`"42"`) y DuckDB con su tipo (`42`).

## Usar Zetaris

1. Registra las fuentes en Zetaris (NDP File System → `io_pagos`, `io_logistica`, `io_soporte`).
2. Corre `zetaris/canonico.sql` en el SQL Workspace, una sentencia a la vez.
3. Copia `.env.example` como `.env.local` y completa `ZETARIS_URL`, `ZETARIS_API_TOKEN` y `ZETARIS_ORG_ID`. Agrega `IO_MOTOR=zetaris` e `IO_TIMEOUT_S=60`: Zetaris tarda unos 5–6 s con las vistas canónicas, y si se corta una consulta por tiempo, Zetaris la sigue ejecutando y las siguientes quedan en fila. **`.env.local` nunca se sube al repo.**
4. Comprueba que los dos motores dan lo mismo:

```
python scripts/comparar_motores.py
```

## Pruebas

```
python -m pytest
```

## Configuración

| Variable | Por defecto | Para qué |
| --- | --- | --- |
| `IO_MOTOR` | `duckdb` | `zetaris` para usar Zetaris con respaldo en DuckDB |
| `IO_DUCKDB` | `datos/io.duckdb` | ruta de la base |
| `IO_LOG` | `logs/consultar.jsonl` | dónde queda la evidencia |
| `IO_LIMITE_FILAS` | `100` | filas máximas por consulta |
| `IO_TIMEOUT_S` | `10` | segundos máximos por consulta |
| `IO_RUN_ID` | vacío | identifica una corrida en el log |
| `IO_MCP_TRANSPORTE` | `stdio` (`http` en Docker) | cómo se sirve MCP |
| `IO_MCP_HOST` / `IO_MCP_PUERTO` | `127.0.0.1` / `8000` | dónde escucha MCP por HTTP |
| `ZETARIS_URL`, `ZETARIS_API_TOKEN`, `ZETARIS_ORG_ID` | — | solo en `.env.local` |
