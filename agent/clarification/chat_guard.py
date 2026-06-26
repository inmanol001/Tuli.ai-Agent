from __future__ import annotations

import re

from pydantic import BaseModel, Field

from agent.clarification.context_resolver import ContextResolver
from agent.gateway.message_types import ContextPackage
from agent.gateway.session_manager import SessionState


class ChatGuardResult(BaseModel):
    should_clarify: bool
    reason: str
    missing_info: list[str] = Field(default_factory=list)
    pending_clarification: str | None = None
    resolved_reference: str | None = None
    candidates: list[str] = Field(default_factory=list)
    context_resolution: dict | None = None


class ChatSafetyClarificationGuard:
    def __init__(self) -> None:
        self.context_resolver = ContextResolver()

    _status_question_phrases = (
        "se ejecutó",
        "se ejecuto",
        "se aplicó",
        "se aplico",
        "quedó abierto",
        "quedo abierto",
        "terminó",
        "termino",
        "terminó correctamente",
        "termino correctamente",
        "ya lo hiciste",
        "ya hiciste",
        "ya buscaste",
        "ya abriste",
        "quedó listo",
        "quedo listo",
    )
    _vague_reference_phrases = (
        "eso",
        "esa",
        "ese",
        "esto",
        "este",
        "esta",
        "la otra",
        "el otro",
        "el mismo",
        "la misma",
        "el primero",
        "la primera",
        "segunda opción",
        "segunda opcion",
        "otro nombre",
        "como antes",
        "como la vez pasada",
        "donde nos quedamos",
        "ahorita",
        "mencionado",
        "la que te mencioné",
        "la que te mencione",
        "la que mencioné",
        "la que mencione",
        "la aplicación que usamos",
        "la aplicacion que usamos",
        "la app que usamos",
        "el sitio correcto",
        "la documentación oficial",
        "la documentacion oficial",
        "la documentación",
        "la documentacion",
    )
    _continuation_phrases = (
        "continúa",
        "continua",
        "sigue",
        "repite",
        "repetir",
        "usa eso mismo",
        "usa lo mismo",
        "hazlo como antes",
        "hazlo como la vez pasada",
        "usa el otro nombre",
        "continúa desde donde nos quedamos",
        "continua desde donde nos quedamos",
        "desde donde nos quedamos",
        "despues de eso",
        "después de eso",
    )
    _operational_verbs = (
        "abre",
        "abrir",
        "busca",
        "buscar",
        "búscame",
        "buscame",
        "muestrame",
        "muéstrame",
        "muestra",
        "usa",
        "usar",
        "haz",
        "hacer",
        "hazlo",
        "continua",
        "continúa",
        "sigue",
        "repite",
        "aplica",
        "aplicar",
        "corrige",
        "corregir",
        "revisa",
        "revisar",
        "inspecciona",
        "inspeccionar",
        "prueba",
        "probar",
        "monta",
        "montar",
        "crea",
        "crear",
        "diseña",
        "diseñar",
        "mueve",
        "mover",
        "manda",
        "enviar",
        "envía",
        "guarda",
        "guardar",
        "renombra",
        "exporta",
    )
    _ambiguous_target_phrases = (
        "documentación oficial",
        "documentacion oficial",
        "documentación",
        "documentacion",
        "sitio correcto",
        "aplicación que usamos",
        "aplicacion que usamos",
        "app que usamos",
        "parte que falla",
        "error anterior",
        "la parte que falla",
        "archivo",
        "error",
        "ventana",
        "canva",
        "diseño",
        "diseno",
        "browser",
        "navegador",
    )
    _open_verbs = (
        "abre",
        "abrir",
        "abreme",
        "ábreme",
        "abrela",
        "ábrela",
        "abrelo",
        "ábrelo",
        "muestra",
        "muestrame",
        "muéstrame",
    )
    _search_verbs = ("busca", "buscar", "búscame", "buscame", "investiga", "consulta")
    _design_targets = ("canva", "diseño", "diseno", "plantilla", "post", "flyer", "historia")
    _code_targets = ("código", "codigo", "debug", "error", "archivo", "stack trace", "trace")
    _window_targets = ("ventana", "windows", "window", "escritorio")
    _app_targets = ("app", "aplicación", "aplicacion", "la aplicación que usamos", "la app que usamos")
    _conceptual_phrases = (
        "qué es",
        "que es",
        "explícame",
        "explicame",
        "cuál es la diferencia",
        "cual es la diferencia",
        "por qué",
        "por que",
        "cómo funciona",
        "como funciona",
    )

    def evaluate(
        self,
        context: ContextPackage,
        session: SessionState | None = None,
    ) -> ChatGuardResult:
        if context.router_decision.route != "chat":
            return ChatGuardResult(
                should_clarify=False,
                reason="route_not_chat",
            )

        resolution = self.context_resolver.resolve(context, session)
        text = self._normalized_text(context.user_message)
        if not text:
            return ChatGuardResult(
                should_clarify=False,
                reason="empty_message",
            )

        if self._is_conceptual_question(text):
            return ChatGuardResult(
                should_clarify=False,
                reason="conceptual_question",
                candidates=resolution.candidates,
                resolved_reference=resolution.resolved_reference,
                context_resolution=resolution.model_dump(mode="json"),
            )

        if resolution.has_status_question:
            if resolution.recent_tool_result is not None:
                return ChatGuardResult(
                    should_clarify=False,
                    reason="recent_tool_result_available",
                    candidates=resolution.candidates,
                    resolved_reference=resolution.resolved_reference,
                    context_resolution=resolution.model_dump(mode="json"),
                )
            return self._result(
                reason=resolution.reason,
                missing_info=["tool_result"],
                pending_clarification="tool_result",
                candidates=resolution.candidates,
                resolved_reference=resolution.resolved_reference,
                context_resolution=resolution.model_dump(mode="json"),
            )

        if resolution.reason == "explicit_platform_missing_content":
            return ChatGuardResult(
                should_clarify=True,
                reason="explicit_platform_missing_content",
                missing_info=["target_content"],
                pending_clarification="target_content",
                candidates=resolution.candidates,
                resolved_reference=None,
                context_resolution=resolution.model_dump(mode="json"),
            )

        if (
            resolution.has_vague_reference
            and resolution.confidence == "high"
            and resolution.resolved_reference
        ):
            if self._has_operational_intent(text):
                return ChatGuardResult(
                    should_clarify=True,
                    reason="resolved_reference_confirmation",
                    missing_info=["resolved_reference_confirmation"],
                    pending_clarification="resolved_reference_confirmation",
                    candidates=resolution.candidates,
                    resolved_reference=resolution.resolved_reference,
                    context_resolution=resolution.model_dump(mode="json"),
                )
            return ChatGuardResult(
                should_clarify=False,
                reason="resolved_vague_reference_from_history",
                candidates=resolution.candidates,
                resolved_reference=resolution.resolved_reference,
                context_resolution=resolution.model_dump(mode="json"),
            )

        if resolution.has_vague_reference and resolution.confidence == "ambiguous":
            return ChatGuardResult(
                should_clarify=True,
                reason="ambiguous_reference",
                missing_info=["ambiguous_reference"],
                pending_clarification="ambiguous_reference",
                candidates=resolution.candidates,
                resolved_reference=None,
                context_resolution=resolution.model_dump(mode="json"),
            )

        vague_reference = resolution.has_vague_reference or self._has_any(text, self._vague_reference_phrases)
        continuation_reference = self._has_any(text, self._continuation_phrases)
        operational_verb = self._has_any(text, self._operational_verbs)
        ambiguous_target = self._has_any(text, self._ambiguous_target_phrases)
        documentation_target = self._has_any(
            text,
            (
                "documentación oficial",
                "documentacion oficial",
                "documentación",
                "documentacion",
            ),
        )
        design_target = self._has_any(text, self._design_targets)
        code_target = self._has_any(text, self._code_targets)
        window_target = self._has_any(text, self._window_targets)
        app_target = self._has_any(text, self._app_targets)
        open_target = self._has_any(text, self._open_verbs)
        search_target = self._has_any(text, self._search_verbs)

        if operational_verb and vague_reference:
            result = self._clarify_operational(text, session, reason="generic_operational_ambiguity")
            return self._enrich_result(result, resolution)

        if continuation_reference and (operational_verb or vague_reference):
            return self._enrich_result(self._result(
                reason="continuation_reference",
                missing_info=["previous_context"],
                pending_clarification="previous_context",
            ), resolution)

        if ambiguous_target and (operational_verb or vague_reference):
            if documentation_target:
                return self._enrich_result(self._result(
                    reason="generic_operational_ambiguity",
                    missing_info=["target_workflow_or_platform"],
                    pending_clarification="target_workflow_or_platform",
                ), resolution)
            if code_target or "parte que falla" in text or "error anterior" in text:
                return self._enrich_result(self._result(
                    reason="generic_operational_ambiguity",
                    missing_info=["target_file_or_error"],
                    pending_clarification="target_file_or_error",
                ), resolution)
            if app_target:
                return self._enrich_result(self._result(
                    reason="generic_operational_ambiguity",
                    missing_info=["target_app"],
                    pending_clarification="target_app",
                ), resolution)
            if design_target:
                return self._enrich_result(self._result(
                    reason="generic_operational_ambiguity",
                    missing_info=["target_workflow_or_platform"],
                    pending_clarification="target_workflow_or_platform",
                ), resolution)
            if window_target:
                return self._enrich_result(self._result(
                    reason="generic_operational_ambiguity",
                    missing_info=["window_action"],
                    pending_clarification="window_action",
                ), resolution)
            if open_target:
                return self._enrich_result(self._result(
                    reason="generic_operational_ambiguity",
                    missing_info=["target_url"],
                    pending_clarification="target_url",
                ), resolution)
            if search_target:
                return self._enrich_result(self._result(
                    reason="generic_operational_ambiguity",
                    missing_info=["search_query"],
                    pending_clarification="search_query",
                ), resolution)
            return self._enrich_result(self._result(
                reason="generic_operational_ambiguity",
                missing_info=["missing_details"],
                pending_clarification="missing_details",
            ), resolution)

        if design_target and vague_reference:
            return self._enrich_result(self._result(
                reason="generic_operational_ambiguity",
                missing_info=["target_workflow_or_platform"],
                pending_clarification="target_workflow_or_platform",
            ), resolution)

        if code_target and vague_reference:
            return self._enrich_result(self._result(
                reason="generic_operational_ambiguity",
                missing_info=["target_file_or_error"],
                pending_clarification="target_file_or_error",
            ), resolution)

        if window_target and vague_reference:
            return self._enrich_result(self._result(
                reason="generic_operational_ambiguity",
                missing_info=["window_action"],
                pending_clarification="window_action",
            ), resolution)

        if app_target and vague_reference:
            return self._enrich_result(self._result(
                reason="generic_operational_ambiguity",
                missing_info=["target_app"],
                pending_clarification="target_app",
            ), resolution)

        if vague_reference and (open_target or search_target):
            pending = "target_url" if open_target else "search_query"
            return self._enrich_result(self._result(
                reason="generic_operational_ambiguity",
                missing_info=[pending],
                pending_clarification=pending,
            ), resolution)

        if vague_reference and not self._looks_like_chat(text):
            return self._enrich_result(self._result(
                reason="generic_operational_ambiguity",
                missing_info=["missing_details"],
                pending_clarification="missing_details",
            ), resolution)

        return ChatGuardResult(
            should_clarify=False,
            reason="safe_chat",
            candidates=resolution.candidates,
            resolved_reference=resolution.resolved_reference,
            context_resolution=resolution.model_dump(mode="json"),
        )

    def _clarify_operational(
        self,
        text: str,
        session: SessionState | None,
        *,
        reason: str,
    ) -> ChatGuardResult:
        if self._has_any(text, self._search_verbs):
            return self._result(
                reason=reason,
                missing_info=["search_query"],
                pending_clarification="search_query",
            )
        if "parte que falla" in text or "la parte que falla" in text or "error anterior" in text:
            return self._result(
                reason=reason,
                missing_info=["target_file_or_error"],
                pending_clarification="target_file_or_error",
            )
        if self._has_any(text, self._open_verbs):
            if self._has_any(text, self._app_targets):
                return self._result(
                    reason=reason,
                    missing_info=["target_app"],
                    pending_clarification="target_app",
                )
            return self._result(
                reason=reason,
                missing_info=["target_url"],
                pending_clarification="target_url",
            )
        if self._has_any(text, self._design_targets):
            return self._result(
                reason=reason,
                missing_info=["target_workflow_or_platform"],
                pending_clarification="target_workflow_or_platform",
            )
        if self._has_any(text, self._code_targets):
            return self._result(
                reason=reason,
                missing_info=["target_file_or_error"],
                pending_clarification="target_file_or_error",
            )
        if self._has_any(text, self._window_targets):
            return self._result(
                reason=reason,
                missing_info=["window_action"],
                pending_clarification="window_action",
            )
        if self._has_any(text, self._continuation_phrases):
            return self._result(
                reason="continuation_reference",
                missing_info=["previous_context"],
                pending_clarification="previous_context",
            )
        return self._result(
            reason=reason,
            missing_info=["missing_details"],
            pending_clarification="missing_details",
        )

    def _result(
        self,
        *,
        reason: str,
        missing_info: list[str],
        pending_clarification: str,
        candidates: list[str] | None = None,
        resolved_reference: str | None = None,
        context_resolution: dict | None = None,
    ) -> ChatGuardResult:
        return ChatGuardResult(
            should_clarify=True,
            reason=reason,
            missing_info=missing_info,
            pending_clarification=pending_clarification,
            candidates=candidates or [],
            resolved_reference=resolved_reference,
            context_resolution=context_resolution,
        )

    def _looks_like_chat(self, text: str) -> bool:
        return bool(re.search(r"\b(hola|gracias|buenas|sí|si|no|claro|ok|vale)\b", text))

    def _is_conceptual_question(self, text: str) -> bool:
        return self._has_any(text, self._conceptual_phrases)

    def _has_operational_intent(self, text: str) -> bool:
        return (
            self._has_any(text, self._operational_verbs)
            or self._has_any(text, self._open_verbs)
            or self._has_any(text, self._search_verbs)
            or self._has_any(text, self._continuation_phrases)
            or self._has_any(text, self._design_targets)
            or self._has_any(text, self._code_targets)
            or self._has_any(text, self._window_targets)
            or self._has_any(text, self._app_targets)
        )

    def _has_any(self, text: str, phrases: tuple[str, ...]) -> bool:
        return any(
            re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text)
            for phrase in phrases
        )

    def _normalized_text(self, text: str) -> str:
        return " ".join((text or "").strip().lower().split())

    def _enrich_result(
        self,
        result: ChatGuardResult,
        resolution,
    ) -> ChatGuardResult:
        if result.candidates or result.resolved_reference or result.context_resolution:
            return result
        return result.model_copy(
            update={
                "candidates": resolution.candidates,
                "resolved_reference": resolution.resolved_reference,
                "context_resolution": resolution.model_dump(mode="json"),
            }
        )
