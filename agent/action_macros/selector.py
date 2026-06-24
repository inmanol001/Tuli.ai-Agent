from __future__ import annotations

import re
import unicodedata
from typing import Any

from agent.capabilities.tools.macos_window_tools import NATIVE_TILING_ACTIONS
from agent.gateway.message_types import ContextPackage
from agent.router.router_schema import RouterDecision
from agent.action_macros.schemas import ActionMacroPlan


APP_ALIASES = {
    "google chrome": "Google Chrome",
    "chrome": "Google Chrome",
    "safari": "Safari",
    "terminal": "Terminal",
    "finder": "Finder",
    "notes": "Notes",
    "notas": "Notes",
    "vscode": "Visual Studio Code",
    "vs code": "Visual Studio Code",
    "visual studio code": "Visual Studio Code",
    "code": "Visual Studio Code",
}

WINDOW_ACTION_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("top-left", ("esquina superior izquierda", "upper left corner", "top left")),
    ("top-right", ("esquina superior derecha", "upper right corner", "top right")),
    ("bottom-left", ("esquina inferior izquierda", "lower left corner", "bottom left")),
    ("bottom-right", ("esquina inferior derecha", "lower right corner", "bottom right")),
    ("left-right", ("left & right", "left-right", "izquierda y derecha")),
    ("quarters", ("quarters", "cuartos")),
    ("return", (
        "tamaño anterior",
        "volver al tamaño anterior",
        "previous size",
        "return to previous size",
        "volver a su tamaño anterior",
    )),
    ("fill", ("llenar", "llena", "fill", "llena la pantalla", "llenar la pantalla")),
    ("center", ("centrar", "centra", "center", "centra la ventana", "ponla al centro")),
    ("top", ("arriba", "top")),
    ("bottom", ("abajo", "bottom")),
    ("left", ("izquierda", "left")),
    ("right", ("derecha", "right")),
]


class ActionMacroSelector:
    def select(self, context: ContextPackage) -> ActionMacroPlan:
        decision = context.router_decision
        if decision.route != "action_ready":
            return ActionMacroPlan(selected=False)

        raw_text = context.user_message.strip().lower()
        text = self._normalize_text(raw_text)
        window_action = self._detect_window_action(text)
        if not window_action:
            return ActionMacroPlan(selected=False)

        open_app_intent = self._has_open_app_intent(text)
        app_name = self._extract_app_name(text) if open_app_intent else None

        if open_app_intent:
            if not app_name:
                return ActionMacroPlan(selected=False)
            return ActionMacroPlan(
                selected=True,
                workflow_name="open_app_and_tile_window",
                inputs={"app_name": app_name, "window_action": window_action},
                reason="matched_open_app_and_tile_window",
            )

        if self._mentions_window(text):
            return ActionMacroPlan(
                selected=True,
                workflow_name="tile_active_window",
                inputs={"window_action": window_action},
                reason="matched_tile_active_window",
            )

        return ActionMacroPlan(selected=False)

    def _mentions_window(self, text: str) -> bool:
        return any(token in text for token in ("ventana", "window", "esta ventana", "ventana activa"))

    def _has_open_app_intent(self, text: str) -> bool:
        return any(
            phrase in text
            for phrase in ("abre", "abrir", "open", "lanza", "inicia")
        )

    def _extract_app_name(self, text: str) -> str | None:
        for alias in sorted(APP_ALIASES, key=len, reverse=True):
            pattern = rf"\b{re.escape(alias)}\b"
            if re.search(pattern, text):
                return APP_ALIASES[alias]

        match = re.search(
            r"\b(?:abre|abrir|open|lanza|inicia)\s+(?P<app>.+?)(?:\s+y\s+(?:pon|coloca|manda|centra)\b|\s+(?:a\s+la\s+derecha|a\s+la\s+izquierda|a\s+la\s+izquierda|a\s+la\s+derecha)\b|$)",
            text,
        )
        if match:
            candidate = match.group("app").strip(" .,!?:;")
            return self._normalize_app_candidate(candidate)
        return None

    def _normalize_app_candidate(self, candidate: str) -> str | None:
        if not candidate:
            return None
        for alias in sorted(APP_ALIASES, key=len, reverse=True):
            if alias in candidate:
                return APP_ALIASES[alias]
        return candidate.title()

    def _detect_window_action(self, text: str) -> str | None:
        for action, phrases in WINDOW_ACTION_PATTERNS:
            if any(phrase in text for phrase in phrases):
                if action in NATIVE_TILING_ACTIONS:
                    return action
        return None

    def _normalize_text(self, text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text)
        return "".join(ch for ch in normalized if not unicodedata.combining(ch))


WorkflowSelector = ActionMacroSelector
