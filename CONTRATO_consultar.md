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
  "ms": 4.2
}
```

- Devuelve como máximo `IO_LIMITE_FILAS` filas (100 por defecto). Si había más, `truncado` es `true`.
- Fechas y decimales se devuelven como texto.

## Salida si la consulta se rechaza o falla

```json
{"ok": false, "error": "Solo se permiten consultas de lectura (SELECT). Se recibió: DROP."}
```

Se rechaza, sin tocar la base, cuando:

| Caso | Ejemplo |
| --- | --- |
| No es una lectura | `DROP`, `DELETE`, `INSERT`, `UPDATE`, `CREATE`, `COPY`, `ATTACH` |
| Trae más de una sentencia | `SELECT 1; DROP TABLE pagos` |
| Intenta leer archivos fuera de la base | `SELECT * FROM read_csv('...')` |
| Tarda más del límite | más de `IO_TIMEOUT_S` segundos (10 por defecto) |
| Tiene un error de SQL | tabla o columna que no existe |

Tres barreras: se revisa el tipo de sentencia antes de ejecutar, la base se abre en **solo lectura** y el acceso a archivos externos está **desactivado**.

## Log (`logs/consultar.jsonl`)

Una línea por llamada, aceptada o rechazada:

```json
{"ts": "2026-10-19T14:05:00+00:00", "herramienta": "consultar", "run_id": "demo-1",
 "sql": "SELECT ...", "ok": true, "error": null, "n_filas": 1, "truncado": false,
 "ms": 4.2, "filas": [{"transportista": "RapidEnvio", "disputas": 6}]}
```

`filas` guarda exactamente lo que recibió el agente: es la fila de evidencia que muestra el video.

## Configuración (variables de entorno)

| Variable | Por defecto |
| --- | --- |
| `IO_DUCKDB` | `datos/juguete.duckdb` |
| `IO_LOG` | `logs/consultar.jsonl` |
| `IO_LIMITE_FILAS` | `100` |
| `IO_TIMEOUT_S` | `10` |
| `IO_RUN_ID` | vacío (identifica la corrida en el log) |
