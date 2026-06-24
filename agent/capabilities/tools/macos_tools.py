import subprocess

from agent.executor.results import ToolResult


DEFAULT_TIMEOUT_SECONDS = 5

APP_ALIASES = {
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "safari": "Safari",
    "terminal": "Terminal",
    "finder": "Finder",
    "notes": "Notes",
    "notas": "Notes",
    "vscode": "Visual Studio Code",
    "vs code": "Visual Studio Code",
    "code": "Visual Studio Code",
}


def normalize_app_name(app_name: str) -> str:
    clean = (app_name or "").strip().strip("\"'")
    clean = clean.removesuffix(".app").strip()
    return APP_ALIASES.get(clean.lower(), clean)


def open_app(app_name: str, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> ToolResult:
    normalized = normalize_app_name(app_name)
    command = ["/usr/bin/open", "-a", normalized]
    if not normalized:
        return ToolResult(
            tool_name="open_app",
            success=False,
            error="open_app requires a non-empty app_name",
            metadata={"phase": "real_tool"},
        )

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
            tool_name="open_app",
            success=False,
            data={"app_name": normalized},
            error="/usr/bin/open is not available on this system",
            metadata={"phase": "real_tool", "command": command},
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            tool_name="open_app",
            success=False,
            data={"app_name": normalized},
            error=f"open_app timed out after {timeout_seconds}s",
            metadata={"phase": "real_tool", "command": command},
        )
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or "").strip()
        return ToolResult(
            tool_name="open_app",
            success=False,
            data={"app_name": normalized},
            error=message or f"could not open {normalized}",
            metadata={"phase": "real_tool", "command": command},
        )

    return ToolResult(
        tool_name="open_app",
        success=True,
        data={"app_name": normalized},
        metadata={"phase": "real_tool", "command": command},
    )
