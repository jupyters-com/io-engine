"""Servidor MCP del motor de IO, con una sola herramienta: consultar(sql).

Dos formas de servirlo:
    python -m motor.servidor_mcp            # stdio: lo lanza el agente como proceso hijo
    IO_MCP_TRANSPORTE=http python -m motor.servidor_mcp
                                            # HTTP en http://<host>:8000/mcp (así corre en Docker)
"""

import os

from mcp.server.mcpserver import MCPServer

from motor import consultar as nucleo

servidor = MCPServer(
    "io-engine",
    instructions=(
        "Motor de datos de IO. La única forma de leer datos es la herramienta "
        "consultar(sql): una sola sentencia SELECT por llamada, solo lectura."
    ),
)


@servidor.tool(
    description=(
        "Ejecuta UNA consulta SQL de solo lectura (SELECT) sobre el esquema de IO en DuckDB "
        "y devuelve las filas (máximo 100). Rechaza DROP, INSERT, UPDATE, DELETE, varias "
        "sentencias y lectura de archivos. Cada llamada queda registrada como evidencia, "
        "incluido qué motor respondió (Zetaris o DuckDB)."
    )
)
def consultar(sql: str) -> dict:
    return nucleo.consultar(sql)


def servir():
    if os.getenv("IO_MCP_TRANSPORTE", "stdio").lower() in ("http", "streamable-http"):
        servidor.run("streamable-http",
                     host=os.getenv("IO_MCP_HOST", "127.0.0.1"),
                     port=int(os.getenv("IO_MCP_PUERTO", "8000")))
    else:
        servidor.run("stdio")


if __name__ == "__main__":
    servir()
