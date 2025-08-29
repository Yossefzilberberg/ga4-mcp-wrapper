import anyio
from mcp.server import Server
from mcp.server.stdio import stdio_server

srv = Server("smoke-test")

@srv.tool()
def search(q: str = ""):
    # מספיק ל-handshake של ChatGPT
    return [{"id": "demo", "title": "OK", "url": "demo", "snippet": "ready"}]

@srv.tool()
def fetch(id: str):
    return {"id": id, "ok": True}

async def main() -> None:
    async with stdio_server(srv).run():
        await anyio.sleep_forever()

if __name__ == "__main__":
    anyio.run(main)
