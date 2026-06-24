from agent.rag.store import ingest_knowledge


def run_ingest() -> dict:
    return ingest_knowledge().model_dump(mode="json")
