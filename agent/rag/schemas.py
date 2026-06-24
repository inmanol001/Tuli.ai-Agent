from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class KnowledgeChunk(BaseModel):
    id: str
    text: str
    source: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagSnippet(BaseModel):
    source: str
    text: str
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestStats(BaseModel):
    documents_seen: int = 0
    chunks_indexed: int = 0
    persist_path: str
    collection_name: str


class RagConfig(BaseModel):
    enabled: bool = True
    embedding_model: str = "qwen3-embedding:0.6b"
    persist_path: Path = Path("agent/rag/chroma")
    collection_name: str = "local_knowledge"
    top_k: int = 3
    min_score: float = 0.0
    knowledge_paths: list[Path] = Field(default_factory=list)
