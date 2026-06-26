import re

from agent.router.router_schema import RouterDecision


GREETING_RE = re.compile(r"^\s*(hola|hello|hi|buenas|hey)\s*[!.?]*\s*$", re.I)
YOUTUBE_RE = re.compile(r"\b(youtube|you tube)\b", re.I)
KNOWN_WEB_DESTINATION_RE = re.compile(
    r"\b(google|youtube|you\s*tube|github|openai|ollama|canva|facebook|instagram|tiktok)\b",
    re.I,
)

VISIBLE_BROWSER_RE = re.compile(
    r"\b("
    r"mu[eé]strame|mu[eé]stralo|muestralo|muestres|mostrar|muestra|quiero\s+ver|ver|ponme|pon"
    r")\b.*\b("
    r"navegador|abierto|abierta|sitio|p[aá]gina|web|google|youtube|github|openai|ollama|canva"
    r")\b|"
    r"\b("
    r"navegador|abierto|abierta|sitio|p[aá]gina|web|google|youtube|github|openai|ollama|canva"
    r")\b.*\b("
    r"mu[eé]strame|mostrar|muestra|quiero\s+ver|ver|ponme|pon"
    r")\b",
    re.I,
)

GOOGLE_VISIBLE_SEARCH_RE = re.compile(
    r"\b(busca|buscar|search|abre|abrir|open)\b.*\b(en\s+google|google)\b|"
    r"\b(en\s+google|google)\b.*\b(busca|buscar|search)\b",
    re.I,
)

WEB_RESEARCH_BROAD_RE = re.compile(
    r"\b("
    r"compara|comparar|compare|"
    r"investiga|investigar|investigues|research|"
    r"fuentes|sources|referencias|references|"
    r"quiero\s+leer\s+sobre|leer\s+sobre|"
    r"dime\s+qu[eé]\s+encuentras|qu[eé]\s+encuentras\s+sobre"
    r")\b",
    re.I,
)
MUSIC_RE = re.compile(r"\b(m[uú]sica|canci[oó]n|video|videos|song|music)\b", re.I)
OPEN_RE = re.compile(r"\b(abre|abrir|open)\b", re.I)
HTTP_URL_RE = re.compile(r"\bhttps?://[^\s]+", re.I)
DANGEROUS_URL_RE = re.compile(r"\b(file|javascript|data|ftp):", re.I)
LOCAL_PATH_RE = re.compile(r"(^|\s)(/Users/|~/|/Applications/|/System/|/tmp/)", re.I)
DOMAIN_RE = re.compile(r"\b([a-z0-9-]+\.)+[a-z]{2,}(/[^\s]*)?\b", re.I)
BROWSER_SEARCH_RE = re.compile(
    r"\b(busca|buscar|search|googlea|googlear|informaci[oó]n sobre|"
    r"info sobre|investiga)\b",
    re.I,
)

WEB_INFO_SEARCH_RE = re.compile(
    r"\b(?:"
    r"investiga|investigar|research|look\s+up|"
    r"busca(?:r)?\s+(?:en\s+internet|en\s+la\s+web|informaci[oó]n|noticias|documentaci[oó]n|docs?)|"
    r"informaci[oó]n\s+sobre|info\s+sobre|"
    r"noticias|news|actualidad|"
    r"[uú]ltim[ao]s?|latest|reciente|current|"
    r"documentaci[oó]n|docs?"
    r")\b",
    re.I,
)

