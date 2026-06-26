from agent.memory.memory_intent_classifier import (
    MemoryIntentClassification,
    classify_memory_intent,
)


class FakeClient:
    def __init__(self, raw: str):
        self.raw = raw
        self.calls = []

    def chat(self, model, messages, **kwargs):
        self.calls.append(
            {
                "model": model,
                "messages": messages,
                "kwargs": kwargs,
            }
        )
        return self.raw


def test_semantic_pattern_quiero_que_sepas_saves_without_model():
    client = FakeClient('{"should_save": false}')

    result = classify_memory_intent(
        "quiero que sepas que mi cumpleaños es el 18 de febrero",
        client=client,
        model="fake",
    )

    assert result.should_save is True
    assert result.value == "mi cumpleaños es el 18 de febrero"
    assert result.memory_type == "personal_fact"
    assert result.key == "birthday"
    assert result.confidence >= 0.80
    assert client.calls == []


def test_semantic_pattern_no_olvides_alias():
    result = classify_memory_intent(
        "no olvides que cuando diga diseño floral me refiero a Ysis Sánchez",
        client=FakeClient("{}"),
        model="fake",
    )

    assert result.should_save is True
    assert result.memory_type == "alias"
    assert result.key == "diseño floral"


def test_ignores_casual_text_without_model_call():
    client = FakeClient('{"should_save": true}')

    result = classify_memory_intent(
        "me gusta Figma",
        client=client,
        model="fake",
    )

    assert result.should_save is False
    assert result.reason == "no_memory_signal"
    assert client.calls == []


def test_ignores_action_without_model_call():
    client = FakeClient('{"should_save": true}')

    result = classify_memory_intent(
        "abre figma",
        client=client,
        model="fake",
    )

    assert result.should_save is False
    assert result.reason == "looks_like_action"
    assert client.calls == []


def test_model_fallback_saves_high_confidence():
    client = FakeClient(
        '{"should_save": true, "memory_type": "preference", "key": "preference", '
        '"value": "prefiero respuestas directas", "confidence": 0.91, "reason": "future preference"}'
    )

    result = classify_memory_intent(
        "cuando hablemos después quiero respuestas directas",
        client=client,
        model="fake-model",
    )

    assert result.should_save is True
    assert result.memory_type == "preference"
    assert result.value == "prefiero respuestas directas"
    assert client.calls


def test_model_fallback_rejects_low_confidence():
    client = FakeClient(
        '{"should_save": true, "memory_type": "instruction", "key": null, '
        '"value": "me gusta Figma", "confidence": 0.51, "reason": "weak"}'
    )

    result = classify_memory_intent(
        "en el futuro quizá me gusta Figma",
        client=client,
        model="fake-model",
    )

    assert result.should_save is False
    assert "low_confidence" in result.reason
