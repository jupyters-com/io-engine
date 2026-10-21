# Motor de IO en un contenedor: genera los datos, los carga (dlt), corre dbt y sirve consultar(sql) por MCP.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    IO_DUCKDB=/app/datos/io.duckdb \
    IO_LOG=/app/logs/consultar.jsonl \
    IO_MCP_TRANSPORTE=http \
    IO_MCP_HOST=0.0.0.0 \
    IO_MCP_PUERTO=8000

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000
CMD ["python", "scripts/arrancar.py"]
