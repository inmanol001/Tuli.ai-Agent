from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


Intent = Literal["chat", "action", "memory", "rag", "safety", "refuse"]
Route = Literal[
    "chat",
    "clarification",
    "planner",
    "action_ready",
    "memory_lookup",
    "rag_lookup",
    "safety_confirmation",
    "refuse",
]
RiskLevel = Literal["low", "medium", "high"]


def _normalize_browser_search_aliases(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        if value == "web_search":
            value = "browser_search"
        if value not in normalized:
            normalized.append(value)
    return normalized


class RouterDecision(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    intent: Intent = "chat"
    domain: str = "general"
    action: str = "respond"
    route: Route = "chat"
    needs_tool: bool = False
    needs_clarification: bool = False
    missing_info: list[str] = Field(default_factory=list)
    needs_memory: bool = False
    needs_rag: bool = False
    needs_vision: bool = False
    risk_level: RiskLevel = "low"
    suggested_plugins: list[str] = Field(default_factory=list)
    suggested_skills: list[str] = Field(default_factory=list)
    suggested_tools: list[str] = Field(default_factory=list)
    context_needed: list[str] = Field(default_factory=list)

    @field_validator("suggested_skills", "suggested_tools")
    @classmethod
    def normalize_web_search_aliases(cls, values: list[str]) -> list[str]:
        return _normalize_browser_search_aliases(values)

    @classmethod
    def json_schema_for_ollama(cls) -> dict[str, Any]:
        return cls.model_json_schema()


class RouterResult(BaseModel):
    decision: RouterDecision
    model_used: str
    raw: str
    corrected: bool = False
    error: str | None = None
