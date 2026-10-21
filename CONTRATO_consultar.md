# Contrato · `consultar(sql)`

La única puerta del agente a los datos del motor. Solo lee, y cada llamada deja una línea en el log.

## Entrada

| Campo | Tipo | Reglas |
| --- | --- | --- |
| `sql` | texto | **Una sola** sentencia de lectura (`SELECT` o `WITH … SELECT`). Puede terminar en `;`. |

## Salida si la consulta es válida

```json
{
  "ok": true,
  "columnas": ["transportista", "disputas"],
  "filas": [{"transportista": "RapidEnvio", "disputas": 6}],
  "n_filas": 1,
  "truncado": false,
  "motor": "duckdb",
  "respaldo": false,
  "ms": 4.2
}
```

- Devuelve como máximo `IO_LIMITE_FILAS` filas (100 por defecto). Si había más, `truncado` es `true`.
- Fechas y decimales se devuelven como texto.
- `motor` dice quién respondió: `"zetaris"` o `"duckdb"`.
- `respaldo` es `true` cuando se pidió Zetaris, no pudo responder y respondió DuckDB. En ese caso se agrega `motivo_respaldo` con la causa.

## Salida si la consulta se rechaza o falla

```json
{"ok": false, "error": "Solo se permiten consultas de lectura (SELECT). Se recibió: DROP.",
 "motor": null, "respaldo": false, "ms": 0.4}
```

`motor` es `null` si la consulta se rechazó antes de llegar a un motor. Si falló dentro de un motor (error de SQL, tiempo), dice cuál era.

Se rechaza, sin tocar la base, cuando:

| Caso | Ejemplo |
| --- | --- |
| No es una lectura | `DROP`, `DELETE`, `INSERT`, `UPDATE`, `CREATE`, `COPY`, `ATTACH` |
| Trae más de una sentencia | `SELECT 1; DROP TABLE pagos` |
| Intenta leer archivos fuera de la base | `SELECT * FROM read_csv('...')` |
| Tarda más del límite | más de `IO_TIMEOUT_S` segundos (10 por defecto) |
| Tiene un error de SQL | tabla o columna que no existe |

### Barreras según el motor

| Barrera | DuckDB | Zetaris |
| --- | --- | --- |
| 1. Una sola sentencia `SELECT` (se revisa antes de ejecutar) | ✔ | ✔ |
| 2. Base abierta en solo lectura | ✔ | ✘ depende de los permisos del token |
| 3. Sin acceso a archivos externos | ✔ | ✘ depende de los permisos del token |

Con Zetaris solo rige la barrera 1 desde nuestro código. Por eso el `ZETARIS_API_TOKEN` debe ser de un usuario con un rol de **solo lectura** sobre las fuentes de IO (Management → Roles en Zetaris). Mientras usemos el usuario administrador, la barrera 1 es la única protección.

## Qué motor responde

| `IO_MOTOR` | Qué pasa | `motor` | `respaldo` |
| --- | --- | --- | --- |
| `duckdb` (por defecto) | Responde DuckDB | `duckdb` | `false` |
| `zetaris`, Zetaris responde | Responde Zetaris | `zetaris` | `false` |
| `zetaris`, Zetaris no responde | Responde DuckDB | `duckdb` | `true` |

Zetaris "no responde" cuando faltan credenciales, no hay conexión, el token es rechazado (401/403), la ruta no existe (404) o el servidor falla (5xx). Si Zetaris **sí** responde pero rechaza el SQL (400/422), no hay respaldo: se devuelve el error con `motor: zetaris`.

Es el mismo camino que la DoD 3 del Brief: la misma consulta con Zetaris prendido y apagado se distingue comparando `motor` y `respaldo` en el log.

### Adaptador de Zetaris

Usa la misma ruta que el SQL Workspace de Zetaris: `POST {ZETARIS_URL}/api/proxy/sql-editor/sqls/run-stream`, con `Authorization: Bearer <ZETARIS_API_TOKEN>`, `X-Request-ID` y `X-Org-ID`. La respuesta es una línea JSON con las columnas y una por fila. **Zetaris devuelve todos los valores como texto** (`"42"`), DuckDB con su tipo (`42`).

## Log (`logs/consultar.jsonl`)

Una línea por llamada, aceptada o rechazada:

```json
{"ts": "2026-10-19T14:05:00+00:00", "herramienta": "consultar", "run_id": "demo-1",
 "sql": "SELECT ...", "motor": "duckdb", "respaldo": false, "motivo_respaldo": null, "ok": true, "error": null, "n_filas": 1, "truncado": false,
 "ms": 4.2, "filas": [{"transportista": "RapidEnvio", "disputas": 6}]}
```

`filas` guarda exactamente lo que recibió el agente: es la fila de evidencia que muestra el video. `motor` y `respaldo` muestran en pantalla quién respondió.

## Configuración (variables de entorno)

| Variable | Por defecto |
| --- | --- |
| `IO_DUCKDB` | `datos/juguete.duckdb` |
| `IO_LOG` | `logs/consultar.jsonl` |
| `IO_LIMITE_FILAS` | `100` |
| `IO_TIMEOUT_S` | `10` |
| `IO_RUN_ID` | vacío (identifica la corrida en el log) |
| `IO_MOTOR` | `duckdb` (o `zetaris`) |
| `ZETARIS_URL`, `ZETARIS_API_TOKEN`, `ZETARIS_ORG_ID` | en `.env.local` (ver `.env.example`); nunca en el repo |
| `ZETARIS_RUTA_SQL` | `/api/proxy/sql-editor/sqls/run-stream` |
