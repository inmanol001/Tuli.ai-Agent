from __future__ import annotations

import re
import subprocess
from typing import Any

from agent.capabilities.tools.macos_observation_tools import (
    DEFAULT_TIMEOUT_SECONDS,
    macos_observe_frontmost,
    macos_visible_windows,
)
from agent.executor.results import ToolResult


SPACE_CONTROL_METHOD = "system_events_keyboard_shortcut"
SPACE_STATUS_NOTE = "macOS uses internal ManagedSpaceID values, not simple Desktop numbers."
DIRECT_DESKTOP_NOTE = "Direct desktop shortcuts require Mission Control shortcuts enabled."

SPACE_KEY_CODES = {
    "next": 124,
    "previous": 123,
    "mission_control": 126,
    1: 18,
    2: 19,
    3: 20,
    4: 21,
    5: 23,
    6: 22,
    7: 26,
    8: 28,
    9: 25,
}


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


def _friendly_osascript_error(message: str) -> str:
    lower = message.lower()
    if "-10827" in message:
        return "System Events could not send the Spaces keyboard shortcut."
    if "not allowed" in lower or "not authorized" in lower:
        return "Automation or Accessibility permission is not available for System Events."
    return message or "System Events could not send the Spaces keyboard shortcut."


def _script_for_key_code(key_code: int) -> str:
    return f'tell application "System Events" to key code {key_code} using control down'


def _send_shortcut(
    action: str,
    key_code: int,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    note: str | None = None,
) -> ToolResult:
    script = _script_for_key_code(key_code)
    try:
        _run_osascript(script, timeout_seconds=timeout_seconds)
    except FileNotFoundError:
        return ToolResult(
            tool_name=f"macos_{action}",
            success=False,
            data={"action": action, "method": SPACE_CONTROL_METHOD, "key_code": key_code},
            error="osascript is not available on this system",
            metadata={"phase": "real_tool", "script": script},
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            tool_name=f"macos_{action}",
            success=False,
            data={"action": action, "method": SPACE_CONTROL_METHOD, "key_code": key_code},
            error=f"osascript timed out after {timeout_seconds}s",
            metadata={"phase": "real_tool", "script": script},
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or exc.stdout or "").strip()
        return ToolResult(
            tool_name=f"macos_{action}",
            success=False,
            data={
                "action": action,
                "method": SPACE_CONTROL_METHOD,
                "key_code": key_code,
                "note": note,
            },
            error=_friendly_osascript_error(stderr or str(exc.returncode)),
            metadata={"phase": "real_tool", "script": script},
        )

    return ToolResult(
        tool_name=f"macos_{action}",
        success=True,
        data={
            "action": action,
            "method": SPACE_CONTROL_METHOD,
            "key_code": key_code,
            "note": note,
        },
        metadata={"phase": "real_tool", "script": script},
    )


def _parse_space_defaults(text: str) -> dict[str, Any]:
    managed_ids = [int(match) for match in re.findall(r"ManagedSpaceID\s*=\s*(\d+)", text)]
    monitor_matches = re.findall(
        r'"?(?:Display Identifier|DisplayIdentifier|Display UUID|DisplayUUID)"?\s*=',
        text,
    )
    current_match = re.search(r"Current Space[\s\S]{0,500}?ManagedSpaceID\s*=\s*(\d+)", text)
    current_id = int(current_match.group(1)) if current_match else None
    return {
        "current_space": "unknown",
        "current_space_managed_id": current_id,
        "available_spaces_detected": len(set(managed_ids)) if managed_ids else None,
        "monitors": len(monitor_matches) if monitor_matches else None,
        "note": SPACE_STATUS_NOTE,
    }


def _read_space_defaults(*, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    result = subprocess.run(
        ["/usr/bin/defaults", "read", "com.apple.spaces"],
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    return _parse_space_defaults(result.stdout or "")


def macos_space_status(
    *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
) -> ToolResult:
    try:
        status = _read_space_defaults(timeout_seconds=timeout_seconds)
        status_source = "defaults_read_com_apple_spaces"
    except Exception as exc:
        status = {
            "current_space": "unknown",
            "current_space_managed_id": None,
            "available_spaces_detected": None,
            "monitors": None,
            "note": SPACE_STATUS_NOTE,
            "status_error": str(exc),
        }
        status_source = "fallback_unknown"

    frontmost = macos_observe_frontmost(timeout_seconds=timeout_seconds)
    windows = macos_visible_windows(timeout_seconds=timeout_seconds)
    status["frontmost_app"] = (
        frontmost.data.get("app_name") if frontmost.success else "unknown"
    )
    status["visible_windows_count"] = windows.data.get("count") if windows.success else None
    return ToolResult(
        tool_name="macos_space_status",
        success=True,
        data=status,
        metadata={
            "phase": "real_tool",
            "source": status_source,
            "frontmost_success": frontmost.success,
            "visible_windows_success": windows.success,
        },
    )


def macos_space_next(
    *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
) -> ToolResult:
    return _send_shortcut(
        "space_next",
        SPACE_KEY_CODES["next"],
        timeout_seconds=timeout_seconds,
    )


def macos_space_previous(
    *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
) -> ToolResult:
    return _send_shortcut(
        "space_previous",
        SPACE_KEY_CODES["previous"],
        timeout_seconds=timeout_seconds,
    )


def macos_space_mission_control(
    *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
) -> ToolResult:
    return _send_shortcut(
        "space_mission_control",
        SPACE_KEY_CODES["mission_control"],
        timeout_seconds=timeout_seconds,
    )


def macos_space_switch_desktop_number(
    number: int, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
) -> ToolResult:
    if not isinstance(number, int) or isinstance(number, bool) or number not in range(1, 10):
        return ToolResult(
            tool_name="macos_space_switch_desktop_number",
            success=False,
            data={
                "action": "space_switch_desktop_number",
                "number": number,
                "method": SPACE_CONTROL_METHOD,
                "note": DIRECT_DESKTOP_NOTE,
            },
            error="Unsupported desktop number. Use 1 through 9.",
            metadata={"phase": "real_tool"},
        )

    result = _send_shortcut(
        "space_switch_desktop_number",
        SPACE_KEY_CODES[number],
        timeout_seconds=timeout_seconds,
        note=DIRECT_DESKTOP_NOTE,
    )
    result.tool_name = "macos_space_switch_desktop_number"
    result.data["number"] = number
    return result
