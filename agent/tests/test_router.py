from agent.router.router_schema import RouterDecision
from agent.router.router_validator import validate_and_correct_router_decision


def route_for(text: str) -> RouterDecision:
    decision, _ = validate_and_correct_router_decision(RouterDecision(), text)
    return decision


def test_greeting_routes_to_chat():
    decision = route_for("hola")
    assert decision.route == "chat"
    assert decision.needs_tool is False


def test_ambiguous_youtube_routes_to_clarification():
    decision = route_for("busca música en YouTube")
    assert decision.route == "clarification"
    assert decision.needs_tool is True
    assert "artist_or_genre" in decision.missing_info


def test_specific_youtube_routes_to_action_ready():
    decision = route_for("busca omega en YouTube")
    assert decision.route == "action_ready"
    assert decision.suggested_tools == ["browser_search"]


def test_open_chrome_routes_to_open_app():
    decision = route_for("abre Chrome")
    assert decision.route == "action_ready"
    assert decision.suggested_tools == ["open_app"]
    assert decision.suggested_plugins == ["macos"]


def test_open_url_routes_to_browser_search():
    decision = route_for("abre https://youtube.com")
    assert decision.route == "action_ready"
    assert decision.suggested_tools == ["browser_search"]


def test_open_clear_domain_routes_to_browser_search():
    decision = route_for("abre google.com")
    assert decision.route == "action_ready"
    assert decision.suggested_tools == ["browser_search"]


def test_open_youtube_routes_to_browser_search():
    decision = route_for("abre YouTube")
    assert decision.route == "action_ready"
    assert decision.suggested_tools == ["browser_search"]


def test_general_web_search_routes_to_browser_search():
    decision = route_for("busca información sobre macOS Spaces")
    assert decision.route == "action_ready"
    assert decision.suggested_tools == ["browser_search"]


def test_canva_post_routes_to_full_workflow_candidate():
    decision = route_for("haz un post en Canva del Día del Padre")
    assert decision.route == "action_ready"
    assert decision.intent == "action"
    assert decision.domain == "workflow"
    assert decision.action == "full_workflow_candidate"
    assert decision.needs_tool is True
    assert decision.needs_clarification is False
    assert decision.missing_info == []
    assert decision.risk_level == "low"
    assert decision.suggested_tools == []


def test_canva_design_routes_to_full_workflow_candidate():
    decision = route_for("crea un diseño en Canva para el Día de las Madres")
    assert decision.route == "action_ready"
    assert decision.domain == "workflow"
    assert decision.action == "full_workflow_candidate"


def test_canva_flyer_routes_to_full_workflow_candidate():
    decision = route_for("diseña un flyer en Canva sobre una oferta")
    assert decision.route == "action_ready"
    assert decision.domain == "workflow"
    assert decision.action == "full_workflow_candidate"


def test_canva_image_routes_to_full_workflow_candidate():
    decision = route_for("haz una imagen para Instagram en Canva de Bellamar")
    assert decision.route == "action_ready"
    assert decision.domain == "workflow"
    assert decision.action == "full_workflow_candidate"


def test_canva_card_routes_to_full_workflow_candidate():
    decision = route_for("crea una tarjeta en Canva para Airbnb")
    assert decision.route == "action_ready"
    assert decision.domain == "workflow"
    assert decision.action == "full_workflow_candidate"


def test_general_post_routes_to_full_workflow_candidate():
    decision = route_for("haz un post del dia del padre")
    assert decision.route == "action_ready"
    assert decision.domain == "workflow"
    assert decision.action == "full_workflow_candidate"
    assert decision.suggested_skills == ["full_workflows"]
    assert decision.suggested_tools == []


def test_instagram_post_routes_to_full_workflow_candidate():
    decision = route_for("crea un post para instagram del dia del padre")
    assert decision.route == "action_ready"
    assert decision.domain == "workflow"
    assert decision.action == "full_workflow_candidate"
    assert decision.suggested_skills == ["full_workflows"]
    assert decision.suggested_tools == []


def test_general_card_routes_to_full_workflow_candidate():
    decision = route_for("diseña una tarjeta del dia de las madres")
    assert decision.route == "action_ready"
    assert decision.domain == "workflow"
    assert decision.action == "full_workflow_candidate"
    assert decision.suggested_skills == ["full_workflows"]
    assert decision.suggested_tools == []


def test_general_flyer_routes_to_full_workflow_candidate():
    decision = route_for("prepara un flyer de oferta")
    assert decision.route == "action_ready"
    assert decision.domain == "workflow"
    assert decision.action == "full_workflow_candidate"
    assert decision.suggested_skills == ["full_workflows"]
    assert decision.suggested_tools == []


def test_general_image_routes_to_full_workflow_candidate():
    decision = route_for("genera una imagen para una promo")
    assert decision.route == "action_ready"
    assert decision.domain == "workflow"
    assert decision.action == "full_workflow_candidate"
    assert decision.suggested_skills == ["full_workflows"]
    assert decision.suggested_tools == []


def test_general_ad_routes_to_full_workflow_candidate():
    decision = route_for("haz un anuncio para Bellamar")
    assert decision.route == "action_ready"
    assert decision.domain == "workflow"
    assert decision.action == "full_workflow_candidate"
    assert decision.suggested_skills == ["full_workflows"]
    assert decision.suggested_tools == []


