import re

from agent.gateway.session_manager import SessionState
from agent.router.router_schema import RouterDecision


TOPIC_CHANGE_RE = re.compile(
    r"\b(olvidalo|olvídalo|mejor|cambia|ahora|dime|cuentame|cuéntame|chiste)\b",
    re.I,
)
SHORT_REPLY_RE = re.compile(r"^[\w\sáéíóúñü.,'-]{1,40}$", re.I)
NEW_REQUEST_RE = re.compile(
    r"\b("
    r"abre|abrir|busca|buscar|investiga|consulta|mueve|mover|acomoda|centra|"
    r"haz|hacer|crea|crear|diseña|diseñar|edita|editar|quiero\s+editar|quiero\s+crear|quiero\s+hacer"
    r")\b",
    re.I,
)

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
    pending = session.pending_clarification
    if not pending:
        return decision

    inferred_pending = infer_pending_from_user_text(user_text) or infer_pending_from_recent_assistant(session)
    if inferred_pending and pending != inferred_pending:
        pending = inferred_pending
        session.pending_clarification = inferred_pending

    normalized = " ".join(user_text.strip().lower().split()).strip(" .,:;!?¿¡")

    if is_clear_topic_change(user_text):
        session.pending_clarification = None
        return decision

    # Si el usuario empieza una solicitud nueva completa, no la encierres
    # dentro del pending anterior. Esto evita que "quiero editar una imagen"
    # sea tratado como nombre de app después de target_app.
    if not is_short_clarification_reply(user_text) and NEW_REQUEST_RE.search(user_text):
        session.pending_clarification = None
        return decision

    if normalized in {"cancel", "cancela", "cancelar", "no", "olvidalo", "olvídalo"}:
        cancelled = decision.model_copy(deep=True)
        cancelled.intent = "chat"
        cancelled.domain = "clarification"
        cancelled.action = "cancel_pending_clarification"
        cancelled.route = "chat"
        cancelled.needs_tool = False
        cancelled.needs_clarification = False
        cancelled.missing_info = []
        cancelled.suggested_plugins = []
        cancelled.suggested_skills = []
        cancelled.suggested_tools = []
        session.pending_clarification = None
        return cancelled

    if is_short_clarification_reply(user_text):
        promoted = decision.model_copy(deep=True)
        promoted.intent = "action"
        promoted.risk_level = "low"
        promoted.route = "action_ready"
        promoted.needs_tool = True
        promoted.needs_clarification = False
        promoted.missing_info = []

        if pending == "window_action":
            promoted.domain = "macos"
            promoted.action = "window_native_tiling"
            promoted.suggested_plugins = ["macos"]
            promoted.suggested_skills = ["macos_windows"]
            promoted.suggested_tools = ["window_native_tiling"]
            promoted.context_needed = [f"pending_clarification:{pending}", f"user_choice:{normalized}"]
            return promoted

        if pending == "target_app":
            promoted.domain = "macos"
            promoted.action = "open_app"
            promoted.suggested_plugins = ["macos"]
            promoted.suggested_skills = ["open_app"]
            promoted.suggested_tools = ["open_app"]
            promoted.context_needed = [f"pending_clarification:{pending}", f"user_choice:{normalized}"]
            return promoted

        if pending in {"target_url", "resolved_reference_confirmation"}:
            promoted.domain = "browser"
            promoted.action = "browser_search"
            promoted.suggested_plugins = ["browser"]
            promoted.suggested_skills = ["browser_search"]
            promoted.suggested_tools = ["browser_search"]
            promoted.context_needed = [f"pending_clarification:{pending}", f"user_choice:{normalized}"]
            return promoted

        if pending in {"search_query", "ambiguous_reference"}:
            promoted.domain = "browser"
            promoted.action = "resolve_pending_reference"
            promoted.suggested_plugins = ["browser"]
            promoted.suggested_skills = ["web_search", "browser_search"]
            promoted.suggested_tools = ["web_search", "browser_search"]
            promoted.context_needed = [f"pending_clarification:{pending}", f"user_choice:{normalized}"]
            return promoted

    return decision




def infer_pending_from_user_text(user_text: str) -> str | None:
    text = " ".join((user_text or "").lower().split())

    if any(x in text for x in ("llévame", "llevame", "ese sitio", "esa página", "esa pagina", "ese website")):
        return "target_url"

    if any(x in text for x in ("investiga eso", "consulta eso", "averigua eso", "busca eso")):
        return "search_query"

    if any(x in text for x in ("mueve la ventana", "acomoda la ventana", "coloca la ventana")):
        return "window_action"

    return None

def infer_pending_from_recent_assistant(session: SessionState) -> str | None:
    for turn in reversed(session.history):
        if turn.role != "assistant" or not turn.content:
            continue

        text = " ".join(turn.content.lower().split())

        if "qué página" in text or "que pagina" in text or "sitio quieres abrir" in text or "url" in text:
            return "target_url"

        if "qué quieres que busque" in text or "que quieres que busque" in text or "tema exacto" in text:
            return "search_query"

        if "acción quieres hacer con la ventana" in text or "accion quieres hacer con la ventana" in text:
            return "window_action"

        if "qué app quieres abrir" in text or "que app quieres abrir" in text:
            return "target_app"

        if "qué quieres crear" in text or "que quieres crear" in text or "diseño" in text or "canva" in text:
            return "target_workflow_or_platform"

        break

    return None

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
