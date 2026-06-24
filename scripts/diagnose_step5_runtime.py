import time
import json
import faulthandler
import traceback

faulthandler.dump_traceback_later(45, repeat=True)

from agent.models import ollama_client as ollama_client_module
from agent.models.main_model import MainModel
from agent.router.xlam_router import XlamRouter
from agent.context_builder.builder import ContextBuilder
from agent.response_action.controller import ResponseController
from agent.executor.executor import Executor
from agent.gateway.gateway import Gateway


USER_TEXT = "busca música nueva de Bad Bunny en YouTube"


def now():
    return time.perf_counter()


def preview(value, limit=700):
    text = str(value)
    return text[:limit] + ("..." if len(text) > limit else "")


# Patch OllamaClient.chat
_original_chat = ollama_client_module.OllamaClient.chat

def timed_chat(self, model, messages, **kwargs):
    messages_list = list(messages)
    total_chars = sum(len(m.get("content", "")) for m in messages_list)
    has_schema = kwargs.get("format_schema") is not None
    options = kwargs.get("options") or {}

    print("\n[OLLAMA START]")
    print(f"model={model}")
    print(f"messages={len(messages_list)}")
    print(f"chars={total_chars}")
    print(f"format_schema={has_schema}")
    print(f"think={kwargs.get('think')}")
    print(f"stream={kwargs.get('stream')}")
    print(f"options={options}")
    print("[PROMPT PREVIEW]")
    for i, msg in enumerate(messages_list):
        print(f"--- message {i} role={msg.get('role')} chars={len(msg.get('content',''))}")
        print(preview(msg.get("content", ""), 500))

    start = now()
    try:
        result = _original_chat(self, model, messages_list, **kwargs)
        elapsed = now() - start
        print(f"[OLLAMA END] model={model} seconds={elapsed:.2f}")
        print("[RAW OUTPUT PREVIEW]")
        print(preview(result, 1000))
        return result
    except Exception as exc:
        elapsed = now() - start
        print(f"[OLLAMA ERROR] model={model} seconds={elapsed:.2f} error={exc}")
        raise


ollama_client_module.OllamaClient.chat = timed_chat


# Patch router
_original_route = XlamRouter.route

def timed_route(self, user_text):
    print("\n[STAGE START] Router.route")
    start = now()
    result = _original_route(self, user_text)
    print(f"[STAGE END] Router.route seconds={now()-start:.2f}")
    print(result.model_dump(mode="json"))
    return result

XlamRouter.route = timed_route


# Patch context builder
_original_build_context = ContextBuilder.build

def timed_build_context(self, user_text, router_decision, session):
    print("\n[STAGE START] ContextBuilder.build")
    start = now()
    result = _original_build_context(self, user_text, router_decision, session)
    print(f"[STAGE END] ContextBuilder.build seconds={now()-start:.2f}")
    def cap_name(item):
        if isinstance(item, dict):
            return item.get("name")
        return getattr(item, "name", str(item))

    print("selected_plugins:", [cap_name(p) for p in result.selected_plugins])
    print("selected_skills:", [cap_name(s) for s in result.selected_skills])
    print("selected_tools:", [cap_name(t) for t in result.selected_tools])
    return result

ContextBuilder.build = timed_build_context


# Patch main model calls
_original_plan = MainModel.plan_or_act

def timed_plan(self, context):
    print("\n[STAGE START] MainModel.plan_or_act")
    start = now()
    result = _original_plan(self, context)
    print(f"[STAGE END] MainModel.plan_or_act seconds={now()-start:.2f}")
    print(result.model_dump(mode="json"))
    return result

MainModel.plan_or_act = timed_plan


_original_finalize = MainModel.finalize_from_tool_result

def timed_finalize(self, context, tool_call, tool_result):
    print("\n[STAGE START] MainModel.finalize_from_tool_result")
    start = now()
    result = _original_finalize(self, context, tool_call, tool_result)
    print(f"[STAGE END] MainModel.finalize_from_tool_result seconds={now()-start:.2f}")
    print("[FINAL TEXT]")
    print(preview(result, 1000))
    return result

MainModel.finalize_from_tool_result = timed_finalize


# Patch executor
_original_execute = Executor.execute

def timed_execute(self, tool_call):
    print("\n[STAGE START] Executor.execute")
    print(tool_call.model_dump(mode="json"))
    start = now()
    result = _original_execute(self, tool_call)
    print(f"[STAGE END] Executor.execute seconds={now()-start:.2f}")
    print(result.model_dump(mode="json"))
    return result

Executor.execute = timed_execute


print("\n=== DIAGNOSE STEP 5 RUNTIME ===")
print("message:", USER_TEXT)

try:
    start = now()
    gateway = Gateway()
    response = gateway.handle_message(USER_TEXT, debug=True)
    print(f"\n[TOTAL END] seconds={now()-start:.2f}")
    print("\n[AGENT RESPONSE]")
    print(json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2))
except KeyboardInterrupt:
    print("\n[INTERRUPTED BY USER]")
    traceback.print_exc()
except Exception:
    print("\n[ERROR]")
    traceback.print_exc()
