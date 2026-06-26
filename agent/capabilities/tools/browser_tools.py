import subprocess
from urllib.parse import urlencode, urlparse

from agent.executor.results import ToolResult


DEFAULT_TIMEOUT_SECONDS = 5
ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_BROWSER_TARGETS = {
    "auto",
    "web",
    "google",
    "youtube",
    "url",
    "google_home",
    "youtube_home",
}
KNOWN_SITE_URLS = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "you tube": "https://www.youtube.com",
    "github": "https://github.com",
    "openai": "https://openai.com",
    "ollama": "https://ollama.com",
    "canva": "https://www.canva.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "tiktok": "https://www.tiktok.com",
}


def normalize_http_url(url: str) -> str:
    clean = (url or "").strip()
    if not clean:
        raise ValueError("open_url requires a non-empty url")
    if "://" not in clean and "." in clean and not clean.startswith("/"):
        clean = f"https://{clean}"
    parsed = urlparse(clean)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise ValueError("open_url only allows http and https URLs")
    if not parsed.netloc:
        raise ValueError("open_url requires an absolute http or https URL")
    return clean


def open_url(url: str, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> ToolResult:
    try:
        normalized = normalize_http_url(url)
    except ValueError as exc:
        return ToolResult(
            tool_name="open_url",
            success=False,
            error=str(exc),
            metadata={"phase": "real_tool"},
        )

    scheme = urlparse(normalized).scheme.lower()
    command = ["/usr/bin/open", normalized]
    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError:
        return ToolResult(
            tool_name="open_url",
            success=False,
            data={"url": normalized, "scheme": scheme},
            error="/usr/bin/open is not available on this system",
            metadata={"phase": "real_tool", "command": command},
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            tool_name="open_url",
            success=False,
            data={"url": normalized, "scheme": scheme},
            error=f"open_url timed out after {timeout_seconds}s",
            metadata={"phase": "real_tool", "command": command},
        )
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or "").strip()
        return ToolResult(
            tool_name="open_url",
            success=False,
            data={"url": normalized, "scheme": scheme},
            error=message or f"could not open {normalized}",
            metadata={"phase": "real_tool", "command": command},
        )

    return ToolResult(
        tool_name="open_url",
        success=True,
        data={"url": normalized, "scheme": scheme},
        metadata={"phase": "real_tool", "command": command},
    )


def _google_search_url(query: str) -> str:
    return "https://www.google.com/search?" + urlencode({"q": query})


def _youtube_search_url(query: str) -> str:
    return "https://www.youtube.com/results?" + urlencode({"search_query": query})


def _normalize_query_key(query: str) -> str:
    return " ".join((query or "").strip().lower().split())


def _looks_like_direct_url(query: str) -> bool:
    clean = (query or "").strip()
    if not clean or " " in clean:
        return False
    if clean.startswith(("http://", "https://", "www.")):
        return True
    return "." in clean


def _resolve_browser_target(query: str, target: str) -> tuple[str, str]:
    clean_query = (query or "").strip()
    normalized_target = (target or "auto").strip().lower()
    if normalized_target not in ALLOWED_BROWSER_TARGETS:
        raise ValueError(
            "browser_search target must be one of auto, web, google, youtube, url, google_home, youtube_home"
        )
    if normalized_target in {"google_home", "youtube_home"}:
        return normalized_target, (
            "https://www.google.com"
            if normalized_target == "google_home"
            else "https://www.youtube.com"
        )
    if normalized_target == "url":
        return normalized_target, normalize_http_url(clean_query)
    if not clean_query and normalized_target not in {"google_home", "youtube_home"}:
        raise ValueError("browser_search requires a non-empty query")

    query_key = _normalize_query_key(clean_query)
    if normalized_target == "auto":
        if query_key in KNOWN_SITE_URLS:
            return "url", KNOWN_SITE_URLS[query_key]
        if _looks_like_direct_url(clean_query):
            return "url", normalize_http_url(clean_query)
        if "youtube" in query_key:
            return "youtube", _youtube_search_url(clean_query)
        return "web", _google_search_url(clean_query)
    if normalized_target in {"web", "google"}:
        return normalized_target, _google_search_url(clean_query)
    if normalized_target == "youtube":
        return normalized_target, _youtube_search_url(clean_query)
    raise ValueError("browser_search could not resolve a target")


def browser_search(
    query: str, target: str = "auto", *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
) -> ToolResult:
    try:
        resolved_target, url = _resolve_browser_target(query, target)
    except ValueError as exc:
        return ToolResult(
            tool_name="browser_search",
            success=False,
            error=str(exc),
            metadata={"phase": "real_tool", "requested_target": target},
        )

    result = open_url(url, timeout_seconds=timeout_seconds)
    return ToolResult(
        tool_name="browser_search",
        success=result.success,
        data={
            "query": (query or "").strip(),
            "target": resolved_target,
            "url": url,
            "opened": result.success,
        },
        error=result.error,
        metadata={
            "phase": "real_tool",
            "requested_target": target,
            "used_helper": "open_url",
        },
    )
