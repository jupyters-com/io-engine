# Datos SINTÉTICOS de contracargos

**Todo lo que hay en esta carpeta es inventado.** Lo genera `motor/generador.py` con la semilla `2026`
(JPTRS-61), siguiendo el plan de datos de JPTRS-54. No contiene datos personales: los correos usan el
dominio reservado `ejemplo.test`, no hay nombres ni direcciones, y de las tarjetas solo hay los últimos
4 dígitos de tarjetas de prueba de Stripe.

| Archivo | Imita a | Contenido |
| --- | --- | --- |
| `pagos.json` | Stripe | 300 clientes, 800 cargos, 42 disputas (fechas en unix, montos en centavos) |
| `envios.csv` | Operador logístico | 800 envíos (fechas dd/mm/aaaa, pedido sin prefijo) |
| `soporte.json` | Sistema de tickets | 150 tickets (pedido con `#`, correo con mayúsculas variables) |
| `casos_plantados.json` | — | Hoja de respuestas de los tres casos. **No se carga en la base.** |

Período: 1-jul-2026 a 30-sep-2026. Para regenerar y cargar en DuckDB:

```
python scripts/generar_y_cargar.py
```
