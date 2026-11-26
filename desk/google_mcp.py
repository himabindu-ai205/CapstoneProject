import asyncio
import os
from pathlib import Path

_ALLOWED = {"append_to_google_doc", "create_email_draft"}


def mcp_script() -> Path | None:
    configured = os.environ.get("GOOGLE_MCP_DIR", "").strip()
    root = Path(configured) if configured else Path(__file__).resolve().parents[2] / "MCP Server"
    script = root / "dist" / "index.js"
    return script if script.is_file() else None


def mcp_call(name: str, arguments: dict) -> dict:
    if name not in _ALLOWED:
        raise RuntimeError("The pulse only appends a doc or creates an email draft.")
    script = mcp_script()
    if script is None:
        raise RuntimeError("Google MCP server is not built.")
    return asyncio.run(_call(script, name, arguments))


async def _call(script: Path, name: str, arguments: dict) -> dict:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    params = StdioServerParameters(command="node", args=[str(script)], cwd=str(script.parent.parent))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)
    if result.isError:
        text = " ".join(getattr(block, "text", "") for block in result.content)
        raise RuntimeError(text or "Google rejected the write.")
    return {"ok": True}
