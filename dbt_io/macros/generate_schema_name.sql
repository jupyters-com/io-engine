{# Usa el nombre de esquema tal cual (origen, mapeo, canonico) en vez de "main_origen". #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name | trim if custom_schema_name else target.schema }}
{%- endmacro %}
