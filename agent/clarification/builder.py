from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from agent.clarification.context_resolver import ContextResolver
from agent.gateway.message_types import ContextPackage


KNOWN_SITE_HINTS = (
    "github",
    "ollama",
    "canva",
    "openai",
    "youtube",
    "google",
)


class ClarificationResult(BaseModel):
    text: str
    pending_clarification: str
    reason: str
    missing_info: list[str] = Field(default_factory=list)
    options: list[str] = Field(default_factory=list)
    expects_free_text: bool = False
    allow_numbered_options: bool = True
    guidance: str = ""
    source: str = "clarification_builder"


@dataclass(slots=True)
class ClarificationSpec:
    question: str
    options: list[str]
    pending_clarification: str
    reason: str
    missing_info: list[str]
    expects_free_text: bool = False
    allow_numbered_options: bool = True
    guidance: str = ""


class ClarificationBuilder:
    def __init__(self) -> None:
        self.context_resolver = ContextResolver()

    _missing_info_questions: dict[str, tuple[str, list[str], str]] = {
        "artist_or_genre": (
            "Necesito saber el artista, canción o género.",
            [
                "Usar el artista o canción exactos.",
                "Buscar por género musical.",
                "Cancelar esta acción.",
            ],
            "artist_or_genre",
        ),
        "search_query": (
            "¿Qué quieres que busque exactamente?",
            [
                "Escribirme el tema exacto.",
                "Buscar una página o documentación específica.",
                "Cancelar esta búsqueda.",
            ],
            "search_query",
        ),
        "window_action": (
            "Necesito saber qué acción quieres hacer con la ventana.",
            [
                "Moverla a la izquierda.",
                "Moverla a la derecha.",
                "Centrarla.",
                "Cancelar esta acción.",
            ],
            "window_action",
        ),
        "ambiguous_reference": (
            "Cuando dices eso, veo varias opciones recientes. ¿A cuál te refieres?",
            [
                "Otra cosa.",
                "Cancelar esta acción.",
            ],
            "ambiguous_reference",
        ),
        "resolved_reference_confirmation": (
            "Entiendo que te refieres a eso. ¿Quieres continuar con esa referencia?",
            [
                "Sí.",
                "No, me refiero a otra cosa.",
                "Cancelar.",
            ],
            "resolved_reference_confirmation",
        ),
        "target_app": (
            "¿Qué app quieres abrir?",
            [
                "Escribirme el nombre exacto de la app.",
                "Listar apps disponibles.",
                "Cancelar esta acción.",
            ],
            "target_app",
        ),
        "target_url": (
            "¿Qué página o sitio quieres abrir?",
            [
                "Escribirme la URL o nombre exacto.",
                "Buscar el sitio por nombre.",
                "Cancelar esta acción.",
            ],
            "target_url",
        ),
        "tool_result": (
            "No puedo confirmarlo sin un resultado reciente de una herramienta.",
            [
                "Revisar el último resultado de herramienta.",
                "Repetir la acción ahora.",
                "Continuar sin comprobarlo.",
            ],
            "tool_result",
        ),
        "previous_context": (
            "Necesito saber a qué contexto anterior te refieres.",
            [
                "Usar la última tarea mencionada.",
                "Escribirme el contexto exacto.",
                "Cancelar esta acción.",
            ],
            "previous_context",
        ),
        "target_file_or_error": (
            "Necesito saber qué archivo, error o parte concreta quieres revisar.",
            [
                "Usar el último error mencionado.",
                "Escribirme el archivo o error exacto.",
                "Cancelar esta acción.",
            ],
            "target_file_or_error",
        ),
        "target_workflow_or_platform": (
            "Necesito concretar el diseño antes de seguir. ¿Qué quieres crear y dónde quieres hacerlo?",
            [
                "Post para redes.",
                "Flyer, tarjeta o anuncio.",
                "Diseño en Canva u otra plataforma.",
            ],
            "target_workflow_or_platform",
        ),
        "target_content": (
            "¿Qué contenido quieres usar?",
            [
                "Pegar o escribir el contenido exacto.",
                "Describir la idea que quieres usar.",
                "Cancelar esta acción.",
            ],
            "target_content",
        ),
        "missing_details": (
            "Necesito un dato concreto antes de seguir.",
            [
                "Escribirme la acción exacta.",
                "Dar más contexto.",
                "Cancelar esta acción.",
            ],
            "missing_details",
        ),
        "topic": (
            "Necesito saber el tema.",
            [
                "Usar el último tema mencionado.",
                "Escribirme el tema exacto.",
                "Cancelar esta acción.",
            ],
            "topic",
        ),
        "format": (
            "Necesito saber el formato.",
            [
                "Post cuadrado.",
                "Historia.",
                "Flyer.",
                "Otro formato.",
            ],
            "format",
        ),
        "style": (
            "Necesito saber el estilo.",
            [
                "Elegante.",
                "Promocional.",
                "Playero.",
                "Otro estilo.",
            ],
            "style",
        ),
        "platform": (
            "Necesito saber la plataforma.",
            [
                "Canva.",
                "Redes sociales.",
                "Otra plataforma.",
            ],
            "platform",
        ),
    }

    def build(
        self,
        context: ContextPackage,
        *,
        missing_info_override: list[str] | None = None,
        reason_hint: str | None = None,
    ) -> ClarificationResult:
        resolution = self.context_resolver.resolve(context)
        missing_info = self._normalize_missing_info(
            missing_info_override if missing_info_override is not None else context.router_decision.missing_info
        )
        inferred_reason = reason_hint or self._infer_reason(context, missing_info)

        forced = self._forced_spec_for_pending(context, missing_info, inferred_reason)
        if forced is not None:
            text = self._format_text(forced.question, forced.options)
            return ClarificationResult(
                text=text,
                pending_clarification=forced.pending_clarification,
                reason=forced.reason,
                missing_info=forced.missing_info,
                options=forced.options,
                expects_free_text=forced.expects_free_text,
                allow_numbered_options=forced.allow_numbered_options,
                guidance=forced.guidance,
            )

        spec = self._select_spec(context, missing_info, inferred_reason, resolution)
        spec = self._clean_spec_for_pending(spec)
        text = self._format_text(spec.question, spec.options)
        return ClarificationResult(
            text=text,
            pending_clarification=spec.pending_clarification,
            reason=spec.reason,
            missing_info=spec.missing_info,
            options=spec.options,
            expects_free_text=spec.expects_free_text,
            allow_numbered_options=spec.allow_numbered_options,
            guidance=spec.guidance,
        )

    def _pending_from_current_signal(
        self,
        context: ContextPackage,
        missing_info: list[str],
        inferred_reason: str | None,
    ) -> str | None:
        joined_missing = " ".join(missing_info or []).lower()
        reason = (inferred_reason or "").lower()
        decision = context.router_decision
        action = (getattr(decision, "action", "") or "").lower()
        domain = (getattr(decision, "domain", "") or "").lower()
        tools = set(getattr(decision, "suggested_tools", []) or [])

        signal = " ".join([joined_missing, reason, action, domain, " ".join(tools)])

        if "window_action" in signal or "window_native_tiling" in signal or "window" in signal:
            return "window_action"

        if "target_app" in signal or ("open_app" in tools and "browser_search" not in tools):
            return "target_app"

        if "search_query" in signal or "web_search" in tools:
            return "search_query"

        if (
            "target_url" in signal
            or "browser_search" in tools
            or action in {"browser_search", "open_url", "open_page"}
            or domain == "browser"
        ):
            return "target_url"

        if (
            "target_workflow_or_platform" in signal
            or "workflow" in signal
            or "canva" in signal
            or "design" in signal
            or "diseño" in signal
        ):
            return "target_workflow_or_platform"

        if "target" in joined_missing:
            if "open_app" in tools and "browser_search" not in tools:
                return "target_app"
            if "web_search" in tools:
                return "search_query"
            if "browser_search" in tools or domain == "browser":
                return "target_url"

        # Rescue semántico: algunos guards llegan con missing_details,
        # pero la señal actual dice claramente web/search/window.
        user_text = (context.user_message or "").lower()
        if any(x in user_text for x in ("llévame", "llevame", "ese sitio", "esa página", "esa pagina", "ese website")):
            return "target_url"

        if any(x in user_text for x in ("investiga eso", "consulta eso", "averigua eso", "busca eso")):
            return "search_query"

        if any(x in user_text for x in ("mueve la ventana", "acomoda la ventana", "coloca la ventana")):
            return "window_action"

        return None

    def _free_text_spec(
        self,
        context: ContextPackage,
        pending: str,
        missing_info: list[str],
        reason: str,
    ) -> ClarificationSpec:
        return ClarificationSpec(
            question=self._natural_free_text_question(context, pending),
            options=[],
            pending_clarification=pending,
            reason=reason or pending,
            missing_info=missing_info or [pending],
            expects_free_text=True,
            allow_numbered_options=False,
            guidance=self._clarification_guidance(pending),
        )

    def _natural_free_text_question(self, context: ContextPackage, pending: str) -> str:
        # No es una plantilla única. Son variantes breves guiadas por el slot faltante
        # para que no se sienta como formulario rígido.
        seed = (len(context.recent_history) + len(context.user_message or "") + len(pending)) % 3

        variants = {
            "target_url": [
                "¿A qué página quieres que te lleve? Puedes decirme el nombre del sitio o pegar la URL.",
                "Dime el sitio o la URL que quieres abrir.",
                "Claro, ¿qué página quieres abrir?",
            ],
            "search_query": [
                "¿Qué tema quieres que investigue exactamente?",
                "Dime qué quieres que busque y lo reviso.",
                "¿Sobre qué quieres que haga la búsqueda?",
            ],
            "target_app": [
                "¿Cuál aplicación quieres que abra?",
                "Dime el nombre de la app y la abro.",
                "Claro, ¿qué app quieres usar?",
            ],
            "target_workflow_or_platform": [
                "Dime un poco más: ¿qué quieres crear y dónde lo quieres trabajar?",
                "Perfecto, cuéntame qué tipo de diseño necesitas y para qué plataforma.",
                "¿Qué pieza quieres crear? Puedes decirme si es post, flyer, historia, presentación u otra cosa.",
            ],
            "target_content": [
                "¿Qué contenido quieres usar?",
                "Pásame el texto, idea o contenido que quieres trabajar.",
                "Dime qué contenido debo tomar como base.",
            ],
            "missing_details": [
                "Dame un poco más de detalle para hacerlo bien.",
                "Necesito un dato más concreto para continuar.",
                "Aclárame qué quieres que haga exactamente.",
            ],
        }

        choices = variants.get(pending) or variants["missing_details"]
        return choices[seed]

    def _clarification_guidance(self, pending: str) -> str:
        guidance = {
            "target_url": "Ask naturally for the site name or URL. Do not show fake numbered options. Expect free text.",
            "search_query": "Ask naturally for the exact search topic. Do not show fake numbered options. Expect free text.",
            "target_app": "Ask naturally which app to open. Do not show fake numbered options. Expect free text.",
            "target_workflow_or_platform": "Ask naturally for the design/workflow details. Avoid rigid menu unless there are real candidates.",
            "target_content": "Ask naturally for the content to use. Expect free text.",
            "missing_details": "Ask naturally for the missing concrete detail. Expect free text.",
        }
        return guidance.get(pending, "Ask a brief natural clarification question.")

    def _forced_spec_for_pending(
        self,
        context: ContextPackage,
        missing_info: list[str],
        inferred_reason: str,
    ):
        pending = self._pending_from_current_signal(context, missing_info, inferred_reason)
        if pending is None:
            pending = self._pending_hint(context)

        if pending == "window_action":
            return ClarificationSpec(
                question="Necesito saber qué acción quieres hacer con la ventana.",
                options=[
                    "Moverla a la izquierda.",
                    "Moverla a la derecha.",
                    "Centrarla.",
                    "Cancelar esta acción.",
                ],
                pending_clarification="window_action",
                reason=inferred_reason or "window_action",
                missing_info=missing_info or ["window_action"],
            )

        if pending == "target_url":
            return self._free_text_spec(context, "target_url", missing_info, inferred_reason or "target_url")

        if pending == "target_app":
            return self._free_text_spec(context, "target_app", missing_info, inferred_reason or "target_app")

        if pending == "target_workflow_or_platform":
            return self._free_text_spec(context, "target_workflow_or_platform", missing_info, inferred_reason or "target_workflow_or_platform")

        return None

    def _clean_spec_for_pending(self, spec: ClarificationSpec) -> ClarificationSpec:
        pending = spec.pending_clarification

        if pending == "window_action":
            return ClarificationSpec(
                question="Necesito saber qué acción quieres hacer con la ventana.",
                options=[
                    "Moverla a la izquierda.",
                    "Moverla a la derecha.",
                    "Centrarla.",
                    "Cancelar esta acción.",
                ],
                pending_clarification="window_action",
                reason=spec.reason,
                missing_info=spec.missing_info,
            )

        if pending == "target_workflow_or_platform":
            return ClarificationSpec(
                question="Cuéntame qué tipo de diseño necesitas y para qué plataforma.",
                options=[],
                pending_clarification="target_workflow_or_platform",
                reason=spec.reason,
                missing_info=spec.missing_info,
                expects_free_text=True,
                allow_numbered_options=False,
                guidance=self._clarification_guidance("target_workflow_or_platform"),
            )

        if pending == "target_app":
            return ClarificationSpec(
                question="¿Cuál aplicación quieres que abra?",
                options=[],
                pending_clarification="target_app",
                reason=spec.reason,
                missing_info=spec.missing_info,
                expects_free_text=True,
                allow_numbered_options=False,
                guidance=self._clarification_guidance("target_app"),
            )

        return spec

    def _select_spec(
        self,
        context: ContextPackage,
        missing_info: list[str],
        reason: str,
        resolution,
    ) -> ClarificationSpec:
        if missing_info:
            return self._from_missing_info(context, missing_info, reason, resolution)

        inferred = self._infer_from_user_text(context)
        if inferred is not None:
            return inferred

        pending = self._pending_hint(context) or "missing_details"
        topic = self._extract_topic_from_text_or_history(context)
        if topic:
            question = f"Necesito confirmar si te refieres a {topic} antes de seguir."
            options = [
                f"Sí, usar {topic}.",
                "No, me refiero a otra cosa.",
                "Cancelar esta acción.",
            ]
        else:
            question = "Necesito un dato concreto antes de seguir. ¿Qué quieres que haga exactamente?"
            options = [
                "Escribirme la acción exacta.",
                "Dar más contexto.",
                "Cancelar esta acción.",
            ]
        return ClarificationSpec(
            question=question,
            options=options,
            pending_clarification=pending,
            reason=reason or "clarification",
            missing_info=[],
        )

    def _from_missing_info(
        self,
        context: ContextPackage,
        missing_info: list[str],
        reason: str,
        resolution,
    ) -> ClarificationSpec:
        normalized = set(missing_info)
        pending = self._pending_hint(context) or missing_info[0]

        if "resolved_reference_confirmation" in normalized:
            reference = resolution.resolved_reference or (
                resolution.candidates[0] if resolution.candidates else None
            )
            if reference:
                action = self._action_label_from_user_message(context.user_message)
                if action == "open":
                    question = f"Entiendo que te refieres a {reference}. ¿Quieres que lo abra?"
                    options = [
                        f"Sí, abrir {reference}.",
                        "No, me refiero a otra cosa.",
                        "Cancelar esta acción.",
                    ]
                elif action == "search":
                    question = f"Entiendo que te refieres a {reference}. ¿Quieres que busque eso?"
                    options = [
                        f"Sí, buscar {reference}.",
                        "No, me refiero a otra cosa.",
                        "Cancelar esta búsqueda.",
                    ]
                elif action == "use":
                    question = f"Entiendo que te refieres a {reference}. ¿Quieres usar eso?"
                    options = [
                        f"Sí, usar {reference}.",
                        "No, me refiero a otra cosa.",
                        "Cancelar esta acción.",
                    ]
                else:
                    question = f"Entiendo que te refieres a {reference}. ¿Quieres continuar con eso?"
                    options = [
                        f"Sí, usar {reference}.",
                        "No, me refiero a otra cosa.",
                        "Cancelar esta acción.",
                    ]
                return ClarificationSpec(
                    question=question,
                    options=options,
                    pending_clarification="resolved_reference_confirmation",
                    reason=reason or "resolved_reference_confirmation",
                    missing_info=missing_info,
                )
            return ClarificationSpec(
                question="Necesito más detalles para continuar.",
                options=[
                    "Dar más contexto concreto.",
                    "Escribirme el detalle exacto.",
                    "Cancelar esta acción.",
                ],
                pending_clarification="missing_details",
                reason=reason or "missing_details",
                missing_info=["missing_details"],
            )

        if "target_content" in normalized:
            platform = self._platform_from_current_message(context)
            if platform:
                question = f"Necesito saber qué contenido quieres usar en {platform}."
            else:
                question = "Necesito saber qué contenido quieres usar."
            candidates = self._recent_candidates(context, resolution)
            if candidates:
                options = self._candidate_options("target_content", candidates)
            else:
                options = [
                    "Usar el último contenido mencionado.",
                    "Escribirme el contenido exacto.",
                    "Cancelar esta acción.",
                ]
            return ClarificationSpec(
                question=question,
                options=options,
                pending_clarification="target_content",
                reason=reason or "target_content",
                missing_info=missing_info,
            )

        if "ambiguous_reference" in normalized:
            candidates = resolution.candidates or self._recent_candidates(context)
            if not candidates:
                return ClarificationSpec(
                    question="Necesito más detalles para continuar.",
                    options=[
                        "Dar más contexto concreto.",
                        "Escribirme el detalle exacto.",
                        "Cancelar esta acción.",
                    ],
                    pending_clarification="missing_details",
                    reason=reason or "missing_details",
                    missing_info=["missing_details"],
                )
            options = self._candidate_options("ambiguous_reference", candidates)
            return ClarificationSpec(
                question="Cuando dices eso, veo varias opciones recientes. ¿A cuál te refieres?",
                options=options,
                pending_clarification="ambiguous_reference",
                reason=reason or "ambiguous_reference",
                missing_info=missing_info,
            )

        if normalized & {"format", "style", "platform"}:
            topic = self._topic_from_context(context)
            prefix = f"Perfecto. Para hacerlo bien{f' sobre {topic}' if topic else ''}: "
            parts = []
            if "format" in normalized:
                parts.append("¿lo quieres como post cuadrado, historia o flyer?")
            if "style" in normalized:
                parts.append("¿prefieres estilo elegante, playero o promocional?")
            if "platform" in normalized:
                parts.append("¿en qué plataforma lo vas a usar?")
            question = prefix + " ".join(parts)
            options = [
                "Post cuadrado.",
                "Historia.",
                "Flyer.",
                "Otro formato.",
            ]
            return ClarificationSpec(
                question=question,
                options=options,
                pending_clarification=pending,
                reason=reason or "missing_info",
                missing_info=missing_info,
            )

        for key in (
            "tool_result",
            "previous_context",
            "target_file_or_error",
            "target_workflow_or_platform",
            "missing_details",
            "search_query",
            "window_action",
            "ambiguous_reference",
            "resolved_reference_confirmation",
            "target_content",
            "target_app",
            "target_url",
            "topic",
            "artist_or_genre",
        ):
            if key in normalized:
                question, options, pending_key = self._missing_info_questions[key]
                candidates = self._recent_candidates(context, resolution)
                free_text_keys = {
                    "target_url",
                    "target_app",
                    "target_workflow_or_platform",
                    "search_query",
                    "target_content",
                    "missing_details",
                }
                if key in free_text_keys:
                    return self._free_text_spec(context, key, missing_info, reason or "missing_info")

                if candidates and key in {
                    "previous_context",
                    "topic",
                    "target_file_or_error",
                    "window_action",
                }:
                    options = self._candidate_options(key, candidates)

                return ClarificationSpec(
                    question=question,
                    options=options,
                    pending_clarification=pending or pending_key,
                    reason=reason or "missing_info",
                    missing_info=missing_info,
                )

        question = "Necesito aclarar un dato antes de seguir."
        options = [
            "Dar más contexto concreto.",
            "Escribirme el dato exacto.",
            "Cancelar esta acción.",
        ]
        return ClarificationSpec(
            question=question,
            options=options,
            pending_clarification=pending,
            reason=reason or "missing_info",
            missing_info=missing_info,
        )

    def _infer_from_user_text(self, context: ContextPackage) -> ClarificationSpec | None:
        text = self._normalized_text(context.user_message)

        if any(phrase in text for phrase in ("ya abriste", "ya hiciste", "ya buscaste")):
            topic = self._extract_topic_from_text_or_history(context) or "la acción anterior"
            question = (
                f"No puedo confirmarlo porque no tengo un `tool_result` reciente de {topic} en esta sesión."
            )
            return ClarificationSpec(
                question=question,
                options=[
                    f"Abrir {topic} ahora.",
                    "Revisar el último resultado de herramienta.",
                    "Seguir con otra cosa.",
                ],
                pending_clarification="unclear_confirmation_status",
                reason="unclear_confirmation_status",
                missing_info=[],
            )

        if any(phrase in text for phrase in ("abre eso", "abrir eso", "abre esa", "abre este", "abre lo")):
            return ClarificationSpec(
                question='Necesito saber qué quieres abrir con “eso”.',
                options=[
                    "Abrir el último sitio o tema mencionado.",
                    "Escribirme el nombre de la app o página.",
                    "Cancelar esta acción.",
                ],
                pending_clarification="unclear_open_target",
                reason="unclear_open_target",
                missing_info=[],
            )

        if any(phrase in text for phrase in ("búscame eso", "buscame eso", "busca eso", "buscar eso")):
            return ClarificationSpec(
                question='Necesito saber qué tema quieres que busque con “eso”.',
                options=[
                    "Escribirme el tema exacto.",
                    "Buscar sobre ToolPlanner.",
                    "Escribirme el tema exacto.",
                ],
                pending_clarification="unclear_search_query",
                reason="unclear_search_query",
                missing_info=[],
            )

        if any(phrase in text for phrase in ("hazlo como la vez pasada", "como la vez pasada", "como antes")):
            return ClarificationSpec(
                question="Necesito saber a qué acción anterior te refieres.",
                options=[
                    "Repetir la última acción ejecutada si existe.",
                    "Usar el último tema de conversación.",
                    "Decirme exactamente qué quieres repetir.",
                ],
                pending_clarification="unclear_previous_action",
                reason="unclear_previous_action",
                missing_info=[],
            )

        if "muéstrame el primero" in text or "muestrame el primero" in text or "la primera" in text or "el primero" in text:
            return ClarificationSpec(
                question="No tengo una lista reciente suficientemente clara para saber cuál es “el primero”.",
                options=[
                    "Pegar la lista otra vez.",
                    "Usar el último resultado de búsqueda si existe.",
                    "Decirme cuál quieres abrir.",
                ],
                pending_clarification="unclear_list_item",
                reason="unclear_list_item",
                missing_info=[],
            )

        if "haz un diseño" in text or "haz diseño" in text or "crear un diseño" in text:
            return ClarificationSpec(
                question="Necesito definir el tipo de diseño antes de seguir.",
                options=[
                    "Post para redes.",
                    "Tarjeta o anuncio.",
                    "Diseño para Canva.",
                    "Otro formato.",
                ],
                pending_clarification="unclear_design_format",
                reason="unclear_design_format",
                missing_info=[],
            )

        if (
            "pon eso en canva" in text
            or "poner eso en canva" in text
            or ("canva" in text and "eso" in text)
        ):
            return ClarificationSpec(
                question="Necesito saber qué contenido quieres poner en Canva.",
                options=[
                    "Usar el último texto o idea mencionada.",
                    "Crear un diseño nuevo en Canva.",
                    "Decirme exactamente qué contenido usar.",
                ],
                pending_clarification="unclear_canva_content",
                reason="unclear_canva_content",
                missing_info=[],
            )

        return None

    def _infer_reason(self, context: ContextPackage, missing_info: list[str]) -> str:
        if missing_info:
            return "missing_info"
        inferred = self._infer_from_user_text(context)
        if inferred is not None:
            return inferred.reason
        if self._pending_hint(context):
            return "pending_clarification"
        return "clarification"

    def _topic_from_context(self, context: ContextPackage) -> str | None:
        topic = self._extract_topic_from_text_or_history(context)
        if topic:
            return topic
        if context.router_decision.domain and context.router_decision.domain != "general":
            return context.router_decision.domain
        return None

    def _extract_topic_from_text_or_history(self, context: ContextPackage) -> str | None:
        for source in (
            context.user_message,
            *(turn.content for turn in reversed(context.recent_history)),
        ):
            topic = self._extract_topic_from_text(source)
            if topic:
                return topic
        return None

    def _extract_topic_from_text(self, text: str) -> str | None:
        normalized = self._normalized_text(text)
        for hint in KNOWN_SITE_HINTS:
            if hint in normalized:
                return hint.capitalize() if hint != "github" else "GitHub"
        domain = re.search(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", normalized)
        if domain:
            return domain.group(0)
        if "toolplanner" in normalized:
            return "ToolPlanner"
        if "canva" in normalized:
            return "Canva"
        if "ventana" in normalized:
            return "la ventana"
        return None

    def _pending_hint(self, context: ContextPackage) -> str | None:
        pending = context.session_state.get("pending_clarification")
        if isinstance(pending, str) and pending.strip():
            return pending.strip()
        return None

    def _normalize_missing_info(self, missing_info: list[str] | Any) -> list[str]:
        if not missing_info:
            return []
        if isinstance(missing_info, str):
            items = [missing_info]
        else:
            items = list(missing_info)
        normalized: list[str] = []
        for item in items:
            if not isinstance(item, str):
                continue
            cleaned = item.strip()
            if cleaned and cleaned not in normalized:
                normalized.append(cleaned)
        return normalized

    def _format_text(self, question: str, options: list[str]) -> str:
        if not options:
            return question.strip()
        lines = [question, "", "Opciones:"]
        for index, option in enumerate(options, start=1):
            lines.append(f"{index}. {option}")
        return "\n".join(lines)

    def _normalized_text(self, text: str) -> str:
        return " ".join((text or "").strip().lower().split())

    def _recent_candidates(self, context: ContextPackage, resolution=None) -> list[str]:
        if resolution is not None and getattr(resolution, "candidates", None):
            return list(resolution.candidates)
        return self.context_resolver.resolve(context).candidates

    def _candidate_options(self, key: str, candidates: list[str]) -> list[str]:
        clean_candidates: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if not candidate:
                continue
            cleaned = str(candidate).strip().rstrip(".")
            if not cleaned:
                continue
            dedupe_key = cleaned.lower()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            clean_candidates.append(cleaned)

        if not clean_candidates:
            return []

        limited = clean_candidates[:3]

        if key in {"target_app", "target_url"}:
            options = [f"Abrir {candidate}." for candidate in limited]
            options.append("Otro destino.")
            return options

        if key in {"search_query", "topic"}:
            options = [f"Buscar {candidate}." for candidate in limited]
            options.append("Otro tema.")
            return options

        if key in {
            "target_workflow_or_platform",
            "previous_context",
            "missing_details",
            "resolved_reference_confirmation",
            "target_content",
        }:
            options = [f"Usar {candidate}." for candidate in limited]
            options.append("Otra cosa.")
            return options

        if key == "ambiguous_reference":
            options = [f"{candidate}." for candidate in limited]
            options.append("Otra cosa.")
            return options

        if key == "target_file_or_error":
            options = [f"Revisar {candidate}." for candidate in limited]
            options.append("Otro archivo o error.")
            return options

        if key == "window_action":
            options = [f"Usar {candidate}." for candidate in limited]
            options.append("Otra ventana o acción.")
            return options

        options = [f"Usar {candidate}." for candidate in limited]
        options.append("Otra cosa.")
        return options

    def _action_label_from_user_message(self, user_message: str) -> str:
        text = self._normalized_text(user_message)
        if any(token in text for token in ("abre", "abrir", "ábre", "abrela", "ábrela", "abrirlo", "abrirla")):
            return "open"
        if any(token in text for token in ("busca", "buscar", "búscame", "buscame")):
            return "search"
        if any(token in text for token in ("usa", "usar", "hazlo", "haz", "continua", "continúa", "sigue")):
            return "use"
        return "continue"

    def _platform_from_current_message(self, context: ContextPackage) -> str | None:
        text = self._normalized_text(context.user_message)
        for platform in ("canva", "github", "youtube", "google", "ollama", "openai"):
            if platform in text:
                return "GitHub" if platform == "github" else platform.capitalize()
        return None
