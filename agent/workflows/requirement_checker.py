from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


class RequirementCheckResult(BaseModel):
    can_continue: bool
    needs_user_input: bool
    needs_approval: bool
    missing_info: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    approval_request: str | None = None
    reason: str = "ok"


@dataclass(slots=True)
class RequirementContext:
    workflow_name: str
    user_goal: str
    step_kind: str | None = None
    step_title: str | None = None
    state: dict[str, Any] | None = None
    requires_visual_validation: bool = False
    requires_approval: bool = False
    correction_request: bool = False


class RequirementChecker:
    """Check whether a workflow can continue without asking for unnecessary input."""

    def check(self, context: RequirementContext) -> RequirementCheckResult:
        state = context.state or {}
        workflow_name = context.workflow_name
        goal_text = context.user_goal.lower()
        title_text = (context.step_title or "").lower()
        step_text = f"{title_text} {context.step_kind or ''}".strip()

        missing_info: list[str] = []
        questions: list[str] = []
        approval_request: str | None = None
        needs_user_input = False
        needs_approval = False
        reason = "ok"

        if context.correction_request:
            needs_user_input = True
            reason = "correction_request"
            questions.append("¿Qué ajuste específico quieres que haga?")
            return RequirementCheckResult(
                can_continue=False,
                needs_user_input=needs_user_input,
                needs_approval=needs_approval,
                missing_info=missing_info,
                questions=questions,
                approval_request=approval_request,
                reason=reason,
            )

        if context.requires_approval or self._needs_safety_approval(workflow_name, goal_text, step_text):
            needs_approval = True
            reason = "safety_confirmation"
            approval_request = self._approval_request(workflow_name, context.step_title, goal_text)
            return RequirementCheckResult(
                can_continue=False,
                needs_user_input=False,
                needs_approval=needs_approval,
                missing_info=missing_info,
                questions=questions,
                approval_request=approval_request,
                reason=reason,
            )

        if context.requires_visual_validation:
            needs_approval = True
            reason = "visual_validation"
            approval_request = "¿Quieres que valide visualmente el resultado antes de cerrarlo?"
            return RequirementCheckResult(
                can_continue=False,
                needs_user_input=False,
                needs_approval=True,
                missing_info=missing_info,
                questions=questions,
                approval_request=approval_request,
                reason=reason,
            )

        if workflow_name == "design_canva_post" or "canva" in goal_text:
            format_value = self._get_state_value(state, "format")
            style_value = self._get_state_value(state, "style")

            if not format_value:
                missing_info.append("format")
            if not style_value:
                missing_info.append("style")

            if missing_info:
                needs_user_input = True
                reason = "missing_info"
                questions.append(
                    self._creative_question(
                        missing_info=missing_info,
                        topic=self._get_state_value(state, "topic") or self._extract_topic(goal_text),
                    )
                )

        if self._looks_like_preference_request(goal_text):
            needs_user_input = True
            reason = "preference"
            if not questions:
                questions.append(self._preference_question(goal_text))

        if needs_user_input:
            return RequirementCheckResult(
                can_continue=False,
                needs_user_input=True,
                needs_approval=False,
                missing_info=missing_info,
                questions=questions,
                approval_request=None,
                reason=reason,
            )

        return RequirementCheckResult(
            can_continue=True,
            needs_user_input=False,
            needs_approval=False,
            missing_info=[],
            questions=[],
            approval_request=None,
            reason=reason,
        )

    def _needs_safety_approval(self, workflow_name: str, goal_text: str, step_text: str) -> bool:
        risky_markers = (
            "borrar",
            "delete",
            "eliminar",
            "publicar",
            "postear",
            "comprar",
            "enviar",
            "send",
            "ejecutar",
            "run command",
            "comando",
            "archivo",
            "files",
        )
        return any(marker in goal_text or marker in step_text for marker in risky_markers)

    def _creative_question(self, *, missing_info: list[str], topic: str | None) -> str:
        parts = []
        if "format" in missing_info:
            parts.append("¿lo quieres como post cuadrado, historia o flyer?")
        if "style" in missing_info:
            parts.append("¿prefieres estilo elegante, playero o promocional?")
        if "platform" in missing_info:
            parts.append("¿en qué plataforma lo vas a usar?")
        if topic:
            prefix = f"Perfecto. Para hacerlo bien sobre {topic}: "
        else:
            prefix = "Perfecto. Para hacerlo bien: "
        return prefix + " ".join(parts)

    def _preference_question(self, goal_text: str) -> str:
        if "estilo" in goal_text or "style" in goal_text:
            return "¿Quieres estilo elegante, promocional o playero?"
        return "¿Qué prefieres exactamente para continuar?"

    def _approval_request(self, workflow_name: str, step_title: str | None, goal_text: str) -> str:
        if workflow_name == "design_canva_post":
            return "¿Me das permiso para continuar con este diseño?"
        if step_title:
            return f"¿Me das permiso para continuar con el paso '{step_title}'?"
        return f"¿Me das permiso para continuar con {goal_text}?"

    def _looks_like_preference_request(self, goal_text: str) -> bool:
        return any(
            phrase in goal_text
            for phrase in (
                "estilo",
                "look",
                "tono",
                "dirección",
                "direccion",
                "preferencia",
            )
        )

    def _get_state_value(self, state: dict[str, Any], key: str) -> str | None:
        value = state.get(key)
        if value is None:
            value = state.get(key.lower())
        if value is None:
            value = state.get(key.replace("_", " "))
        if value is None:
            return None
        return str(value).strip() or None

    def _extract_topic(self, goal_text: str) -> str | None:
        for marker in (" sobre ", " para ", " del ", " de la ", " de los ", " de las "):
            if marker in goal_text:
                return goal_text.split(marker, 1)[1].strip(" .,!?:;") or None
        return None


RequirementCheckerResult = RequirementCheckResult
