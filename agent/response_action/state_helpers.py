import re

from agent.gateway.session_manager import SessionState
from agent.router.router_schema import RouterDecision


TOPIC_CHANGE_RE = re.compile(
    r"\b(olvidalo|olvídalo|mejor|cambia|ahora|dime|cuentame|cuéntame|chiste)\b",
    re.I,
)
SHORT_REPLY_RE = re.compile(r"^[\w\sáéíóúñü.,'-]{1,40}$", re.I)
CONFIRMATION_REPLY_RE = re.compile(
    r"^\s*(s[ií]|si|confirma|hazlo|no|cancela|cancelar|olvidalo|olvídalo)\s*[!.?]*\s*$",
    re.I,
)


def is_short_clarification_reply(text: str) -> bool:
    compact = " ".join(text.strip().split())
    if not compact:
        return False
    if TOPIC_CHANGE_RE.search(compact):
        return False
    words = compact.split()
    return len(words) <= 4 and len(compact) <= 40 and bool(SHORT_REPLY_RE.match(compact))


def is_clear_topic_change(text: str) -> bool:
    return bool(TOPIC_CHANGE_RE.search(text.strip()))


def resolve_pending_clarification(
    session: SessionState, user_text: str, decision: RouterDecision
) -> RouterDecision:
    if not session.pending_clarification:
        return decision

    if decision.route == "action_ready":
        return decision

    if decision.route == "clarification":
        return decision

    if decision.route == "chat" and is_short_clarification_reply(user_text):
        promoted = decision.model_copy(deep=True)
        promoted.intent = "action"
        promoted.domain = "browser"
        promoted.action = "search"
        promoted.route = "action_ready"
        promoted.needs_tool = True
        promoted.needs_clarification = False
        promoted.missing_info = []
        promoted.suggested_plugins = ["browser"]
        promoted.suggested_skills = ["browser_search"]
        promoted.suggested_tools = ["browser_search"]
        return promoted

    return decision


def clear_pending_for_topic_change(session: SessionState, user_text: str) -> None:
    if is_clear_topic_change(user_text):
        session.pending_clarification = None
        session.pending_confirmation = None
        setattr(session, "pending_workflow", None)


def clear_pending_workflow_for_topic_change(
    session: SessionState, user_text: str
) -> None:
    if is_clear_topic_change(user_text):
        setattr(session, "pending_workflow", None)
        session.pending_confirmation = None
        session.pending_clarification = None


def clear_stale_pending_confirmation_for_action(
    session: SessionState, user_text: str, decision: RouterDecision
) -> None:
    if not session.pending_confirmation:
        return
    if decision.route != "action_ready" or decision.risk_level != "low":
        return
    if CONFIRMATION_REPLY_RE.match(user_text):
        return
    session.pending_confirmation = None
