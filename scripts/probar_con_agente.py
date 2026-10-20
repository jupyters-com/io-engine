"""Hace de "agente": se conecta al servidor MCP, pide un dato y luego intenta un DROP.

Es el criterio de aceptación de JPTRS-52. Al terminar, mira logs/consultar.jsonl.
    python scripts/probar_con_agente.py
"""

import asyncio
import json
import os
import sys

from mcp.client.client import Client
from mcp.client.stdio import StdioServerParameters

SERVIDOR = StdioServerParameters(
    command=sys.executable,
    args=["-m", "motor.servidor_mcp"],
    env={**os.environ, "IO_RUN_ID": os.getenv("IO_RUN_ID", "prueba-jptrs-52")},
)

PEDIR_DATO = """
SELECT e.transportista, e.region, count(*) AS disputas
FROM disputas d JOIN envios e USING (pedido_id)
GROUP BY 1, 2 ORDER BY disputas DESC
"""
INTENTO_PELIGROSO = "DROP TABLE disputas"


def mostrar(titulo, resultado):
    print(f"\n=== {titulo} ===")
    datos = resultado.structured_content or json.loads(resultado.content[0].text)
    print(json.dumps(datos, indent=2, ensure_ascii=False))


async def main():
    async with Client(SERVIDOR) as agente:
        herramientas = await agente.list_tools()
        print("Herramientas disponibles:", [h.name for h in herramientas.tools])

        mostrar("1. El agente pide un dato", await agente.call_tool("consultar", {"sql": PEDIR_DATO}))
        mostrar("2. El agente intenta un DROP", await agente.call_tool("consultar", {"sql": INTENTO_PELIGROSO}))


if __name__ == "__main__":
    asyncio.run(main())