FRONTMOST_RE = re.compile(
    r"\b(qu[eé]\s+app\s+est[aá]\s+abierta|qu[eé]\s+estoy\s+viendo|"
    r"observa\s+la\s+app\s+actual|cu[aá]l\s+es\s+la\s+ventana\s+activa|"
    r"app\s+activa|frontmost)\b",
    re.I,
)
VISIBLE_WINDOWS_RE = re.compile(
    r"\b("
    r"mu[eé]strame|muestra|listar|lista|ver|ense[ñn]ame|dime"
    r")\b.*\b("
    r"ventanas|windows"
    r")\b.*\b("
    r"visibles|disponibles|abiertas|abiertos|actuales|activas"
    r")\b|"
    r"\b("
    r"ventanas|windows"
    r")\b.*\b("
    r"visibles|disponibles|abiertas|actuales|activas"
    r")\b",
    re.I,
)
PERMISSIONS_RE = re.compile(
    r"\b(qu[eé]\s+permisos\s+tiene\s+el\s+agente|revisa\s+permisos\s+de\s+mac|"
    r"verifica\s+permisos|permisos\s+de\s+mac|permisos\s+tiene)\b",
    re.I,
)
LIST_APPS_RE = re.compile(
    r"\b(lista\s+apps|qu[eé]\s+apps\s+puedo\s+abrir|apps\s+disponibles|"
    r"aplicaciones\s+disponibles)\b",
    re.I,
)
SCREEN_OBSERVE_RE = re.compile(r"\b(observa|mira|ve)\s+mi\s+pantalla\b", re.I)
SPACE_NEXT_RE = re.compile(
    r"\b(cambia\s+al\s+siguiente\s+escritorio|ve\s+al\s+siguiente\s+space|"
    r"space\s+siguiente|desktop\s+siguiente|siguiente\s+escritorio)\b",
    re.I,
)
SPACE_PREVIOUS_RE = re.compile(
    r"\b(cambia\s+al\s+escritorio\s+anterior|ve\s+al\s+space\s+anterior|"
    r"space\s+anterior|desktop\s+anterior|escritorio\s+anterior)\b",
    re.I,
)
MISSION_CONTROL_RE = re.compile(
    r"\b(?:"
    r"mission\s+control|"
    r"mision\s+control|"
    r"misión\s+control|"
    r"control\s+de\s+misi[oó]n|"
    r"vista\s+de\s+escritorios"
    r")\b",
    re.I,
)
SPACE_SWITCH_NUMBER_RE = re.compile(
    r"\b(?:(?:cambia|ve)\s+a?l?\s+|(?:perd[oó]n\s+)?me\s+refiero\s+al\s+)"
    r"(?:escritori(?:o)?|desktop|space)\s+(\d+)\b",
    re.I,
)
SPACE_STATUS_RE = re.compile(
    r"\b(estado\s+de\s+spaces|en\s+qu[eé]\s+escritorio\s+estoy|"
    r"estado\s+del\s+escritorio)\b",
    re.I,
)
WINDOW_TILING_SPECIFIC_RE = re.compile(
    r"\b(ventana|window)\b.*\b("
    r"izquierd\w*|derech\w*|arrib\w*|abaj\w*|centr\w*|center|fill|llen\w*|esquin\w*|"
    r"return|anterior\w*|previous|quarters?|left\s*&\s*right|left-right"
    r")\b|\b("
    r"izquierd\w*|derech\w*|arrib\w*|abaj\w*|centr\w*|center|fill|llen\w*|esquin\w*|"
    r"return|anterior\w*|previous|quarters?|left\s*&\s*right|left-right"
    r")\b.*\b(ventana|window)\b",
    re.I,
)
WINDOW_TILING_STANDALONE_RE = re.compile(
    r"\b(vuelve\s+al\s+tama[ñn]o\s+anterior|return\s+to\s+previous\s+size|"
    r"fill|center|centra(?:r)?|left\s*&\s*right|left-right|quarters?|"
    r"top-left|top-right|bottom-left|bottom-right)\b",
    re.I,
)
WINDOW_TILING_GENERIC_RE = re.compile(
    r"\b(mueve|mover|pon|coloca|manda|resize|redimensiona|acomoda)\b.*\b(ventana|window)\b|"
    r"\b(ventana|window)\b.*\b(mueve|mover|pon|coloca|manda|resize|redimensiona|acomoda)\b",
    re.I,
)
FULL_WORKFLOW_CANVA_DESIGN_RE = re.compile(
    r"\b("
    r"haz|hacer|crea|crear|dise[ñn]a|dise[ñn]ar|prepara|preparar|genera|generar"
    r")\b.*\b("
    r"post|dise[ñn]o|flyer|tarjeta|anuncio|banner|imagen|pieza|arte|historia|story|reel|publicaci[oó]n"
    r")\b.*\bcanva\b|"
    r"\bcanva\b.*\b("
    r"post|dise[ñn]o|flyer|tarjeta|anuncio|banner|imagen|pieza|arte|historia|story|reel|publicaci[oó]n"
    r")\b",
    re.I,
)
FULL_WORKFLOW_CREATIVE_ASSET_RE = re.compile(
    r"\b("
    r"haz|hacer|crea|crear|dise[ñn]a|dise[ñn]ar|prepara|preparar|genera|generar|produce|producir"
    r")\b.*\b("
    r"post|dise[ñn]o|flyer|tarjeta|anuncio|banner|imagen|pieza|arte|historia|story|reel|publicaci[oó]n|caption|copy"
    r")\b",
    re.I,
)
CREATIVE_CHAT_ONLY_RE = re.compile(
    r"\b("
    r"dame ideas|ideas para|qu[eé] puedo escribir|sugerencias|ay[uú]dame a mejorar|corrige|reescribe|mejora"
    r")\b",
    re.I,
)
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
SPECIFIC_MUSIC_RE = re.compile(
    r"\b(artista|album|canci[oó]n|nueva|nuevo|de\s+[a-z0-9áéíóúñ ]{3,})\b",
    re.I,
)
SAFETY_RE = re.compile(
    r"\b(borra|borrar|elimina|eliminar|delete|rm\s+-|instala|instalar|install|"
    r"escribe|write|comando|sudo)\b",
    re.I,
)
MEMORY_RE = re.compile(
    r"\b(qu[eé]\s+hicimos|recuerdas|recuerda|memoria|problema anterior|"
    r"what did we do|remember)\b",
    re.I,
)
RAG_RE = re.compile(
    r"\b(base de conocimiento|knowledge base|seg[uú]n mis notas|mis notas|"
    r"en los documentos|documentos locales|procedimiento|procedimientos|"
    r"consulta local|documentaci[oó]n local)\b",
    re.I,
)

