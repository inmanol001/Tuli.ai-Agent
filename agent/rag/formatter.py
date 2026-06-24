from agent.rag.schemas import RagSnippet


def format_snippets(snippets: list[RagSnippet]) -> list[dict]:
    return [snippet.model_dump(mode="json") for snippet in snippets]


def snippets_to_prompt_lines(snippets: list[dict]) -> list[str]:
    if not snippets:
        return ["RAG snippets: (none)"]
    lines = ["RAG snippets:"]
    for index, snippet in enumerate(snippets, start=1):
        source = snippet.get("source", "unknown")
        score = snippet.get("score")
        text = " ".join(str(snippet.get("text", "")).split())
        lines.append(f"[{index}] source={source} score={score}: {text}")
    return lines
