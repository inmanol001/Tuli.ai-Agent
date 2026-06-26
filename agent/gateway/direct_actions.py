from __future__ import annotations

import re
from typing import Any

from agent.capabilities.tools.browser_tools import KNOWN_SITE_URLS, normalize_http_url
from agent.capabilities.tools.schemas import ToolCall


DIRECT_BROWSER_OPEN_RE = re.compile(
    r"\b("
    r"abre|abrir|open|"
    r"ll[eé]vame|llevame|"
    r"entra|entrar|"
    r"visita|visitar|visit|"
    r"navega|navegar|"
    r"quiero\s+ver|mu[eé]strame|muestrame|muestra|mostrar|"
    r"ve"
    r")\b|"
    r"\bir\s+a\b|\bir\s+al\b|\bir\s+a\s+la\b",
    re.I,
)
ABSOLUTE_URL_RE = re.compile(r"https?://[^\s)>,]+", re.I)
BARE_DOMAIN_RE = re.compile(
    r"\b(?:[a-z0-9-]+\.)+(?:[a-z]{2,})(?:/[^\s)>,]*)?\b",
    re.I,
)


def _normalized_text(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _selected_tool_names(selected_tools: list[dict[str, Any]] | None) -> set[str]:
    names: set[str] = set()
    for tool in selected_tools or []:
        if isinstance(tool, dict):
            name = tool.get("name")
        else:
            name = getattr(tool, "name", None)
        if isinstance(name, str) and name:
            names.add(name)
    return names


def resolve_direct_browser_destination(user_text: str) -> tuple[str, str] | None:
    """
    Resolve simple, low-risk browser-open requests without an LLM.

    Returns (query, target), where target is compatible with browser_search.
    This intentionally handles semantic variants like "llévame a GitHub" so
    they do not fall into the generic clarification flow.
    """
    text = user_text or ""
    normalized = _normalized_text(text)
    if not normalized:
        return None

    has_open_intent = DIRECT_BROWSER_OPEN_RE.search(normalized) is not None
    absolute_url = ABSOLUTE_URL_RE.search(text)
    if absolute_url is not None:
        return normalize_http_url(absolute_url.group(0)), "url"

    if not has_open_intent:
        return None

    domain_match = BARE_DOMAIN_RE.search(text)
    if domain_match:
        domain = domain_match.group(0).strip().lower().rstrip(".,)")
        if domain.startswith("www."):
            domain = domain[4:]
        return domain, "auto"

    for site_name in KNOWN_SITE_URLS:
        if site_name in normalized:
            return site_name, "auto"

    return None


def direct_browser_search_call(
    user_text: str,
    selected_tools: list[dict[str, Any]] | None = None,
) -> tuple[ToolCall, str] | None:
    if selected_tools is not None and "browser_search" not in _selected_tool_names(selected_tools):
        return None

    resolved = resolve_direct_browser_destination(user_text)
    if resolved is None:
        return None

    query, target = resolved
    reason = "direct_browser_url" if target == "url" else "direct_browser_known_destination"
    return (
        ToolCall(
            tool_name="browser_search",
            arguments={"query": query, "target": target},
            risk_level="low",
            requires_confirmation=False,
        ),
        reason,
    )
