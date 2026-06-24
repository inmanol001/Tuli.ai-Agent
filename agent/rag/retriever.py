from agent.rag.formatter import format_snippets
from agent.rag.schemas import RagConfig
from agent.rag.store import ChromaKnowledgeStore, RagDependencyError, load_rag_config


class RagRetriever:
    def __init__(
        self,
        config: RagConfig | None = None,
        store: ChromaKnowledgeStore | None = None,
    ) -> None:
        self.config = config or load_rag_config()
        self._store = store

    @property
    def store(self) -> ChromaKnowledgeStore:
        if self._store is None:
            self._store = ChromaKnowledgeStore(self.config)
        return self._store

    def retrieve(self, query: str) -> list[dict]:
        if not self.config.enabled:
            return []
        try:
            return format_snippets(self.store.query(query, top_k=self.config.top_k))
        except RagDependencyError:
            return []
        except Exception:
            return []