def test_post_ideas_remain_chat():
    decision = route_for("dame ideas para un post del dia del padre")
    assert decision.domain != "workflow"
    assert decision.action != "full_workflow_candidate"


def test_post_writing_help_remains_chat():
    decision = route_for("qué puedo escribir en un post del dia del padre")
    assert decision.domain != "workflow"
    assert decision.action != "full_workflow_candidate"


def test_caption_correction_remains_chat():
    decision = route_for("corrige este caption")
    assert decision.domain != "workflow"
    assert decision.action != "full_workflow_candidate"


def test_open_canva_is_not_full_workflow():
    decision = route_for("abre Canva")
    assert decision.domain != "workflow"
    assert decision.action != "full_workflow_candidate"


def test_search_canva_is_not_full_workflow():
    decision = route_for("busca Canva")
    assert decision.domain != "workflow"
    assert decision.action != "full_workflow_candidate"


def test_open_local_path_is_refused():
    decision = route_for("abre /Users/inma/test.txt")
    assert decision.route == "refuse"
    assert decision.needs_tool is False


def test_frontmost_question_routes_to_observe_frontmost():
    decision = route_for("qué app está abierta")
    assert decision.route == "action_ready"
    assert decision.suggested_tools == ["macos_observe_frontmost"]


def test_visible_windows_question_routes_to_visible_windows():
    decision = route_for("qué ventanas hay abiertas")
    assert decision.route == "action_ready"
    assert decision.suggested_tools == ["macos_visible_windows"]


def test_visible_windows_available_routes_to_visible_windows():
    decision = route_for("muéstrame las ventanas disponibles")
    assert decision.route == "action_ready"
    assert decision.needs_tool is True
    assert decision.suggested_tools == ["macos_visible_windows"]


def test_permissions_question_routes_to_permissions_check():
    decision = route_for("revisa permisos de mac")
    assert decision.route == "action_ready"
    assert decision.suggested_tools == ["macos_permissions_check"]


def test_list_apps_question_routes_to_list_apps():
    decision = route_for("qué apps puedo abrir")
    assert decision.route == "action_ready"
    assert decision.suggested_tools == ["macos_list_apps"]


def test_observe_screen_does_not_route_to_screenshot():
    decision = route_for("observa mi pantalla")
    assert decision.route == "refuse"
    assert "screenshot" not in decision.suggested_tools


def test_space_next_routes_to_space_next():
    decision = route_for("cambia al siguiente escritorio")
    assert decision.route == "action_ready"
    assert decision.suggested_tools == ["macos_space_next"]


def test_space_previous_routes_to_space_previous():
    decision = route_for("cambia al escritorio anterior")
    assert decision.route == "action_ready"
    assert decision.suggested_tools == ["macos_space_previous"]


def test_mission_control_routes_to_mission_control():
    decision = route_for("abre mission control")
    assert decision.route == "action_ready"
    assert decision.suggested_tools == ["macos_space_mission_control"]


def test_space_switch_number_routes_to_switch_number():
    decision = route_for("cambia al escritorio 2")
    assert decision.route == "action_ready"
    assert decision.risk_level == "low"
    assert decision.suggested_tools == ["macos_space_switch_desktop_number"]


def test_space_switch_number_routes_for_typo_and_correction():
    typo = route_for("cambia a escritori 1")
    correction = route_for("perdón me refiero al escritorio 2")
    assert typo.route == "action_ready"
    assert typo.suggested_tools == ["macos_space_switch_desktop_number"]
    assert correction.route == "action_ready"
    assert correction.suggested_tools == ["macos_space_switch_desktop_number"]


def test_space_status_routes_to_space_status():
    decision = route_for("estado de spaces")
    assert decision.route == "action_ready"
    assert decision.suggested_tools == ["macos_space_status"]


def test_window_right_routes_to_window_native_tiling():
    decision = route_for("pon la ventana a la derecha")
    assert decision.route == "action_ready"
    assert decision.risk_level == "low"
    assert decision.suggested_skills == ["macos_windows"]
    assert decision.suggested_tools == ["window_native_tiling"]


def test_window_center_routes_to_window_native_tiling():
    decision = route_for("centra la ventana")
    assert decision.route == "action_ready"
    assert decision.suggested_tools == ["window_native_tiling"]


def test_window_return_size_routes_to_window_native_tiling():
    decision = route_for("vuelve al tamaño anterior")
    assert decision.route == "action_ready"
    assert decision.suggested_tools == ["window_native_tiling"]


def test_window_generic_request_routes_to_clarification():
    decision = route_for("mueve la ventana")
    assert decision.route == "clarification"
    assert decision.needs_clarification is True
    assert decision.suggested_tools == ["window_native_tiling"]


def test_memory_question_routes_to_memory_lookup():
    decision = route_for("qué hicimos con el problema del JSON")
    assert decision.route == "memory_lookup"


def test_knowledge_base_question_routes_to_rag_lookup():
    decision = route_for("según mis notas sobre JSON")
    assert decision.route == "rag_lookup"
    assert decision.needs_rag is True
    assert decision.needs_tool is False


def test_delete_routes_to_safety_confirmation():
    decision = route_for("borra esos archivos")
    assert decision.route == "safety_confirmation"
