"""Comprueba desde afuera que el motor está sirviendo: llama a consultar(sql) por MCP sobre HTTP.

    python scripts/probar_mcp_http.py                       # http://localhost:8000/mcp
    python scripts/probar_mcp_http.py http://otra-maquina:8000/mcp

Es lo que haría el agente. La llamada queda también en logs/consultar.jsonl.
"""

import asyncio
import json
import sys

from mcp.client.client import Client

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/mcp"
SQL = "SELECT decision, razon_decision, count(*) AS n FROM canonico.disputas " \
      "GROUP BY decision, razon_decision ORDER BY n DESC, razon_decision"


async def main():
    async with Client(URL) as agente:
        herramientas = [h.name for h in (await agente.list_tools()).tools]
        print("Servidor:", URL, "· herramientas:", herramientas)
        r = await agente.call_tool("consultar", {"sql": SQL})
        datos = r.structured_content or json.loads(r.content[0].text)
        datos = datos.get("result", datos)
        print(f"motor={datos['motor']} respaldo={datos['respaldo']} ok={datos['ok']} {datos['ms']} ms")
        for f in datos.get("filas", []):
            print("  " + " · ".join(str(v) for v in f.values()))
        if not datos["ok"]:
            print("Error:", datos["error"])


asyncio.run(main())
