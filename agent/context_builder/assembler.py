from agent.gateway.message_types import ContextPackage
from agent.capabilities.tools.schemas import ToolCall
from agent.executor.results import ToolResult
from agent.behavior.loader import get_soul_prompt
from agent.rag.formatter import snippets_to_prompt_lines



def _user_memory_prompt_lines(context: ContextPackage) -> list[str]:
    memories = context.session_state.get("user_memories") or []

    if not memories:
        return ["User memories:", "(none)"]

    lines = [
        "User memories:",
        "Use these memories when they are relevant. Do not mention them unless they help answer the user.",
        "Trusted memories are user-confirmed facts; use them naturally and confidently when relevant.",
    ]

    for memory in memories[:8]:
        if not isinstance(memory, dict):
            continue

        memory_type = str(memory.get("memory_type") or "memory").strip()
        key = str(memory.get("key") or "").strip()
        value = str(memory.get("value") or "").strip()

        if not value:
            continue

        trust_level = str(memory.get("trust_level") or "normal").strip()
        verification_count = memory.get("verification_count") or 1
        status = str(memory.get("status") or "active").strip()

        label = memory_type
        if key:
            label = f"{memory_type}:{key}"

        if trust_level == "trusted" or status == "verified":
            label = f"trusted {label}"
            lines.append(
                f"- [{label}] {value} "
                f"(verified_by_user={verification_count})"
            )
        else:
            lines.append(f"- [{label}] {value}")

    if len(lines) == 2:
        lines.append("(none)")

    return lines


def assemble_messages(context: ContextPackage) -> list[dict[str, str]]:
    history_lines = [
        f"{turn.role}: {turn.content}" for turn in context.recent_history[-4:]
    ] or ["(no recent history)"]
    state_lines = [
        f"Previous route: {context.session_state.get('previous_route')}",
        f"Current route: {context.session_state.get('current_route')}",
        f"Pending clarification: {context.session_state.get('pending_clarification')}",
        f"Pending confirmation: {context.session_state.get('pending_confirmation')}",
    ]
    capability_lines = [
        f"Safety rules: {context.safety_rules}",
        f"Task instruction: {context.task_instruction}",
        "Tuli soul:",
        get_soul_prompt(),
        "Session state:",
        *state_lines,
        *_user_memory_prompt_lines(context),
        "Recent history:",
        *history_lines,
        *snippets_to_prompt_lines(context.rag_snippets),
    ]
    return [
        {"role": "system", "content": context.system_prompt},
        {"role": "system", "content": "\n".join(capability_lines)},
        {"role": "user", "content": context.user_message},
    ]


def assemble_action_messages(context: ContextPackage) -> list[dict[str, str]]:
    messages = assemble_messages(context)
    messages.insert(
        1,
        {
            "role": "system",
            "content": (
                "Return only valid JSON matching the provided schema. "
                "Choose one of: chat_response, clarification_question, tool_call, "
                "safety_confirmation, final_answer, error. "
                "If route is action_ready, use an available tool when helpful: "
                "open_app with {'app_name': ...}, web_search with {'query': ..., 'max_results': 5}, browser_search with {'query': ..., 'target': ...}, "
                "macOS observation tools with {}, "
                "or macOS Spaces tools with {} except macos_space_switch_desktop_number "
                "which requires {'number': 1-9}. "
                "Use web_search when the user asks to investigate, look up, search the internet, find news, find documentation, or answer using web results. Use browser_search only when opening/navigating the browser will actually help. "
                "Never invent tool results."
            ),
        },
    )
    return messages


def assemble_final_messages(
    context: ContextPackage, tool_call: ToolCall, tool_result: ToolResult
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": context.system_prompt},
        {
            "role": "system",
            "content": (
                "Use the provided tool result to answer the user. "
                "Do not invent facts beyond the tool result."
            ),
        },
        {"role": "user", "content": context.user_message},
        {
            "role": "tool",
            "content": (
                f"tool_call={tool_call.model_dump(mode='json')} "
                f"tool_result={tool_result.model_dump(mode='json')}"
            ),
        },
    ]
