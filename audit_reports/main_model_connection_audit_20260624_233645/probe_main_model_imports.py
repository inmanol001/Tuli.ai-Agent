import importlib
import inspect
import pkgutil

candidates = [
    "agent.models",
    "agent.model",
    "agent.llm",
    "agent.ollama",
    "agent.main_model",
    "agent.clients",
    "agent.clients.ollama",
    "agent.brains",
    "agent.planner",
    "agent.tool_planner",
    "agent.response",
    "agent.response_action",
    "agent.router",
]

print("== direct candidate imports ==")
for name in candidates:
    try:
        mod = importlib.import_module(name)
        print(f"OK {name}: {getattr(mod, '__file__', '')}")
        for attr in dir(mod):
            low = attr.lower()
            if any(k in low for k in ["model", "ollama", "client", "planner", "generate", "chat"]):
                obj = getattr(mod, attr, None)
                print("  ", attr, type(obj))
    except Exception as e:
        print(f"ERR {name}: {type(e).__name__}: {e}")

print("\n== walk agent modules matching keywords ==")
try:
    import agent
    for m in pkgutil.walk_packages(agent.__path__, prefix="agent."):
        name = m.name
        if not any(k in name.lower() for k in ["model", "ollama", "client", "llm", "planner", "response", "router"]):
            continue
        try:
            mod = importlib.import_module(name)
            print(f"\nOK {name}: {getattr(mod, '__file__', '')}")
            for attr in dir(mod):
                low = attr.lower()
                if any(k in low for k in ["main", "model", "ollama", "client", "planner", "generate", "chat", "complete"]):
                    obj = getattr(mod, attr, None)
                    if inspect.isclass(obj) or inspect.isfunction(obj):
                        sig = ""
                        try:
                            sig = str(inspect.signature(obj))
                        except Exception:
                            pass
                        print(f"  {attr}: {type(obj).__name__} {sig}")
        except Exception as e:
            print(f"ERR {name}: {type(e).__name__}: {e}")
except Exception as e:
    print("walk_error:", repr(e))
