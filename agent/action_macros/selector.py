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
    """Select a macro by intent and known recipe shape, not by step-by-step reasoning."""

    def _router_wants_web_search(self, context) -> bool:
        """Return True when router/context already selected web_search.

        In that case, do not let browser-opening macros steal the request.
        web_search returns results to the agent; browser_search only opens a page.
        """

        decision = getattr(context, "router_decision", None)
        action = getattr(decision, "action", "") if decision is not None else ""
        suggested_tools = getattr(decision, "suggested_tools", []) if decision is not None else []

        if action == "web_search":
            return True
        if "web_search" in suggested_tools:
            return True

        selected_tools = getattr(context, "selected_tools", []) or []
        for tool in selected_tools:
            if isinstance(tool, dict) and tool.get("name") == "web_search":
                return True

        return False


    def select(self, context: ContextPackage) -> ActionMacroPlan:
        if self._router_wants_web_search(context):
            return ActionMacroPlan(
                selected=False,
                workflow_name=None,
                inputs={},
                reason="router_selected_web_search",
            )

        decision = context.router_decision
        if decision.route != "action_ready":
            return ActionMacroPlan(selected=False)

        raw_text = context.user_message.strip().lower()
        text = self._normalize_text(raw_text)
        if self._looks_like_work_setup(text):
            return ActionMacroPlan(
                selected=True,
                workflow_name="open_work_setup",
                inputs={"open_chatgpt": True},
                reason="matched_open_work_setup",
            )
        # Open-ended/random YouTube requests are selection intents, not literal searches.
        # They must run before generic browser search.
        if self._looks_like_random_youtube_video(text):
            topic_hint = self._topic_hint(text)
            return ActionMacroPlan(
                selected=True,
                workflow_name="play_random_youtube_video",
                inputs={
                    "query": topic_hint or "__open_ended__",
                    "target": "youtube",
                    "open_ended": True,
                    "topic_hint": topic_hint,
                    "user_context": self._user_context_hint(context),
                },
                reason="matched_play_random_youtube_video",
            )
        if self._looks_like_browser_search(text):
            open_ended = self._is_open_ended_search(text)
            topic_hint = self._topic_hint(text) if open_ended else ""
            return ActionMacroPlan(
                selected=True,
                workflow_name="open_browser_and_search",
                inputs={
                    "query": self._search_query(text) or "__open_ended__",
                    "target": self._search_target(text),
                    "open_ended": open_ended,
                    "topic_hint": topic_hint,
                    "user_context": self._user_context_hint(context),
                },
                reason="matched_open_browser_and_search",
            )
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

    def _user_context_hint(self, context: ContextPackage) -> str:
        """Collect available user preference/context hints without depending on one memory backend."""
        parts: list[str] = []

        state = context.session_state or {}
        for key in (
            "user_profile",
            "profile",
            "preferences",
            "interests",
            "likes",
            "gustos",
            "memory",
            "memories",
            "user_memory",
        ):
            value = state.get(key)
            if value:
                parts.append(str(value))

        for turn in (context.recent_history or [])[-8:]:
            role = getattr(turn, "role", "")
            content = getattr(turn, "content", "")
            if content:
                parts.append(f"{role}: {content}")

        return "\n".join(parts)

    def _is_open_ended_search(self, text: str) -> bool:
        """Detect when the user wants the agent to choose/recommend instead of searching exact words."""
        text = self._normalize_text(text.strip().lower())
        markers = (
            "random",
            "aleatorio",
            "aleatoria",
            "al azar",
            "cualquiera",
            "cualquier cosa",
            "lo que sea",
            "algo interesante",
            "sorprendeme",
            "sorpréndeme",
            "recomiendame",
            "recomiéndame",
        )
        return any(marker in text for marker in markers)

    def _topic_hint(self, text: str) -> str:
        """Extract a soft topic hint without hardcoding user preferences."""
        cleaned = self._normalize_text(text.strip().lower())

        cleaned = re.sub(r"\b(en|de)\s+(youtube|you\s*tube|internet|la\s+web|google)\b", " ", cleaned, flags=re.I)
        cleaned = re.sub(r"\b(youtube|you\s*tube|internet|web|google)\b", " ", cleaned, flags=re.I)

        match = re.search(r"\b(?:de|sobre|acerca de)\s+(.+)$", cleaned, flags=re.I)
        topic = match.group(1).strip() if match else cleaned

        topic = re.sub(
            r"\b(ponme|pon|busca|buscar|buscame|búscame|abre|abrir|reproduce|reproducir|quiero|dame|un|una|el|la|video|videos|vídeo|vídeos|random|aleatorio|aleatoria|azar|cualquiera|cualquier|cosa|lo|que|sea|algo|interesante|sorprendeme|sorpréndeme|recomiendame|recomiéndame)\b",
            " ",
            topic,
            flags=re.I,
        )
        return " ".join(topic.split())


    def _looks_like_random_youtube_video(self, text: str) -> bool:
        """Detect open-ended/random YouTube requests only."""
        if "youtube" not in text and "you tube" not in text:
            return False

        play_markers = (
            "ponme",
            "pon ",
            "reproduce",
            "play ",
            "dame",
            "quiero ver",
        )
        open_markers = (
            "random",
            "aleatorio",
            "aleatoria",
            "al azar",
            "cualquiera",
            "cualquier",
            "cualquier video",
            "lo que sea",
            "sorprendeme",
            "sorpréndeme",
        )

        has_play_intent = any(marker in text for marker in play_markers)
        has_open_marker = any(marker in text for marker in open_markers)
        mentions_video = "video" in text or "vídeo" in text

        return has_play_intent and has_open_marker and mentions_video

    def _youtube_query(self, text: str) -> str:
        """Random is a selection instruction; return only the soft topic hint."""
        return self._topic_hint(text)

    def _looks_like_work_setup(self, text: str) -> bool:
        return any(
            phrase in text
            for phrase in (
                "setup de trabajo",
                "mi setup",
                "work setup",
                "abre mi setup",
                "abre setup",
                "abrir mi setup",
            )
        )

    def _looks_like_browser_search(self, text: str) -> bool:
        return any(
            phrase in text
            for phrase in (
                "busca ",
                "buscar ",
                "search ",
                "abre google y busca",
                "open google and search",
                "abre el navegador y busca",
            )
        )

    def _search_query(self, text: str) -> str:
        """Extract search query while preserving specificity."""
        cleaned = text.strip()

        if cleaned.startswith("http://") or cleaned.startswith("https://"):
            return cleaned

        if self._is_open_ended_search(cleaned):
            return self._topic_hint(cleaned)

        patterns = (
            r"(?:abre google y busca|open google and search|abre el navegador y busca)\s+(?P<query>.+)$",
            r"(?:busca|buscar|search)\s+(?:en\s+youtube|en\s+you\s*tube)\s+(?P<query>.+)$",
            r"(?:busca|buscar|search)\s+(?:en\s+internet|en\s+la\s+web|en\s+google)?\s*(?P<query>.+)$",
            r"(?:abre|abrir|open)\s+(?P<query>.+)$",
        )

        for pattern in patterns:
            match = re.search(pattern, cleaned, flags=re.I)
            if match:
                query = match.group("query").strip()
                query = re.sub(r"^(un|una|el|la)\s+", "", query, flags=re.I).strip()
                return query

        return cleaned

    def _search_target(self, text: str) -> str:
        cleaned = text.strip().lower()

        if cleaned.startswith("http://") or cleaned.startswith("https://"):
            return "url"

        if "youtube" in cleaned or "you tube" in cleaned:
            if cleaned in ("abre youtube", "abrir youtube", "open youtube", "youtube"):
                return "youtube_home"
            return "youtube"

        if "google" in cleaned:
            if cleaned in ("abre google", "abrir google", "open google", "google"):
                return "google_home"
            return "google"

        return "auto"

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
