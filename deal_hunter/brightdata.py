from __future__ import annotations

import json
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from deal_hunter.cache import JsonFileCache


TRAVEL_KEYWORDS = (
    "flight",
    "hotel",
    "booking",
    "travel",
    "ticket",
    "stubhub",
    "viagogo",
    "seatgeek",
    "vivid",
    "kayak",
    "skyscanner",
    "google",
)


@dataclass(slots=True)
class McpTool:
    name: str
    description: str
    input_schema: dict[str, Any]


class BrightDataMCPClient:
    def __init__(
        self,
        *,
        api_token: str | None = None,
        pro_mode: bool = True,
        rate_limit: str = "100/1h",
        cache: JsonFileCache | None = None,
    ) -> None:
        self.api_token = api_token or os.getenv("BRIGHTDATA_API_TOKEN")
        self.pro_mode = pro_mode
        self.rate_limit = rate_limit
        self.cache = cache
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def __aenter__(self) -> "BrightDataMCPClient":
        if not self.api_token:
            raise RuntimeError(
                "BRIGHTDATA_API_TOKEN is required for live mode. Use --offline-demo to run without APIs."
            )
        params = StdioServerParameters(
            command="npx",
            args=["@brightdata/mcp"],
            env={
                "API_TOKEN": self.api_token,
                "PRO_MODE": "true" if self.pro_mode else "false",
                "RATE_LIMIT": self.rate_limit,
            },
        )
        self._stack = AsyncExitStack()
        read_stream, write_stream = await self._stack.enter_async_context(
            stdio_client(params)
        )
        self._session = await self._stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self._session.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._session = None

    async def list_tools(self) -> list[McpTool]:
        if self._session is None:
            raise RuntimeError("Bright Data MCP session is not active.")
        response = await self._session.list_tools()
        tools = getattr(response, "tools", response)
        normalized: list[McpTool] = []
        for tool in tools:
            normalized.append(
                McpTool(
                    name=getattr(tool, "name"),
                    description=getattr(tool, "description", "") or "",
                    input_schema=getattr(tool, "inputSchema", {}) or {},
                )
            )
        return normalized

    async def list_travel_tools(self) -> list[McpTool]:
        selected: list[McpTool] = []
        for tool in await self.list_tools():
            descriptor = f"{tool.name} {tool.description}".lower()
            if tool.name in {"search_engine", "scrape_as_markdown", "extract"}:
                selected.append(tool)
                continue
            if tool.name.startswith("scraping_browser_"):
                selected.append(tool)
                continue
            if tool.name.startswith("web_data_") and any(
                keyword in descriptor for keyword in TRAVEL_KEYWORDS
            ):
                selected.append(tool)
        return selected

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if self._session is None:
            raise RuntimeError("Bright Data MCP session is not active.")
        cache_key = {"tool": name, "arguments": arguments}
        if self.cache is not None:
            cached = self.cache.get("brightdata", cache_key)
            if cached is not None:
                return cached

        result = await self._session.call_tool(name, arguments=arguments)
        normalized = normalize_mcp_result(result)
        if self.cache is not None:
            self.cache.set("brightdata", cache_key, normalized)
        return normalized


def normalize_mcp_result(result: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "is_error": bool(getattr(result, "isError", False)),
        "content": [],
    }
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        payload["structured_content"] = serialize_any(structured)

    text_chunks: list[str] = []
    for block in getattr(result, "content", []) or []:
        block_type = getattr(block, "type", None) or (
            block.get("type") if isinstance(block, dict) else "unknown"
        )
        if block_type == "text":
            text = getattr(block, "text", None)
            if text is None and isinstance(block, dict):
                text = block.get("text")
            if text:
                text_chunks.append(text)
                payload["content"].append({"type": "text", "text": text[:12000]})
        else:
            payload["content"].append(serialize_any(block))

    if text_chunks:
        joined = "\n\n".join(text_chunks)
        payload["text"] = joined[:20000]

    return payload


def serialize_any(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [serialize_any(item) for item in value]
    if isinstance(value, dict):
        return {str(key): serialize_any(item) for key, item in value.items()}
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return serialize_any(model_dump(mode="json"))
    dict_method = getattr(value, "dict", None)
    if callable(dict_method):
        return serialize_any(dict_method())
    if hasattr(value, "__dict__"):
        return serialize_any(vars(value))
    return json.loads(json.dumps(str(value)))
