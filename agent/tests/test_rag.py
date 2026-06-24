from pathlib import Path

from agent.rag.store import (
    ChromaKnowledgeStore,
    RagConfig,
    ingest_knowledge,
    load_file_chunks,
)


class FakeEmbeddingFunction:
    @staticmethod
    def name():
        return "default"

    @staticmethod
    def is_legacy():
        return False

    @staticmethod
    def default_space():
        return "cosine"

    @staticmethod
    def supported_spaces():
        return ["cosine"]

    def get_config(self):
        return {"model": "fake"}

    @staticmethod
    def build_from_config(_config):
        return FakeEmbeddingFunction()

    def embed_query(self, input):
        return self(input)

    def embed_documents(self, input):
        return self(input)

    def __call__(self, input):
        texts = [input] if isinstance(input, str) else list(input)
        return [[float(len(text) % 10), 1.0, 0.5] for text in texts]


def test_load_file_chunks_creates_deterministic_chunks(tmp_path: Path):
    doc = tmp_path / "json.md"
    doc.write_text("JSON local procedure notes", encoding="utf-8")

    chunks = load_file_chunks(doc)

    assert len(chunks) == 1
    assert chunks[0].source == doc.as_posix()
    assert "JSON local" in chunks[0].text


def test_chroma_store_indexes_and_retrieves_with_fake_embedding(tmp_path, monkeypatch):
    monkeypatch.setattr("agent.rag.store.OllamaEmbeddingFunction", lambda _model: FakeEmbeddingFunction())
    config = RagConfig(
        persist_path=tmp_path / "chroma",
        collection_name="test_knowledge",
        knowledge_paths=[],
        top_k=2,
    )
    store = ChromaKnowledgeStore(config)
    doc = tmp_path / "json.md"
    doc.write_text("Procedimiento JSON: valida claves y comillas.", encoding="utf-8")
    store.upsert_chunks(load_file_chunks(doc))

    snippets = store.query("JSON claves", top_k=1)

    assert len(snippets) == 1
    assert snippets[0].source == doc.as_posix()
    assert "Procedimiento JSON" in snippets[0].text


def test_ingest_knowledge_is_idempotent_with_fake_embedding(tmp_path, monkeypatch):
    monkeypatch.setattr("agent.rag.store.OllamaEmbeddingFunction", lambda _model: FakeEmbeddingFunction())
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "json.md").write_text("Nota JSON para RAG local.", encoding="utf-8")
    config = RagConfig(
        persist_path=tmp_path / "chroma",
        collection_name="test_ingest",
        knowledge_paths=[docs],
        top_k=3,
    )

    first = ingest_knowledge(config)
    second = ingest_knowledge(config)

    assert first.documents_seen == 1
    assert first.chunks_indexed == 1
    assert second.documents_seen == 1
    assert second.chunks_indexed == 1
