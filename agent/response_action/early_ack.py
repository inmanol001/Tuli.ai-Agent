import random


EARLY_ACKS = {
    "browser_search": [
        "Claro, voy a buscarlo ahora.",
        "Dame un momento, voy a abrir la búsqueda.",
        "Voy a revisar eso en el navegador.",
        "Perfecto, voy a buscar eso ahora.",
    ],
    "open_app": [
        "Claro, voy a abrirla.",
        "Dame un momento, abro la app.",
        "Voy a abrir esa aplicación.",
        "Perfecto, voy a abrirla ahora.",
    ],
    "macos_permissions_check": [
        "Claro, reviso los permisos.",
        "Dame un momento, voy a verificar los permisos.",
        "Voy a comprobar los permisos de macOS.",
    ],
    "macos_observe_frontmost": [
        "Claro, reviso qué app está activa.",
        "Dame un momento, voy a ver la app actual.",
        "Voy a revisar qué está al frente ahora.",
    ],
    "macos_visible_windows": [
        "Claro, reviso las ventanas abiertas.",
        "Dame un momento, voy a ver qué ventanas están visibles.",
        "Voy a revisar las ventanas ahora.",
    ],
    "macos_list_apps": [
        "Claro, reviso las apps disponibles.",
        "Dame un momento, voy a listar las aplicaciones.",
        "Voy a ver qué apps puedo abrir.",
    ],
    "macos_space_status": [
        "Claro, reviso el estado de los escritorios.",
        "Dame un momento, verifico el estado de Spaces.",
        "Voy a revisar en qué estado están los escritorios.",
    ],
    "macos_space_next": [
        "Claro, voy al siguiente escritorio.",
        "Dame un momento, voy al siguiente Space.",
        "Voy a moverme al próximo escritorio.",
    ],
    "macos_space_previous": [
        "Claro, voy al escritorio anterior.",
        "Dame un momento, regreso al Space anterior.",
        "Voy al escritorio anterior.",
    ],
    "macos_space_mission_control": [
        "Claro, voy a abrir Mission Control.",
        "Dame un momento, voy a mostrar Mission Control.",
        "Voy a abrir Mission Control ahora.",
    ],
    "macos_space_switch_desktop_number": [
        "Claro, voy a cambiar a ese escritorio.",
        "Dame un momento, voy a ese Space.",
        "Voy a cambiar al escritorio indicado.",
    ],
}


DEFAULT_EARLY_ACKS = [
    "Claro, dame un momento.",
    "Perfecto, voy con eso.",
    "Entendido, lo reviso ahora.",
]


def build_early_ack(suggested_tools: list[str]) -> str:
    tool_name = suggested_tools[0] if suggested_tools else ""
    options = EARLY_ACKS.get(tool_name) or DEFAULT_EARLY_ACKS
    return random.choice(options)
