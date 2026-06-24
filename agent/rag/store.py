from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

import yaml

from agent.rag.schemas import IngestStats, KnowledgeChunk, RagConfig, RagSnippet


SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt", ".jsonl"}


class RagDependencyError(RuntimeError):
    pass


def load_rag_config(config_path: str | Path = "agent/config/rag.yaml") -> RagConfig:
    raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    rag = raw.get("rag", {})
    paths = raw.get("knowledge_paths", [])
    return RagConfig(
        enabled=bool(rag.get("enabled", True)),
        embedding_model=rag.get("embedding_model", "qwen3-embedding:0.6b"),
        persist_path=Path(rag.get("persist_path", "agent/rag/chroma")),
        collection_name=rag.get("collection_name", "local_knowledge"),
        top_k=int(rag.get("top_k", 3)),
        min_score=float(rag.get("min_score", 0.0)),
        knowledge_paths=[Path(path) for path in paths],
    )


class OllamaEmbeddingFunction:
    def __init__(self, model: str) -> None:
        self.model = model

    @staticmethod
    def name() -> str:
        return "ollama"

    @staticmethod
    def is_legacy() -> bool:
        return False

    @staticmethod
    def default_space() -> str:
        return "cosine"

    @staticmethod
    def supported_spaces() -> list[str]:
        return ["cosine"]

    def get_config(self) -> dict:
        return {"model": self.model}

    @staticmethod
    def build_from_config(config: dict):
        return OllamaEmbeddingFunction(config.get("model", "qwen3-embedding:0.6b"))

    def embed_query(self, input):
        return self(input)

    def embed_documents(self, input):
        return self(input)

    def __call__(self, input):
        import ollama

        texts = [input] if isinstance(input, str) else list(input)
        embeddings = []
        for text in texts:
            try:
                response = ollama.embed(model=self.model, input=text)
                values = response["embeddings"][0]
            except Exception:
                response = ollama.embeddings(model=self.model, prompt=text)
                values = response["embedding"]
            embeddings.append(values)
        return embeddings


class ChromaKnowledgeStore:
    def __init__(self, config: RagConfig | None = None) -> None:
        self.config = config or load_rag_config()
        self.config.persist_path.mkdir(parents=True, exist_ok=True)
        try:
            import chromadb
        except ImportError as exc:
            raise RagDependencyError(
                "chromadb is required for Paso 7. Install requirements-rag.txt."
            ) from exc
        self.client = chromadb.PersistentClient(path=str(self.config.persist_path))
        self.embedding_function = OllamaEmbeddingFunction(self.config.embedding_model)
        self.collection = self.client.get_or_create_collection(
            name=self.config.collection_name,
            embedding_function=self.embedding_function,
        )

    def upsert_chunks(self, chunks: list[KnowledgeChunk]) -> None:
        if not chunks:
            return
        self.collection.upsert(
            ids=[chunk.id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            metadatas=[
                {"source": chunk.source, **chunk.metadata}
                for chunk in chunks
            ],
        )

    def query(self, query_text: str, top_k: int | None = None) -> list[RagSnippet]:
        result = self.collection.query(
            query_texts=[query_text],
            n_results=top_k or self.config.top_k,
        )
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        snippets: list[RagSnippet] = []
        for text, metadata, distance in zip(documents, metadatas, distances):
            score = None if distance is None else max(0.0, 1.0 - float(distance))
            if score is not None and score < self.config.min_score:
                continue
            metadata = metadata or {}
            snippets.append(
                RagSnippet(
                    source=str(metadata.get("source", "unknown")),
                    text=text,
                    score=score,
                    metadata=dict(metadata),
                )
            )
        return snippets


def iter_knowledge_files(paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if not path.exists():
            continue
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            files.append(path)
            continue
        if path.is_dir():
            files.extend(
                file
                for file in path.rglob("*")
                if file.is_file() and file.suffix.lower() in SUPPORTED_SUFFIXES
            )
    return sorted(files)


def load_file_chunks(file_path: Path, chunk_size: int = 1200) -> list[KnowledgeChunk]:
    if file_path.suffix.lower() == ".jsonl":
        texts = []
        for line in file_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            texts.append(str(payload.get("text") or payload.get("content") or payload))
        text = "\n\n".join(texts)
    else:
        text = file_path.read_text(encoding="utf-8")

    chunks = []
    normalized = text.strip()
    if not normalized:
        return chunks
    for index, start in enumerate(range(0, len(normalized), chunk_size)):
        chunk_text = normalized[start : start + chunk_size].strip()
        chunk_id = hashlib.sha256(
            f"{file_path.as_posix()}:{index}:{chunk_text}".encode("utf-8")
        ).hexdigest()
        chunks.append(
            KnowledgeChunk(
                id=chunk_id,
                text=chunk_text,
                source=file_path.as_posix(),
                metadata={"chunk_index": index},
            )
        )
    return chunks


def ingest_knowledge(config: RagConfig | None = None) -> IngestStats:
    config = config or load_rag_config()
    store = ChromaKnowledgeStore(config)
    files = iter_knowledge_files(config.knowledge_paths)
    chunks: list[KnowledgeChunk] = []
    for file_path in files:
        chunks.extend(load_file_chunks(file_path))
    store.upsert_chunks(chunks)
    return IngestStats(
        documents_seen=len(files),
        chunks_indexed=len(chunks),
        persist_path=str(config.persist_path),
        collection_name=config.collection_name,
    )
