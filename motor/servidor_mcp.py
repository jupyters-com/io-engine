"""Servidor MCP del motor de IO, con una sola herramienta: consultar(sql).

Se ejecuta así (lo lanza el agente, o el script de prueba):
    python -m motor.servidor_mcp
"""

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
        "sentencias y lectura de archivos. Cada llamada queda registrada como evidencia."
    )
)
def consultar(sql: str) -> dict:
    return nucleo.consultar(sql)


if __name__ == "__main__":
    servidor.run("stdio")
