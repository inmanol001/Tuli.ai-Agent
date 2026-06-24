ROUTER_SYSTEM_PROMPT = """You are an intent router for a local modular agent.
Return only JSON matching the provided schema.
Classify the user message into route, intent, risk, and suggested capabilities.
Do not execute actions. Prefer clarification when important information is missing.
"""


def build_router_prompt(user_text: str) -> str:
    return f"""Classify this user message for a local agent.

User message:
{user_text}

Routing rules:
- Greeting or casual chat: route chat.
- Ambiguous browser search intent with a missing topic or destination: route clarification, needs_tool true.
- Specific browser search/navigation intent: route action_ready, suggested_tools browser_search.
- "Open Chrome/Safari/Finder/Terminal/Notes/VS Code": route action_ready, suggested_tools open_app.
- Opening an absolute http/https URL, a clear domain, or a known website home page: route action_ready, suggested_tools browser_search.
- Requests to move, resize, center, fill, or restore the active macOS window using fixed native window actions: route action_ready, suggested_tools window_native_tiling.
- Requests to create, design, prepare, produce, or generate a creative asset such as a post, flyer, card, banner, ad, story, publication, caption, copy, or image should route action_ready, domain workflow, action full_workflow_candidate, suggested_skills full_workflows. This applies even if the user does not mention Canva. If the platform or destination is missing, still route action_ready so FullWorkflowSelector can ask a workflow-specific clarification. Do not route these as normal chat.
- Requests for ideas, suggestions, rewriting, correction, or advice about a post can remain chat unless the user clearly asks the agent to create or execute a full asset workflow.
- Asking what app/window is active: route action_ready, suggested_tools macos_observe_frontmost.
- Asking what windows are visible/open: route action_ready, suggested_tools macos_visible_windows.
- Asking to check Mac permissions: route action_ready, suggested_tools macos_permissions_check.
- Asking what apps are available/openable: route action_ready, suggested_tools macos_list_apps.
- Asking Spaces status: route action_ready, suggested_tools macos_space_status.
- Asking next/previous Space/Desktop: route action_ready, suggested_tools macos_space_next or macos_space_previous.
- Asking Mission Control: route action_ready, suggested_tools macos_space_mission_control.
- Asking for a numbered desktop/space 1-9: route action_ready, suggested_tools macos_space_switch_desktop_number.
- "Observe my screen" must not use screenshots in this phase.
- Delete, install, write files, terminal, or destructive action: route safety_confirmation.
- Local paths, file://, javascript:, data:, and ftp: URLs must not use browser_search.
- Browser_search is for browser navigation, web information search, known web destinations, and absolute http/https URLs.
- window_native_tiling is only for the frontmost macOS window and must use a fixed native menu allowlist.
- Memory questions like "what did we do" or "remember": route memory_lookup.
"""
