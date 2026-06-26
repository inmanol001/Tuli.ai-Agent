from __future__ import annotations

from typing import Any

from agent.executor.results import ToolResult


def web_search(
    query: str,
    max_results: int = 5,
    *,
    region: str = "us-en",
    safesearch: str = "moderate",
    timelimit: str | None = None,
) -> ToolResult:
    """Search the web and return structured results to the agent.

    This does NOT open the browser. It returns title/url/snippet results.
    """

    clean_query = (query or "").strip()
    if not clean_query:
        return ToolResult(
            tool_name="web_search",
            success=False,
            error="web_search requires a non-empty query",
            metadata={"phase": "real_tool", "provider": "ddgs"},
        )

    try:
        max_results_int = int(max_results)
    except Exception:
        max_results_int = 5

    max_results_int = max(1, min(max_results_int, 10))

    try:
        from ddgs import DDGS
    except Exception as exc:
        return ToolResult(
            tool_name="web_search",
            success=False,
            error=f"ddgs is not installed or could not be imported: {exc}",
            metadata={"phase": "real_tool", "provider": "ddgs"},
        )

    try:
        with DDGS() as ddgs:
            raw_results = list(
                ddgs.text(
                    clean_query,
                    region=region,
                    safesearch=safesearch,
                    timelimit=timelimit,
                    max_results=max_results_int,
                )
            )
    except Exception as exc:
        return ToolResult(
            tool_name="web_search",
            success=False,
            error=f"web_search failed: {exc}",
            data={"query": clean_query},
            metadata={"phase": "real_tool", "provider": "ddgs"},
        )

    results: list[dict[str, Any]] = []
    for item in raw_results:
        title = (item.get("title") or "").strip()
        url = (item.get("href") or item.get("url") or "").strip()
        snippet = (item.get("body") or item.get("snippet") or "").strip()

        if not title and not url and not snippet:
            continue

        results.append(
            {
                "title": title,
                "url": url,
                "snippet": snippet,
            }
        )

    return ToolResult(
        tool_name="web_search",
        success=True,
        data={
            "query": clean_query,
            "results": results,
            "count": len(results),
            "provider": "ddgs",
        },
        metadata={
            "phase": "real_tool",
            "provider": "ddgs",
            "max_results": max_results_int,
            "region": region,
            "safesearch": safesearch,
            "timelimit": timelimit,
        },
    )
