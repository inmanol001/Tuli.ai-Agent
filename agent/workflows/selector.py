from __future__ import annotations

import re
import unicodedata

from agent.gateway.message_types import ContextPackage
from agent.workflows.definitions import DesignCanvaPostWorkflow
from agent.workflows.schemas import FullWorkflowPlan


class FullWorkflowSelector:
    def select(self, context: ContextPackage) -> FullWorkflowPlan:
        decision = context.router_decision
        if decision.route != "action_ready":
            return FullWorkflowPlan(selected=False)

        text = self._normalize_text(context.user_message)
        topic = self._extract_topic(context.user_message)
        content_type = self._extract_content_type(text)

        if self._looks_like_canva_post(text):
            if not topic:
                return FullWorkflowPlan(
                    selected=True,
                    workflow_name="design_canva_post",
                    status="needs_clarification",
                    reason="missing_topic",
                    missing_info=["topic"],
                    simulation_mode=True,
                    missing_tools=list(DesignCanvaPostWorkflow.missing_tools),
                )

            return FullWorkflowPlan(
                selected=True,
                workflow_name="design_canva_post",
                inputs={
                    "topic": topic,
                    "format": content_type,
                    "target_app": "Canva",
                },
                status="selected",
                reason="matched_design_canva_post",
                simulation_mode=True,
                missing_tools=list(DesignCanvaPostWorkflow.missing_tools),
            )

        if self._looks_like_creative_asset_request(text):
            return FullWorkflowPlan(
                selected=True,
                workflow_name=None,
                status="needs_clarification",
                reason="missing_workflow_target",
                missing_info=["target_workflow_or_platform"],
                inputs={
                    "topic": topic,
                    "format": content_type,
                },
                simulation_mode=True,
            )

        return FullWorkflowPlan(selected=False)

    def _looks_like_canva_post(self, text: str) -> bool:
        canva = "canva" in text
        post_like = any(
            phrase in text
            for phrase in (
                "post",
                "publicacion",
                "publicación",
                "diseña",
                "disena",
                "crear",
                "haz",
                "hacer",
            )
        )
        return canva and post_like

    def _looks_like_creative_asset_request(self, text: str) -> bool:
        creative_verbs = (
            "haz",
            "hacer",
            "crea",
            "crear",
            "disena",
            "diseña",
            "disenar",
            "diseñar",
            "prepara",
            "preparar",
            "genera",
            "generar",
            "produce",
            "producir",
        )
        creative_assets = (
            "post",
            "diseno",
            "diseño",
            "flyer",
            "tarjeta",
            "anuncio",
            "banner",
            "imagen",
            "pieza",
            "arte",
            "historia",
            "story",
            "reel",
            "publicacion",
            "publicación",
            "caption",
            "copy",
        )
        chat_only_markers = (
            "dame ideas",
            "ideas para",
            "que puedo escribir",
            "qué puedo escribir",
            "sugerencias",
            "ayudame a mejorar",
            "ayúdame a mejorar",
            "corrige",
            "reescribe",
            "mejora",
        )
        return (
            any(marker in text for marker in creative_verbs)
            and any(marker in text for marker in creative_assets)
            and not any(marker in text for marker in chat_only_markers)
        )

    def _extract_content_type(self, text: str) -> str:
        for content_type in (
            "post",
            "flyer",
            "tarjeta",
            "anuncio",
            "banner",
            "imagen",
            "historia",
            "story",
            "reel",
            "publicacion",
            "caption",
            "copy",
            "diseno",
        ):
            if content_type in text:
                return "post" if content_type == "publicacion" else content_type
        return "post"

    def _extract_topic(self, raw_text: str) -> str | None:
        match = re.search(
            r"\b(?:del|de la|de los|de las|para|sobre|acerca de)\s+(?P<topic>.+)$",
            raw_text,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        topic = match.group("topic").strip(" .,!?:;\"'")
        return topic or None

    def _normalize_text(self, text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text.lower())
        return "".join(ch for ch in normalized if not unicodedata.combining(ch))


WorkflowSelector = FullWorkflowSelector
