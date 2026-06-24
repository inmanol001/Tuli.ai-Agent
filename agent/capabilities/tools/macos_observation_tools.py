from __future__ import annotations

import ctypes
import subprocess
from pathlib import Path
from typing import Any, Mapping

from agent.capabilities.tools.macos_tools import APP_ALIASES
from agent.executor.results import ToolResult


DEFAULT_TIMEOUT_SECONDS = 5
DEFAULT_MAX_WINDOWS = 20

try:
    import AppKit  # type: ignore
    import Quartz  # type: ignore
except Exception:  # pragma: no cover - platform dependent
    AppKit = None
    Quartz = None


KNOWN_APPLICATIONS = sorted(
    {
        *APP_ALIASES.values(),
        "App Store",
        "Calculator",
        "Calendar",
        "Chess",
        "Contacts",
        "Dictionary",
        "FaceTime",
        "Mail",
        "Maps",
        "Messages",
        "Music",
        "Photos",
        "Podcasts",
        "Preview",
        "QuickTime Player",
        "Reminders",
        "Safari",
        "Shortcuts",
        "System Settings",
        "TextEdit",
        "TV",
        "Voice Memos",
    }
)


def clean_text(value: object, *, limit: int = 180) -> str:
    return " ".join(str(value).split())[:limit]


