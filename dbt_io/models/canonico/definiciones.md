{% docs entrega_confirmada %}
**Entrega confirmada:** el envío figura como entregado **y** tiene prueba de entrega (firma o foto).
{% enddocs %}

{% docs entrega_tarde %}
**Entrega tarde:** se entregó después de la fecha prometida, o sigue sin entregarse más de
`dias_gracia_entrega` días (3) después de la fecha prometida, a la fecha de corte de los datos.
{% enddocs %}

{% docs zona_con_atrasos %}
**Zona con atrasos:** en una ventana de ±`ventana_zona_dias` días (7) alrededor de la fecha prometida,
el mismo transportista en la misma región entregó tarde al menos el `umbral_zona_atrasos` (50 %) de sus envíos.
{% enddocs %}

{% docs reclamo_previo %}
**Reclamo previo:** existe un mensaje de soporte del mismo cliente, sobre el mismo pedido,
creado **antes** de que se abriera la disputa.
{% enddocs %}

{% docs senales_fraude %}
**Señales de fraude** (cada una suma 1): cliente sin pedidos previos · nivel de riesgo `highest` ·
país de la IP distinto del país de facturación · envío a punto de retiro. **Dos o más = sospecha de fraude.**
{% enddocs %}

{% docs vale_pelear %}
**Disputa que vale la pena pelear:** entrega confirmada **y** sin reclamo previo **y** menos de dos señales de fraude.
En cualquier otro caso no conviene pelearla. Son reglas de IO para el demo, no reglas de las redes de tarjetas.
{% enddocs %}

{% docs causa_operativa %}
**Causa operativa:** la disputa tiene una entrega tarde o extraviada **y** su transportista y región
están en una zona con atrasos en ese período.
{% enddocs %}
