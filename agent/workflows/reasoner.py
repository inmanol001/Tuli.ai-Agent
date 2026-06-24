from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from agent.models.ollama_client import OllamaClient
from agent.models.model_settings import get_main_model
from agent.workflows.schemas import FullWorkflowState


WORKFLOW_REASONER_SYSTEM_PROMPT = """Eres la cabeza de razonamiento de un workflow local.
No ejecutas herramientas.
No afirmes que hiciste acciones externas.
Solo produces el contenido, análisis o decisión que esta fase requiere.
Usa únicamente los inputs y el estado del workflow.
Responde en español.
Sé concreto.
"""


class WorkflowReasonerResult(BaseModel):
    model_used: str
    text: str
    error: str | None = None
    fallback: bool = False


class WorkflowReasoner:
    def __init__(
        self, client: OllamaClient | None = None, model: str | None = None
    ) -> None:
        self.client = client or OllamaClient()
        self.model = model or get_main_model()

    def reason(
        self,
        *,
        workflow_name: str,
        phase_name: str,
        task: str,
        state: FullWorkflowState,
        inputs: dict[str, Any],
    ) -> WorkflowReasonerResult:
        payload = {
            "workflow_name": workflow_name,
            "phase_name": phase_name,
            "task": task,
            "state": state.model_dump(mode="json"),
            "inputs": inputs,
        }
        try:
            text = self.client.chat(
                self.model,
                [
                    {"role": "system", "content": WORKFLOW_REASONER_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False),
                    },
                ],
                stream=False,
                options={"temperature": 0.2, "top_p": 0.9, "num_ctx": 8192},
            ).strip()
            if not text:
                raise ValueError("WorkflowReasoner devolvio texto vacio")
            return WorkflowReasonerResult(model_used=self.model, text=text)
        except Exception as exc:
            return WorkflowReasonerResult(
                model_used=self.model,
                text=self._fallback_reason(task, state, inputs),
                fallback=True,
                error=str(exc),
            )

    def _fallback_reason(
        self, task: str, state: FullWorkflowState, inputs: dict[str, Any]
    ) -> str:
        topic = inputs.get("topic") or state.get_value("topic") or "el tema solicitado"
        if "prompt" in task.lower():
            return f"Prompt creativo base para {topic}."
        if "copy" in task.lower() or "texto" in task.lower():
            return f"Texto breve y claro para {topic}."
        return f"Análisis para {topic}."