def validate_and_correct_router_decision(
    decision: RouterDecision, user_text: str
) -> tuple[RouterDecision, bool]:
    text = user_text.strip()
    corrected = False

    if GREETING_RE.search(text):
        decision = RouterDecision(intent="chat", route="chat", needs_tool=False)
        return decision, True

    # Capability guard: Mission Control is a known macOS Spaces capability.
    # If the user mentions this capability, do not let the router fall back to chat.
    if MISSION_CONTROL_RE.search(text):
        decision.intent = "action"
        decision.domain = "macos"
        decision.action = "space_mission_control"
        decision.route = "action_ready"
        decision.needs_tool = True
        decision.risk_level = "low"
        decision.needs_clarification = False
        decision.missing_info = []
        decision.context_needed = []
        decision.needs_memory = False
        decision.needs_rag = False
        decision.needs_vision = False
        decision.suggested_plugins = ["macos"]
        decision.suggested_skills = ["macos_spaces"]
        decision.suggested_tools = ["macos_space_mission_control"]
        return decision, True

    # Guard clause: Mission Control must never fall through to generic chat.
    # The macOS Spaces tool is low-risk and deterministic.
    if MISSION_CONTROL_RE.search(text):
        decision.intent = "action"
        decision.domain = "macos"
        decision.action = "space_mission_control"
        decision.route = "action_ready"
        decision.needs_tool = True
        decision.risk_level = "low"
        decision.needs_clarification = False
        decision.missing_info = []
        decision.context_needed = []
        decision.needs_memory = False
        decision.needs_rag = False
        decision.needs_vision = False
        decision.suggested_plugins = ["macos"]
        decision.suggested_skills = ["macos_spaces"]
        decision.suggested_tools = ["macos_space_mission_control"]
        return decision, True

    if SCREEN_OBSERVE_RE.search(text):
        decision.intent = "refuse"
        decision.domain = "macos"
        decision.action = "screen_observation_unavailable"
        decision.route = "refuse"
        decision.risk_level = "medium"
        decision.needs_tool = False
        decision.suggested_plugins = []
        decision.suggested_skills = []
        decision.suggested_tools = []
        corrected = True

    elif SAFETY_RE.search(text):
        decision.intent = "safety"
        decision.domain = "safety"
        decision.action = "confirm_before_action"
        decision.route = "safety_confirmation"
        decision.risk_level = "medium"
        decision.needs_tool = False
        decision.needs_clarification = False
        decision.suggested_plugins = []
        decision.suggested_skills = []
        decision.suggested_tools = []
        corrected = True

    elif PERMISSIONS_RE.search(text):
        decision.intent = "action"
        decision.domain = "macos"
        decision.action = "permissions_check"
        decision.route = "action_ready"
        decision.needs_tool = True
        decision.risk_level = "low"
        decision.needs_clarification = False
        decision.suggested_plugins = ["macos"]
        decision.suggested_skills = ["macos_observation"]
        decision.suggested_tools = ["macos_permissions_check"]
        corrected = True

    elif FRONTMOST_RE.search(text):
        decision.intent = "action"
        decision.domain = "macos"
        decision.action = "observe_frontmost"
        decision.route = "action_ready"
        decision.needs_tool = True
        decision.risk_level = "low"
        decision.needs_clarification = False
        decision.suggested_plugins = ["macos"]
        decision.suggested_skills = ["macos_observation"]
        decision.suggested_tools = ["macos_observe_frontmost"]
        corrected = True

    elif VISIBLE_WINDOWS_RE.search(text):
        decision.intent = "action"
        decision.domain = "macos"
        decision.action = "visible_windows"
        decision.route = "action_ready"
        decision.needs_tool = True
        decision.risk_level = "low"
        decision.needs_clarification = False
        decision.suggested_plugins = ["macos"]
        decision.suggested_skills = ["macos_observation"]
        decision.suggested_tools = ["macos_visible_windows"]
        corrected = True

    elif LIST_APPS_RE.search(text):
        decision.intent = "action"
        decision.domain = "macos"
        decision.action = "list_apps"
        decision.route = "action_ready"
        decision.needs_tool = True
        decision.risk_level = "low"
        decision.needs_clarification = False
        decision.suggested_plugins = ["macos"]
        decision.suggested_skills = ["macos_observation"]
        decision.suggested_tools = ["macos_list_apps"]
        corrected = True

    elif SPACE_STATUS_RE.search(text):
        decision.intent = "action"
        decision.domain = "macos"
        decision.action = "space_status"
        decision.route = "action_ready"
        decision.needs_tool = True
        decision.risk_level = "low"
        decision.needs_clarification = False
        decision.suggested_plugins = ["macos"]
        decision.suggested_skills = ["macos_spaces"]
        decision.suggested_tools = ["macos_space_status"]
        corrected = True

    elif SPACE_NEXT_RE.search(text):
        decision.intent = "action"
        decision.domain = "macos"
        decision.action = "space_next"
        decision.route = "action_ready"
        decision.needs_tool = True
        decision.risk_level = "low"
        decision.needs_clarification = False
        decision.suggested_plugins = ["macos"]
        decision.suggested_skills = ["macos_spaces"]
        decision.suggested_tools = ["macos_space_next"]
        corrected = True

    elif SPACE_PREVIOUS_RE.search(text):
        decision.intent = "action"
        decision.domain = "macos"
        decision.action = "space_previous"
        decision.route = "action_ready"
        decision.needs_tool = True
        decision.risk_level = "low"
        decision.needs_clarification = False
        decision.suggested_plugins = ["macos"]
        decision.suggested_skills = ["macos_spaces"]
        decision.suggested_tools = ["macos_space_previous"]
        corrected = True

    elif MISSION_CONTROL_RE.search(text):
        decision.intent = "action"
        decision.domain = "macos"
        decision.action = "space_mission_control"
        decision.route = "action_ready"
        decision.needs_tool = True
        decision.risk_level = "low"
        decision.needs_clarification = False
        decision.suggested_plugins = ["macos"]
        decision.suggested_skills = ["macos_spaces"]
        decision.suggested_tools = ["macos_space_mission_control"]
        corrected = True

    elif SPACE_SWITCH_NUMBER_RE.search(text):
        decision.intent = "action"
        decision.domain = "macos"
        decision.action = "space_switch_desktop_number"
        decision.route = "action_ready"
        decision.needs_tool = True
        decision.risk_level = "low"
        decision.needs_clarification = False
        decision.suggested_plugins = ["macos"]
        decision.suggested_skills = ["macos_spaces"]
        decision.suggested_tools = ["macos_space_switch_desktop_number"]
        corrected = True

    elif WINDOW_TILING_SPECIFIC_RE.search(text) or WINDOW_TILING_STANDALONE_RE.search(text):
        decision.intent = "action"
        decision.domain = "macos"
        decision.action = "window_native_tiling"
        decision.route = "action_ready"
        decision.needs_tool = True
        decision.risk_level = "low"
        decision.needs_clarification = False
        decision.suggested_plugins = ["macos"]
        decision.suggested_skills = ["macos_windows"]
        decision.suggested_tools = ["window_native_tiling"]
        corrected = True

    elif WINDOW_TILING_GENERIC_RE.search(text):
        decision.intent = "action"
        decision.domain = "macos"
        decision.action = "window_native_tiling"
        decision.route = "clarification"
        decision.needs_tool = True
        decision.risk_level = "low"
        decision.needs_clarification = True
        decision.missing_info = ["window_action"]
        decision.suggested_plugins = ["macos"]
        decision.suggested_skills = ["macos_windows"]
        decision.suggested_tools = ["window_native_tiling"]
        corrected = True

    elif (
        FULL_WORKFLOW_CANVA_DESIGN_RE.search(text)
        or (
            FULL_WORKFLOW_CREATIVE_ASSET_RE.search(text)
            and not CREATIVE_CHAT_ONLY_RE.search(text)
        )
    ):
        decision.intent = "action"
        decision.domain = "workflow"
        decision.action = "full_workflow_candidate"
        decision.route = "action_ready"
        decision.needs_tool = True
        decision.needs_clarification = False
        decision.missing_info = []
        decision.needs_memory = False
        decision.needs_rag = False
        decision.risk_level = "low"
        decision.suggested_plugins = []
        decision.suggested_skills = ["full_workflows"]
        decision.suggested_tools = []
        corrected = True

    elif OPEN_RE.search(text) and KNOWN_WEB_DESTINATION_RE.search(text):
        decision.intent = "action"
        decision.domain = "browser"
        decision.action = "browser_search"
        decision.route = "action_ready"
        decision.needs_tool = True
        decision.risk_level = "low"
        decision.needs_clarification = False
        decision.suggested_plugins = ["browser"]
        decision.suggested_skills = ["browser_search"]
        decision.suggested_tools = ["browser_search"]
        corrected = True

    elif VISIBLE_BROWSER_RE.search(text) and KNOWN_WEB_DESTINATION_RE.search(text):
        decision.intent = "action"
        decision.domain = "browser"
        decision.action = "browser_search"
        decision.route = "action_ready"
        decision.needs_tool = True
        decision.risk_level = "low"
        decision.needs_clarification = False
        decision.suggested_plugins = ["browser"]
        decision.suggested_skills = ["browser_search"]
        decision.suggested_tools = ["browser_search"]
        corrected = True

    elif OPEN_RE.search(text) and (
        DANGEROUS_URL_RE.search(text) or LOCAL_PATH_RE.search(text)
    ):
        decision.intent = "refuse"
        decision.domain = "browser"
        decision.action = "browser_search"
        decision.route = "refuse"
        decision.risk_level = "medium"
        decision.needs_tool = False
        decision.needs_clarification = False
        decision.suggested_plugins = []
        decision.suggested_skills = []
        decision.suggested_tools = []
        corrected = True

    elif OPEN_RE.search(text) and (HTTP_URL_RE.search(text) or DOMAIN_RE.search(text)):
        decision.intent = "action"
        decision.domain = "browser"
        decision.action = "browser_search"
        decision.route = "action_ready"
        decision.needs_tool = True
        decision.risk_level = "low"
        decision.needs_clarification = False
        decision.suggested_plugins = ["browser"]
        decision.suggested_skills = ["browser_search"]
        decision.suggested_tools = ["browser_search"]
        corrected = True

    elif OPEN_RE.search(text) and YOUTUBE_RE.search(text):
        decision.intent = "action"
        decision.domain = "browser"
        decision.action = "browser_search"
        decision.route = "action_ready"
        decision.needs_tool = True
        decision.risk_level = "low"
        decision.needs_clarification = False
        decision.suggested_plugins = ["browser"]
        decision.suggested_skills = ["browser_search"]
        decision.suggested_tools = ["browser_search"]
        corrected = True

    elif OPEN_RE.search(text) and any(alias in text.lower() for alias in APP_ALIASES):
        decision.intent = "action"
        decision.domain = "macos"
        decision.action = "open_app"
        decision.route = "action_ready"
        decision.needs_tool = True
        decision.risk_level = "low"
        decision.needs_clarification = False
        decision.suggested_plugins = ["macos"]
        decision.suggested_skills = ["open_app"]
        decision.suggested_tools = ["open_app"]
        corrected = True

    elif MEMORY_RE.search(text):
        decision.intent = "memory"
        decision.domain = "memory"
        decision.action = "lookup"
        decision.route = "memory_lookup"
        decision.needs_memory = True
        decision.needs_tool = False
        corrected = True

    elif RAG_RE.search(text):
        decision.intent = "rag"
        decision.domain = "knowledge_base"
        decision.action = "lookup"
        decision.route = "rag_lookup"
        decision.needs_rag = True
        decision.needs_tool = False
        decision.needs_memory = False
        corrected = True

    elif YOUTUBE_RE.search(text) and MUSIC_RE.search(text):
        decision.intent = "action"
        decision.domain = "youtube"
        decision.action = "search"
        decision.needs_tool = True
        decision.risk_level = "low"
        decision.suggested_plugins = ["browser"]
        decision.suggested_skills = ["browser_search"]
        decision.suggested_tools = ["browser_search"]
        if SPECIFIC_MUSIC_RE.search(text):
            decision.route = "action_ready"
            decision.needs_clarification = False
            decision.missing_info = []
        else:
            decision.route = "clarification"
            decision.needs_clarification = True
            decision.missing_info = ["artist_or_genre"]
        corrected = True

    elif GOOGLE_VISIBLE_SEARCH_RE.search(text):
        decision.intent = "action"
        decision.domain = "browser"
        decision.action = "browser_search"
        decision.route = "action_ready"
        decision.needs_tool = True
        decision.risk_level = "low"
        decision.needs_clarification = False
        decision.missing_info = []
        decision.suggested_plugins = ["browser"]
        decision.suggested_skills = ["browser_search"]
        decision.suggested_tools = ["browser_search"]
        corrected = True

    elif WEB_RESEARCH_BROAD_RE.search(text) and not YOUTUBE_RE.search(text) and not GOOGLE_VISIBLE_SEARCH_RE.search(text):
        decision.intent = "action"
        decision.domain = "browser"
        decision.action = "web_search"
        decision.route = "action_ready"
        decision.needs_tool = True
        decision.risk_level = "low"
        decision.needs_clarification = False
        decision.missing_info = []
        decision.suggested_plugins = ["browser"]
        decision.suggested_skills = ["web_search"]
        decision.suggested_tools = ["web_search"]
        corrected = True

    elif WEB_INFO_SEARCH_RE.search(text) and not YOUTUBE_RE.search(text) and not (
        OPEN_RE.search(text) and (HTTP_URL_RE.search(text) or DOMAIN_RE.search(text))
    ):
        decision.intent = "action"
        decision.domain = "browser"
        decision.action = "web_search"
        decision.route = "action_ready"
        decision.needs_tool = True
        decision.risk_level = "low"
        decision.needs_clarification = False
        decision.missing_info = []
        decision.suggested_plugins = ["browser"]
        decision.suggested_skills = ["web_search"]
        decision.suggested_tools = ["web_search"]

    elif BROWSER_SEARCH_RE.search(text):
        decision.intent = "action"
        decision.domain = "browser"
        decision.action = "browser_search"
        decision.route = "action_ready"
        decision.needs_tool = True
        decision.risk_level = "low"
        decision.needs_clarification = False
        decision.suggested_plugins = ["browser"]
        decision.suggested_skills = ["browser_search"]
        decision.suggested_tools = ["browser_search"]
        corrected = True

    if decision.needs_vision:
        decision.needs_vision = False
        corrected = True

    if decision.suggested_tools:
        allowed_tools = {
            "web_search",
            "browser_search",
            "open_app",
            "window_native_tiling",
            "macos_permissions_check",
            "macos_observe_frontmost",
            "macos_visible_windows",
            "macos_list_apps",
            "macos_space_status",
            "macos_space_next",
            "macos_space_previous",
            "macos_space_mission_control",
            "macos_space_switch_desktop_number",
        }
        decision.suggested_tools = [
            tool for tool in decision.suggested_tools if tool in allowed_tools
        ]
        corrected = True

    if decision.route == "rag_lookup":
        decision.intent = "rag"
        decision.domain = "knowledge_base"
        decision.action = "lookup"
        decision.needs_rag = True
        decision.needs_tool = False
        corrected = True

    return decision, corrected
