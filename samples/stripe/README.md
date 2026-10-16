# Muestras de disputas de Stripe

Datos sintéticos, generados en el modo prueba de Stripe (`livemode: false`) para JPTRS-53.
No contienen claves ni datos reales.

| Archivo | Motivo | Evidencia enviada | Resultado |
| -- | -- | -- | -- |
| `disputa_ganada.json` | `fraudulent` | `winning_evidence` | `won` |
| `disputa_perdida.json` | `product_not_received` | `losing_evidence` | `lost` |

Cada archivo incluye el PaymentIntent, la disputa final y sus eventos (`charge.dispute.*`).
Se usan como referencia de campos y tiempos para el plan de datos sintéticos (JPTRS-54).