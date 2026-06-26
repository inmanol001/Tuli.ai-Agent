#!/usr/bin/env bash
set -u

OUT_DIR="audit_reports"
TS="$(date +"%Y%m%d_%H%M%S")"
OUT="$OUT_DIR/main_model_connection_audit_$TS"
mkdir -p "$OUT"

echo "======================================"
echo " MainModel connection audit"
echo " Output: $OUT"
echo "======================================"

echo ""
echo "== 0. Project info =="
{
  pwd
  python -V
  which python
} | tee "$OUT/00_project_info.txt"

echo ""
echo "== 1. Find model/client/config files =="
{
  echo "--- likely files ---"
  find agent -type f | grep -Ei "model|main|ollama|client|llm|provider|config|settings|planner|router|executor|brain|generation" | sort

  echo ""
  echo "--- model/client/config grep ---"
  grep -RInE "MainModel|main_model|MAIN_MODEL|TULI_MODEL|OLLAMA_MODEL|Ollama|ollama|chat\\(|generate\\(|client|model_used|model_name|base_url|api/generate|api/chat|ToolPlanner|Response|Finalizer|Router" agent 2>/dev/null || true
} > "$OUT/10_model_client_grep.txt"

echo ""
echo "== 2. Inspect config files =="
{
  echo "--- agent/config ---"
  find agent/config -type f -maxdepth 2 -print 2>/dev/null | sort

  echo ""
  for f in agent/config/*; do
    [ -f "$f" ] || continue
    echo ""
    echo "===== $f ====="
    sed -n '1,220p' "$f"
  done

  echo ""
  echo "--- root config files ---"
  for f in .env .env.local pyproject.toml setup.cfg setup.py requirements.txt; do
    [ -f "$f" ] || continue
    echo ""
    echo "===== $f ====="
    sed -n '1,220p' "$f"
  done
} > "$OUT/20_config_files.txt"

echo ""
echo "== 3. Inspect likely MainModel / model client source files =="
{
  for f in $(find agent -type f | grep -Ei "model|ollama|client|llm|provider|planner|finalizer|response" | sort); do
    echo ""
    echo "===== $f ====="
    sed -n '1,260p' "$f"
  done
} > "$OUT/30_likely_sources.txt"

echo ""
echo "== 4. Inspect action macro path and resolver =="
{
  echo "===== resolver current ====="
  sed -n '1,260p' agent/action_macros/open_ended_search_resolver.py 2>/dev/null || true

  echo ""
  echo "===== play_random_youtube_video ====="
  sed -n '1,180p' agent/action_macros/definitions/play_random_youtube_video.py 2>/dev/null || true

  echo ""
  echo "===== open_browser_and_search ====="
  sed -n '1,180p' agent/action_macros/definitions/open_browser_and_search.py 2>/dev/null || true

  echo ""
  echo "===== selector ====="
  sed -n '1,280p' agent/action_macros/selector.py 2>/dev/null || true

  echo ""
  echo "===== macro executor ====="
  sed -n '1,260p' agent/action_macros/executor.py 2>/dev/null || true
} > "$OUT/40_action_macro_path.txt"

echo ""
echo "== 5. Runtime import probe for model classes/functions =="
cat > "$OUT/probe_main_model_imports.py" <<'PY'
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
PY

PYTHONPATH="$PWD" python "$OUT/probe_main_model_imports.py" > "$OUT/50_probe_main_model_imports.txt" 2> "$OUT/50_probe_main_model_imports.err"

cat "$OUT/50_probe_main_model_imports.err"
cat "$OUT/50_probe_main_model_imports.txt"

echo ""
echo "== 6. Runtime probe: instantiate likely model classes safely =="
cat > "$OUT/probe_model_runtime.py" <<'PY'
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
PY

PYTHONPATH="$PWD" python "$OUT/probe_model_runtime.py" > "$OUT/60_probe_model_runtime.txt" 2> "$OUT/60_probe_model_runtime.err"

cat "$OUT/60_probe_model_runtime.err"
cat "$OUT/60_probe_model_runtime.txt"

echo ""
echo "== 7. Build findings =="
python - <<PY > "$OUT/99_findings.txt"
from pathlib import Path
out = Path("$OUT")

def read(name):
    p = out / name
    return p.read_text(errors="ignore") if p.exists() else ""

grep = read("10_model_client_grep.txt")
imports = read("50_probe_main_model_imports.txt")
runtime = read("60_probe_model_runtime.txt")
action = read("40_action_macro_path.txt")
config = read("20_config_files.txt")

findings = []

if "Ollama" in grep or "ollama" in grep:
    findings.append("FOUND: Ollama/main model references exist in code.")
else:
    findings.append("MISSING: No obvious Ollama/main model references found.")

if "MainModel" in grep or "main_model" in grep or "MAIN_MODEL" in grep:
    findings.append("FOUND: MainModel/main_model naming appears in code/config.")
else:
    findings.append("CHECK: No direct MainModel name found; model may be wrapped under planner/client/controller.")

if "ToolPlanner" in grep:
    findings.append("FOUND: ToolPlanner exists and may already call the main model.")
else:
    findings.append("CHECK: ToolPlanner not found by grep.")

if "api/generate" in grep or "api/chat" in grep:
    findings.append("FOUND: Direct Ollama HTTP usage exists somewhere in code.")
else:
    findings.append("CHECK: No direct Ollama HTTP endpoint found; may use ollama Python package.")

if "instantiate: OK" in runtime:
    findings.append("FOUND: At least one model/planner class can instantiate without args; inspect 60_probe_model_runtime.txt.")
else:
    findings.append("CHECK: No likely model class instantiated cleanly; inspect constructors/signatures.")

if "resolve_open_ended_search_query" in action and "_query_from_local_model" in action:
    findings.append("CURRENT: Resolver has its own local-model function; this should be replaced/wired to the main model API.")
else:
    findings.append("CURRENT: Resolver does not yet show own local model function in inspected path.")

if "model_used" in grep:
    findings.append("FOUND: model_used debug traces exist; can use those to confirm resolver uses same model later.")

print("\\n".join("- " + f for f in findings))
PY

cat "$OUT/99_findings.txt"

echo ""
echo "======================================"
echo "DONE"
echo "Report folder: $OUT"
echo ""
echo "Paste these:"
echo "cat $OUT/99_findings.txt"
echo "cat $OUT/50_probe_main_model_imports.txt | tail -160"
echo "cat $OUT/60_probe_model_runtime.txt"
echo "grep -RInE 'class .*Model|def .*generate|def .*chat|model_used|ollama|api/generate|api/chat|ToolPlanner' agent | head -160"
echo "======================================"
