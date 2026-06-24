import json
from types import SimpleNamespace

from agent.gateway.message_types import ContextPackage
from agent.models.main_model import MainModel
from agent.models import model_settings
from agent.router.router_schema import RouterDecision


def test_get_main_model_returns_default_when_runtime_file_missing(monkeypatch, tmp_path):
    config_path = tmp_path / "models.yaml"
    config_path.write_text(
        "main_model:\n  model: qwen3:4b\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(model_settings, "MODELS_CONFIG_PATH", config_path)
    monkeypatch.setattr(
        model_settings, "RUNTIME_MODEL_SETTINGS_PATH", tmp_path / "missing.json"
    )

    assert model_settings.get_main_model() == "qwen3:4b"


def test_set_main_model_rejects_nonexistent_model(monkeypatch, tmp_path):
    monkeypatch.setattr(
        model_settings, "RUNTIME_MODEL_SETTINGS_PATH", tmp_path / "model_settings.json"
    )
    monkeypatch.setattr(
        model_settings,
        "list_ollama_models",
        lambda: ["qwen3:4b", "llama3.1:8b"],
    )

    try:
        model_settings.set_main_model("missing:model")
    except ValueError as exc:
        assert "no está instalado" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown model")


def test_set_main_model_saves_valid_model(monkeypatch, tmp_path):
    settings_path = tmp_path / "model_settings.json"
    monkeypatch.setattr(model_settings, "RUNTIME_MODEL_SETTINGS_PATH", settings_path)
    monkeypatch.setattr(
        model_settings,
        "list_ollama_models",
        lambda: ["qwen3:4b", "llama3.1:8b"],
    )

    saved = model_settings.set_main_model("llama3.1:8b")

    assert saved == "llama3.1:8b"
    assert json.loads(settings_path.read_text(encoding="utf-8")) == {
        "main_model": "llama3.1:8b"
    }


def test_list_ollama_models_supports_multiple_response_shapes(monkeypatch):
    monkeypatch.setattr(
        model_settings,
        "ollama",
        SimpleNamespace(
            list=lambda: {
                "models": [
                    {"name": "qwen3:4b"},
                    {"model": "llama3.1:8b"},
                    SimpleNamespace(name="qwen2.5-coder:7b"),
                ]
            }
        ),
    )

    assert model_settings.list_ollama_models() == [
        "qwen3:4b",
        "llama3.1:8b",
        "qwen2.5-coder:7b",
    ]


def test_main_model_uses_updated_runtime_model(monkeypatch):
    calls = []

    class FakeClient:
        def chat(self, model, messages, **kwargs):
            calls.append(model)
            return "hola"

    selected = {"value": "qwen3:4b"}

    def fake_get_main_model():
        return selected["value"]

    monkeypatch.setattr("agent.models.main_model.get_main_model", fake_get_main_model)
    model = MainModel(client=FakeClient())
    context = ContextPackage(
        system_prompt="system",
        user_message="hola",
        router_decision=RouterDecision(route="chat"),
    )

    model.respond(context)
    selected["value"] = "llama3.1:8b"
    model.respond(context)

    assert calls == ["qwen3:4b", "llama3.1:8b"]
