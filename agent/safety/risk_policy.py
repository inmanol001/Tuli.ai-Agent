BLOCKED_PHASE_1_TOOLS = {
    "take_screenshot",
    "screenshot",
    "screen_analysis",
    "open_app",
    "click",
    "type_text",
    "paste_text",
    "terminal_run_command",
    "write_file",
}


def is_phase_1_blocked(tool_name: str) -> bool:
    return tool_name in BLOCKED_PHASE_1_TOOLS

