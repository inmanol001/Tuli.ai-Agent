import importlib
import inspect

possible = [
    ("agent.models.ollama_client", ["OllamaClient", "OllamaChatClient", "OllamaModel"]),
    ("agent.model.ollama_client", ["OllamaClient", "OllamaChatClient", "OllamaModel"]),
    ("agent.llm.ollama_client", ["OllamaClient", "OllamaChatClient", "OllamaModel"]),
    ("agent.main_model", ["MainModel", "MainChatModel", "MainModelClient"]),
    ("agent.planner.tool_planner", ["ToolPlanner"]),
    ("agent.tool_planner", ["ToolPlanner"]),
    ("agent.response_action.controller", ["ResponseActionController"]),
]

for mod_name, attrs in possible:
    try:
        mod = importlib.import_module(mod_name)
    except Exception as e:
        print(f"IMPORT_FAIL {mod_name}: {type(e).__name__}: {e}")
        continue

    print(f"\nMODULE {mod_name}: {getattr(mod, '__file__', '')}")
    for attr in attrs:
        if not hasattr(mod, attr):
            continue
        obj = getattr(mod, attr)
        print(f"FOUND {attr}: {obj}")
        try:
            print("  signature:", inspect.signature(obj))
        except Exception as e:
            print("  signature_error:", e)

        if inspect.isclass(obj):
            try:
                inst = obj()
                print("  instantiate: OK", inst)
                for meth in dir(inst):
                    low = meth.lower()
                    if any(k in low for k in ["chat", "generate", "complete", "run", "invoke", "plan"]):
                        fn = getattr(inst, meth)
                        if callable(fn):
                            try:
                                print("   method:", meth, inspect.signature(fn))
                            except Exception:
                                print("   method:", meth)
            except Exception as e:
                print("  instantiate: FAIL", type(e).__name__, e)
