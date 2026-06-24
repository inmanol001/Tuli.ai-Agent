from __future__ import annotations

from collections import Counter

from pydantic import BaseModel

from agent.workflows.schemas import FullWorkflowFinalizerResult, FullWorkflowResult


class FullWorkflowFinalizer(BaseModel):
    def finalize(
        self, *, user_message: str, workflow_result: FullWorkflowResult
    ) -> FullWorkflowFinalizerResult:
        try:
            return FullWorkflowFinalizerResult(
                text=self._finalize_text(
                    user_message=user_message, workflow_result=workflow_result
                ),
                fallback=True,
            )
        except Exception as exc:
            return FullWorkflowFinalizerResult(
                text="No pude redactar el resultado del full workflow.",
                fallback=True,
                error=str(exc),
            )

    def _finalize_text(
        self, *, user_message: str, workflow_result: FullWorkflowResult
    ) -> str:
        if workflow_result.workflow_name != "design_canva_post":
            return "El full workflow se preparó, pero no tengo un resumen específico."

        topic = workflow_result.inputs.get("topic", "el tema solicitado")
        phase_counter = Counter(phase.status for phase in workflow_result.phases)
        kind_counter = Counter(phase.kind for phase in workflow_result.phases)
        missing = (
            ", ".join(workflow_result.missing_tools)
            if workflow_result.missing_tools
            else "ninguna"
        )
        prompt = workflow_result.state.get_value("image_prompt")
        copy_text = workflow_result.state.get_value("copy_text")
        reasoning_bits = []
        if prompt:
            reasoning_bits.append(f"prompt: {prompt}")
        if copy_text:
            reasoning_bits.append(f"copy: {copy_text}")
        reasoning_summary = " ".join(reasoning_bits)

        if workflow_result.success:
            return (
                f"Preparé el workflow de Canva para {topic} y quedó completado. "
                f"Fases completadas: {phase_counter.get('completed', 0)}. "
                f"{reasoning_summary}".strip()
            )

        if workflow_result.status == "needs_clarification":
            return "Me falta un detalle para arrancar el workflow de Canva: el tema del post."

        return (
            f"Preparé y simulé el workflow de Canva para {topic}. "
            f"No lo marqué como creado de verdad porque todavía faltan tools para completarlo automáticamente. "
            f"Fases completadas: {phase_counter.get('completed', 0)}; "
            f"razonadas: {kind_counter.get('reason', 0)}; "
            f"simuladas: {phase_counter.get('simulated', 0)}; "
            f"bloqueadas: {phase_counter.get('blocked_missing_tools', 0)}. "
            f"Estado razonado: {reasoning_summary or 'sin texto adicional'}. "
            f"Tools faltantes: {missing}."
        )


WorkflowFinalizer = FullWorkflowFinalizer
WorkflowFinalizerResult = FullWorkflowFinalizerResult
