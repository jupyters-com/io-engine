-- Un envío por pedido, con las definiciones de entrega escritas una sola vez.
with base as (
    select
        *,
        estado = 'entregado' and prueba_entrega in ('firma', 'foto')        as entrega_confirmada,
        estado = 'extraviado'                                                as extraviado,
        case when entregado_en is not null then entregado_en > prometido_en
             else date '{{ var("fecha_corte") }}' > prometido_en + {{ var("dias_gracia_entrega") }}
        end                                                                  as entrega_tarde,
        greatest(0, datediff('day', prometido_en,
                 coalesce(entregado_en, date '{{ var("fecha_corte") }}')))   as dias_atraso
    from {{ ref('map_envios') }}
),
zona as (
    -- Para cada envío: qué tan tarde entrega su transportista en su región en esas fechas
    select a.envio_id,
           count(*)                    as envios_zona,
           avg(b.entrega_tarde::int)   as tasa_tarde_zona
    from base a
    join base b
      on  b.transportista = a.transportista
      and b.region = a.region
      and b.prometido_en between a.prometido_en - {{ var("ventana_zona_dias") }}
                             and a.prometido_en + {{ var("ventana_zona_dias") }}
    group by a.envio_id
)
select
    base.*,
    zona.envios_zona,
    round(zona.tasa_tarde_zona, 3)                                     as tasa_tarde_zona,
    zona.tasa_tarde_zona >= {{ var("umbral_zona_atrasos") }}           as zona_con_atrasos
from base
join zona using (envio_id)
