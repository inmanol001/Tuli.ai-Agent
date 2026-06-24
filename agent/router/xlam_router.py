import json

from pydantic import ValidationError

from agent.models.ollama_client import OllamaClient
from agent.router.router_prompt import ROUTER_SYSTEM_PROMPT, build_router_prompt
from agent.router.router_schema import RouterDecision, RouterResult
from agent.router.router_validator import validate_and_correct_router_decision


class XlamRouter:
    def __init__(
        self,
        client: OllamaClient | None = None,
        model: str = "allenporter/xlam:1b",
        fallback_model: str = "qwen3:4b",
    ) -> None:
        self.client = client or OllamaClient()
        self.model = model
        self.fallback_model = fallback_model

    def route(self, user_text: str) -> RouterResult:
        last_error: str | None = None
        for model in (self.model, self.model, self.fallback_model):
            try:
                raw = self.client.chat(
                    model,
                    [
                        {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                        {"role": "user", "content": build_router_prompt(user_text)},
                    ],
                    format_schema=RouterDecision.json_schema_for_ollama(),
                    stream=False,
                    think=False,
                    options={"temperature": 0},
                )
                payload = json.loads(raw)
                decision = RouterDecision.model_validate(payload)
                decision, corrected = validate_and_correct_router_decision(
                    decision, user_text
                )
                return RouterResult(
                    decision=decision,
                    model_used=model,
                    raw=raw,
                    corrected=corrected,
                )
            except (json.JSONDecodeError, ValidationError, Exception) as exc:
                last_error = str(exc)

        decision, corrected = validate_and_correct_router_decision(
            RouterDecision(), user_text
        )
        return RouterResult(
            decision=decision,
            model_used="deterministic_fallback",
            raw="{}",
            corrected=corrected,
            error=last_error,
        )