def _run_osascript(
    script: str, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
) -> str:
    result = subprocess.run(
        ["/usr/bin/osascript", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    return (result.stdout or "").strip()


def _permission_error(exc: BaseException) -> str:
    if isinstance(exc, FileNotFoundError):
        return "osascript is not available on this system"
    if isinstance(exc, subprocess.TimeoutExpired):
        return "osascript timed out"
    if isinstance(exc, subprocess.CalledProcessError):
        return (exc.stderr or exc.stdout or "permission check failed").strip()
    return str(exc)


def _check_accessibility() -> bool | str:
    try:
        framework = ctypes.CDLL(
            "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
        )
        func = framework.AXIsProcessTrusted
        func.restype = ctypes.c_bool
        func.argtypes = []
        return bool(func())
    except Exception:
        return "unknown"


def _check_screen_recording() -> bool | str:
    try:
        framework = ctypes.CDLL(
            "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
        )
        func = framework.CGPreflightScreenCaptureAccess
        func.restype = ctypes.c_bool
        func.argtypes = []
        return bool(func())
    except Exception:
        return "unknown"


def _check_automation(*, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> bool | str:
    script = r'''
tell application "System Events"
    return name of first process
end tell
'''
    try:
        return bool(_run_osascript(script, timeout_seconds=timeout_seconds))
    except FileNotFoundError:
        return "unknown"
    except subprocess.TimeoutExpired:
        return "unknown"
    except subprocess.CalledProcessError:
        return False
    except Exception:
        return "unknown"


def macos_permissions_check(
    *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
) -> ToolResult:
    data = {
        "accessibility": _check_accessibility(),
        "screen_recording": _check_screen_recording(),
        "automation": _check_automation(timeout_seconds=timeout_seconds),
    }
    return ToolResult(
        tool_name="macos_permissions_check",
        success=True,
        data=data,
        metadata={"phase": "real_tool"},
    )


def _parse_frontmost(raw: str) -> dict[str, Any]:
    parts = raw.split("||")
    pid = None
    if len(parts) > 3 and parts[3].strip():
        try:
            pid = int(parts[3].strip())
        except ValueError:
            pid = None
    return {
        "app_name": clean_text(parts[0]) if len(parts) > 0 and parts[0].strip() else None,
        "bundle_id": clean_text(parts[1]) if len(parts) > 1 and parts[1].strip() else None,
        "window_title": clean_text(parts[2]) if len(parts) > 2 and parts[2].strip() else None,
        "pid": pid,
    }


def macos_observe_frontmost(
    *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
) -> ToolResult:
    script = r'''
tell application "System Events"
    set frontApp to first application process whose frontmost is true
    set appName to name of frontApp
    set bundleId to bundle identifier of frontApp
    set windowName to ""
    set appPid to ""
    try
        set windowName to name of front window of frontApp
    end try
    try
        set appPid to unix id of frontApp
    end try
    return appName & "||" & bundleId & "||" & windowName & "||" & appPid
end tell
'''
    try:
        raw = _run_osascript(script, timeout_seconds=timeout_seconds)
        return ToolResult(
            tool_name="macos_observe_frontmost",
            success=True,
            data=_parse_frontmost(raw),
            metadata={"phase": "real_tool", "source": "system_events"},
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
        return ToolResult(
            tool_name="macos_observe_frontmost",
            success=False,
            error=_permission_error(exc),
            metadata={"phase": "real_tool", "source": "system_events"},
        )
    except Exception as exc:
        return ToolResult(
            tool_name="macos_observe_frontmost",
            success=False,
            error=str(exc),
            metadata={"phase": "real_tool", "source": "system_events"},
        )


def _parse_bounds(raw: Mapping[str, Any]) -> dict[str, int] | None:
    try:
        return {
            "x": int(round(float(raw["X"]))),
            "y": int(round(float(raw["Y"]))),
            "width": int(round(float(raw["Width"]))),
            "height": int(round(float(raw["Height"]))),
        }
    except (KeyError, TypeError, ValueError):
        return None


def _parse_quartz_windows(raw_windows: Any) -> list[dict[str, Any]]:
    if not raw_windows or Quartz is None:
        return []
    try:
        workspace = AppKit.NSWorkspace.sharedWorkspace() if AppKit is not None else None
        front_app = workspace.frontmostApplication() if workspace is not None else None
        front_pid = int(front_app.processIdentifier()) if front_app is not None else -1
    except Exception:
        front_pid = -1

    windows: list[dict[str, Any]] = []
    for item in raw_windows:
        if not isinstance(item, dict):
            continue
        bounds_raw = item.get(Quartz.kCGWindowBounds)
        if not isinstance(bounds_raw, dict):
            continue
        bounds = _parse_bounds(bounds_raw)
        if not bounds or bounds["width"] <= 0 or bounds["height"] <= 0:
            continue
        app_name = clean_text(item.get(Quartz.kCGWindowOwnerName) or "")
        if not app_name:
            continue
        title_raw = item.get(Quartz.kCGWindowName)
        owner_pid_raw = item.get(Quartz.kCGWindowOwnerPID)
        owner_pid = int(owner_pid_raw) if isinstance(owner_pid_raw, int) else None
        windows.append(
            {
                "app_name": app_name,
                "title": clean_text(title_raw) if isinstance(title_raw, str) and title_raw.strip() else None,
                "bounds": bounds,
                "window_id": item.get(Quartz.kCGWindowNumber)
                if isinstance(item.get(Quartz.kCGWindowNumber), int)
                else None,
                "layer": item.get(Quartz.kCGWindowLayer)
                if isinstance(item.get(Quartz.kCGWindowLayer), int)
                else None,
                "onscreen": item.get("kCGWindowIsOnscreen", True),
                "pid": owner_pid,
                "is_frontmost": owner_pid == front_pid,
                "source": "quartz",
            }
        )
    return windows


def _parse_system_events_windows(output: str) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    for line in output.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        parts = cleaned.split("||")
        if len(parts) < 7:
            continue
        try:
            bounds = {
                "x": int(float(parts[2].strip())),
                "y": int(float(parts[3].strip())),
                "width": int(float(parts[4].strip())),
                "height": int(float(parts[5].strip())),
            }
        except ValueError:
            continue
        app_name = clean_text(parts[0])
        if not app_name or bounds["width"] <= 0 or bounds["height"] <= 0:
            continue
        windows.append(
            {
                "app_name": app_name,
                "title": clean_text(parts[1]) if parts[1].strip() else None,
                "bounds": bounds,
                "window_id": None,
                "layer": None,
                "onscreen": True,
                "is_frontmost": parts[6].strip().lower() in {"true", "1", "yes"},
                "source": "system_events",
            }
        )
    return windows


def _quartz_windows() -> list[dict[str, Any]]:
    if Quartz is None:
        return []
    try:
        raw_windows = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly
            | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID,
        )
        return _parse_quartz_windows(raw_windows)
    except Exception:
        return []


def _system_events_windows(
    *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
) -> list[dict[str, Any]]:
    script = r'''
tell application "System Events"
    set output to {}
    repeat with p in application processes
        try
            if visible of p is true then
                set processName to name of p
                set frontState to frontmost of p
                repeat with w in windows of p
                    try
                        set windowName to ""
                        try
                            set windowName to name of w
                        end try
                        set pos to position of w
                        set siz to size of w
                        set end of output to processName & "||" & windowName & "||" & (item 1 of pos) & "||" & (item 2 of pos) & "||" & (item 1 of siz) & "||" & (item 2 of siz) & "||" & frontState
                    end try
                end repeat
            end if
        end try
    end repeat
    return output
end tell
'''
    output = _run_osascript(script, timeout_seconds=timeout_seconds)
    return _parse_system_events_windows(output)


def macos_visible_windows(
    *, max_windows: int = DEFAULT_MAX_WINDOWS, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
) -> ToolResult:
    windows = _quartz_windows()
    source = "quartz"
    partial = False
    error = None
    if not windows:
        try:
            windows = _system_events_windows(timeout_seconds=timeout_seconds)
            source = "system_events"
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            source = "system_events"
            error = _permission_error(exc)
        except Exception as exc:
            source = "system_events"
            error = str(exc)

    if len(windows) > max_windows:
        windows = windows[:max_windows]
        partial = True

    data = {
        "source": source,
        "count": len(windows),
        "partial": partial,
        "windows": windows,
    }
    if windows:
        return ToolResult(
            tool_name="macos_visible_windows",
            success=True,
            data=data,
            metadata={"phase": "real_tool"},
        )

    return ToolResult(
        tool_name="macos_visible_windows",
        success=False,
        data={
            **data,
            "permissions": {
                "accessibility": _check_accessibility(),
                "screen_recording": _check_screen_recording(),
            },
        },
        error=error or "Could not enumerate visible windows",
        metadata={"phase": "real_tool"},
    )


def _installed_apps_from_dir(path: Path) -> list[str]:
    try:
        if not path.exists() or not path.is_dir():
            return []
        return sorted(
            clean_text(item.stem)
            for item in path.iterdir()
            if item.is_dir() and item.suffix == ".app"
        )
    except Exception:
        return []


def macos_list_apps() -> ToolResult:
    app_dirs = [Path("/Applications"), Path("/System/Applications"), Path.home() / "Applications"]
    installed = sorted({app for path in app_dirs for app in _installed_apps_from_dir(path)})
    return ToolResult(
        tool_name="macos_list_apps",
        success=True,
        data={
            "known_apps": KNOWN_APPLICATIONS,
            "aliases": dict(sorted(APP_ALIASES.items())),
            "installed_apps": installed,
        },
        metadata={"phase": "real_tool", "app_dirs": [str(path) for path in app_dirs]},
    )
