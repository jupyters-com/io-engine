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

Tres barreras: se revisa el tipo de sentencia antes de ejecutar, la base se abre en **solo lectura** y el acceso a archivos externos está **desactivado**.

## Qué motor responde

| `IO_MOTOR` | Qué pasa | `motor` | `respaldo` |
| --- | --- | --- | --- |
| `duckdb` (por defecto) | Responde DuckDB | `duckdb` | `false` |
| `zetaris`, Zetaris responde | Responde Zetaris | `zetaris` | `false` |
| `zetaris`, Zetaris no responde | Responde DuckDB | `duckdb` | `true` |

Hoy el adaptador de Zetaris no existe todavía (llega en JPTRS-63), así que `IO_MOTOR=zetaris` cae siempre en la tercera fila. Es el mismo camino que la DoD 3 del Brief: la misma consulta con Zetaris prendido y apagado se distingue comparando `motor` y `respaldo` en el log.

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
| `IO_MOTOR` | `duckdb` (`zetaris` queda previsto para JPTRS-63) |
