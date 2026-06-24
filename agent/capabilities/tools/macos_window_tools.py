from __future__ import annotations

import subprocess
from typing import Any, Mapping

from agent.executor.results import ToolResult


DEFAULT_TIMEOUT_SECONDS = 5

NATIVE_TILING_ACTIONS = (
    "fill",
    "center",
    "left",
    "right",
    "top",
    "bottom",
    "top-left",
    "top-right",
    "bottom-left",
    "bottom-right",
    "left-right",
    "quarters",
    "return",
)

NATIVE_TILING_MENU_ACTIONS: dict[str, Mapping[str, str]] = {
    "fill": {"menu": "Window", "item": "Fill"},
    "center": {"menu": "Window", "item": "Center"},
    "left": {"menu": "Window", "submenu": "Move & Resize", "item": "Left"},
    "right": {"menu": "Window", "submenu": "Move & Resize", "item": "Right"},
    "top": {"menu": "Window", "submenu": "Move & Resize", "item": "Top"},
    "bottom": {"menu": "Window", "submenu": "Move & Resize", "item": "Bottom"},
    "top-left": {"menu": "Window", "submenu": "Move & Resize", "item": "Top Left"},
    "top-right": {"menu": "Window", "submenu": "Move & Resize", "item": "Top Right"},
    "bottom-left": {"menu": "Window", "submenu": "Move & Resize", "item": "Bottom Left"},
    "bottom-right": {"menu": "Window", "submenu": "Move & Resize", "item": "Bottom Right"},
    "left-right": {"menu": "Window", "submenu": "Move & Resize", "item": "Left & Right"},
    "quarters": {"menu": "Window", "submenu": "Move & Resize", "item": "Quarters"},
    "return": {
        "menu": "Window",
        "submenu": "Move & Resize",
        "item": "Return to Previous Size",
    },
}


def _apple_script_string_literal(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _menu_path_for_action(action: str, menu_action: Mapping[str, str]) -> str:
    parts = [menu_action["menu"]]
    submenu = menu_action.get("submenu")
    if submenu:
        parts.append(submenu)
    parts.append(menu_action["item"])
    return " > ".join(parts)


def _friendly_osascript_error(message: str) -> str:
    lower = message.lower()
    if "-10827" in message or "-1719" in message or "menu item not found" in lower:
        return "menu item not found or System Events denied access."
    if "not allowed" in lower or "not authorized" in lower:
        return "Automation or Accessibility permission is not available for System Events."
    return message or "menu item not found or System Events denied access."


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


def _build_window_menu_script(menu_action: Mapping[str, str]) -> str:
    menu = menu_action["menu"]
    submenu = menu_action.get("submenu")
    item = menu_action["item"]

    menu_literal = _apple_script_string_literal(menu)
    item_literal = _apple_script_string_literal(item)
    menu_path = _menu_path_for_action("action", menu_action)
    menu_path_literal = _apple_script_string_literal(menu_path)

    if submenu:
        submenu_literal = _apple_script_string_literal(submenu)
        click_block = f"""
    if not (exists menu item {submenu_literal} of windowMenu) then error "menu item not found: {menu_path}"
    set targetMenu to menu 1 of menu item {submenu_literal} of windowMenu
    if not (exists menu item {item_literal} of targetMenu) then error "menu item not found: {menu_path}"
    click menu item {item_literal} of targetMenu
"""
    else:
        click_block = f"""
    if not (exists menu item {item_literal} of windowMenu) then error "menu item not found: {menu_path}"
    click menu item {item_literal} of windowMenu
"""

    return f"""
tell application "System Events"
    set frontApp to first application process whose frontmost is true
    set appName to name of frontApp
    if not (exists menu bar 1 of frontApp) then error "Frontmost app has no accessible menu bar."
    if not (exists menu bar item {menu_literal} of menu bar 1 of frontApp) then error "menu item not found: {menu}"
    set windowMenu to menu 1 of menu bar item {menu_literal} of menu bar 1 of frontApp
{click_block}
    return appName & "||" & {menu_path_literal}
end tell
"""


def window_native_tiling(
    action: str, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
) -> ToolResult:
    normalized = str(action or "").strip().lower()
    menu_action = NATIVE_TILING_MENU_ACTIONS.get(normalized)
    if menu_action is None:
        return ToolResult(
            tool_name="window_native_tiling",
            success=False,
            data={
                "action": normalized,
                "target": "frontmost window",
                "method": "system_events_window_menu",
                "success": False,
                "details": {"allowed_actions": list(NATIVE_TILING_ACTIONS)},
            },
            error=f"Unsupported native tiling action: {action}",
            metadata={"phase": "real_tool"},
        )

    menu_path = _menu_path_for_action(normalized, menu_action)
    script = _build_window_menu_script(menu_action)

    try:
        raw = _run_osascript(script, timeout_seconds=timeout_seconds)
    except FileNotFoundError:
        return ToolResult(
            tool_name="window_native_tiling",
            success=False,
            data={
                "action": normalized,
                "target": "frontmost window",
                "method": "system_events_window_menu",
                "success": False,
                "menu_path": menu_path,
                "details": {"allowed_actions": list(NATIVE_TILING_ACTIONS)},
            },
            error="osascript is not available on this system",
            metadata={"phase": "real_tool", "script": script},
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            tool_name="window_native_tiling",
            success=False,
            data={
                "action": normalized,
                "target": "frontmost window",
                "method": "system_events_window_menu",
                "success": False,
                "menu_path": menu_path,
                "details": {"allowed_actions": list(NATIVE_TILING_ACTIONS)},
            },
            error=f"window_native_tiling timed out after {timeout_seconds}s",
            metadata={"phase": "real_tool", "script": script},
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or exc.stdout or "").strip()
        return ToolResult(
            tool_name="window_native_tiling",
            success=False,
            data={
                "action": normalized,
                "target": "frontmost window",
                "method": "system_events_window_menu",
                "success": False,
                "menu_path": menu_path,
                "details": {"allowed_actions": list(NATIVE_TILING_ACTIONS)},
            },
            error=_friendly_osascript_error(stderr or str(exc.returncode)),
            metadata={"phase": "real_tool", "script": script},
        )

    parts = raw.split("||")
    frontmost_app = parts[0].strip() if parts and parts[0].strip() else None
    returned_menu_path = (
        parts[1].strip() if len(parts) > 1 and parts[1].strip() else menu_path
    )
    return ToolResult(
        tool_name="window_native_tiling",
        success=True,
        data={
            "action": normalized,
            "target": "frontmost window",
            "method": "system_events_window_menu",
            "success": True,
            "menu_path": returned_menu_path,
            "frontmost_app": frontmost_app,
            "verified": False,
        },
        metadata={"phase": "real_tool", "script": script},
    )
