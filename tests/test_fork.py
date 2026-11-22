"""Guards for the hardened fork."""

from __future__ import annotations

import asyncio

from zepp_mcp import server


def _tool_names() -> set[str]:
    return {t.name for t in asyncio.run(server.server.list_tools())}


def test_raw_request_tool_is_not_exposed():
    names = _tool_names()
    assert "zepp_raw_request" not in names
    assert len(names) == 13
