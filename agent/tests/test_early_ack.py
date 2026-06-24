from agent.response_action.early_ack import (
    DEFAULT_EARLY_ACKS,
    EARLY_ACKS,
    build_early_ack,
)


def test_build_early_ack_returns_browser_phrase():
    ack = build_early_ack(["browser_search"])
    assert ack in EARLY_ACKS["browser_search"]


def test_build_early_ack_returns_open_app_phrase():
    ack = build_early_ack(["open_app"])
    assert ack in EARLY_ACKS["open_app"]


def test_build_early_ack_returns_fallback_for_unknown_tool():
    ack = build_early_ack(["unknown_tool"])
    assert ack in DEFAULT_EARLY_ACKS


def test_early_ack_phrases_do_not_sound_completed():
    banned = ["listo", "ya", "abrí", "busqué", "cambié"]
    all_phrases = DEFAULT_EARLY_ACKS[:]
    for options in EARLY_ACKS.values():
        all_phrases.extend(options)

    for phrase in all_phrases:
        lowered = phrase.lower()
        assert all(token not in lowered for token in banned)
