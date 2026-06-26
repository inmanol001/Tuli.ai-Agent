from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from agent.gateway.message_types import ContextPackage


SuggestedRoute = Literal["chat", "action_ready", "clarification"]
Confidence = Literal["none", "low", "high"]


class ActionIntentResult(BaseModel):
    action_required: bool
    reason: str
    action_type: str | None = None
    target: str | None = None
    confidence: Confidence = "none"
    missing_info: list[str] = Field(default_factory=list)
    suggested_route: SuggestedRoute = "chat"
    suggested_tools: list[str] = Field(default_factory=list)


class ActionIntentGuard:
    """
    Guard mínimo: si algo llegó a chat pero tiene verbo operativo + objetivo explícito,
    se recupera como acción antes de llamar MainModel.
    """

    _conceptual_patterns = (
        r"^\s*(qu[eé]\s+es|que\s+es)\b",
        r"^\s*(expl[ií]came|explicame)\b",
        r"^\s*(c[oó]mo\s+funciona|como\s+funciona)\b",
        r"^\s*(cu[aá]l\s+es|cual\s+es)\b",
        r"^\s*(por\s+qu[eé]|por\s+que)\b",
        r"^\s*(dime|cu[eé]ntame|cuentame)\s+(qu[eé]|que|c[oó]mo|como|por\s+qu[eé]|por\s+que)\b",
    )

    _patterns: tuple[tuple[str, str, list[str]], ...] = (
        (
            "open",
            r"^\s*(?:abre|abrir|[aá]breme|lanza|inicia|ejecuta)\s+(.+)$",
            ["open_app", "browser_search"],
        ),
        (
            "show",
            r"^\s*(?:mu[eé]strame|muestrame|muestra|ens[eé][nñ]ame|ll[eé]vame\s+a|llevame\s+a)\s+(.+)$",
            ["browser_search", "macos_visible_windows"],
        ),
        (
            "search",
            r"^\s*(?:busca|buscar|b[uú]scame|buscame|investiga|consulta)\s+(.+)$",
            ["web_search"],
        ),
        (
            "activate",
            r"^\s*(?:activa|activar|enciende|muestra|abre)\s+(.+)$",
            ["macos_space_mission_control", "open_app"],
        ),
        (
            "window_move",
            r"^\s*(?:pon|poner|mueve|mover|manda|mandar|lleva|llevar)\s+(.+?\b(?:ventana|window)\b.+|.+?\b(?:ventana|window)\b)\s*$",
            ["window_native_tiling"],
        ),
    )

    _missing_target_patterns = (
        r"^\s*(?:abre|abrir|[aá]breme|lanza|inicia|ejecuta)\s*$",
        r"^\s*(?:mu[eé]strame|muestrame|muestra|ens[eé][nñ]ame|ll[eé]vame\s+a|llevame\s+a)\s*$",
        r"^\s*(?:busca|buscar|b[uú]scame|buscame|investiga|consulta)\s*$",
        r"^\s*(?:activa|activar|enciende)\s*$",
        r"^\s*(?:pon|poner|mueve|mover|manda|mandar|lleva|llevar)\s*$",
    )

    _window_direction_words = (
        "izquierda",
        "derecha",
        "arriba",
        "abajo",
        "centro",
        "maximiza",
        "maximizar",
        "pantalla completa",
        "mitad",
        "lado",
    )

    def evaluate(self, context: ContextPackage) -> ActionIntentResult:
        if context.router_decision.route != "chat":
            return ActionIntentResult(action_required=False, reason="route_not_chat")

        text = self._normalized_text(context.user_message)
        original = context.user_message or ""

        if not text:
            return ActionIntentResult(action_required=False, reason="empty_message")

        if self._is_conceptual(text):
            return ActionIntentResult(action_required=False, reason="conceptual_question")

        for pattern in self._missing_target_patterns:
            if re.search(pattern, text, re.I):
                return ActionIntentResult(
                    action_required=False,
                    reason="missing_target",
                    confidence="high",
                    missing_info=["target"],
                    suggested_route="clarification",
                )

        for action_type, pattern, suggested_tools in self._patterns:
            match = re.search(pattern, original, re.I) or re.search(pattern, text, re.I)
            if not match:
                continue

            target = self._clean_target(match.group(1))
            if not target:
                return ActionIntentResult(
                    action_required=False,
                    reason="missing_target",
                    action_type=action_type,
                    confidence="high",
                    missing_info=["target"],
                    suggested_route="clarification",
                )

            if action_type == "window_move" and not self._looks_like_window_action(text):
                continue

            return ActionIntentResult(
                action_required=True,
                reason="verb_plus_target",
                action_type=action_type,
                target=target,
                confidence="high",
                suggested_route="action_ready",
                suggested_tools=suggested_tools,
            )

        return ActionIntentResult(action_required=False, reason="no_action_pattern")

    def _is_conceptual(self, text: str) -> bool:
        return any(re.search(pattern, text, re.I) for pattern in self._conceptual_patterns)

    def _looks_like_window_action(self, text: str) -> bool:
        if "ventana" not in text and "window" not in text:
            return False
        return any(word in text for word in self._window_direction_words)

    def _clean_target(self, value: str) -> str | None:
        target = (value or "").strip().strip(" .,:;!?¿¡()[]{}\"'`")

        if self._normalized_text(target) in {
            "eso", "esa", "ese", "esto", "esta", "este",
            "la", "lo", "el", "la app", "la pagina", "la página", "el sitio",
        }:
            return None

        if not target:
            return None

        if len(target) > 120:
            return None

        return target

    def _normalized_text(self, text: str) -> str:
        return " ".join((text or "").strip().lower().split())
