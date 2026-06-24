DEFAULT_CONTEXT_BUDGET = 8192


def estimate_chars_budget(tokens: int = DEFAULT_CONTEXT_BUDGET) -> int:
    return tokens * 4

