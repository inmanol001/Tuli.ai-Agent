#!/usr/bin/env bash
set -u

OUT_DIR="audit_reports"
TS="$(date +"%Y%m%d_%H%M%S")"
OUT="$OUT_DIR/open_ended_search_audit_$TS"
mkdir -p "$OUT"

echo "======================================"
echo " Open-ended search / memory audit"
echo " Output: $OUT"
echo "======================================"

echo ""
echo "== Project info =="
{
  pwd
  python -V
  which python
} | tee "$OUT/00_project_info.txt"

echo ""
echo "== 1. Search for memory/profile/preference systems =="
{
  echo "--- files likely related to memory/profile/session ---"
  find agent -type f | grep -Ei "memory|memories|profile|preference|session|history|context|state|rag" | sort

  echo ""
  echo "--- grep memory/profile/preference terms ---"
  grep -RInE "memory|memories|remember|recuerda|profile|perfil|preference|preferences|interests|likes|gustos|session_state|recent_history|ConversationTurn|ContextPackage|short.?term|long.?term|rag|knowledge" agent 2>/dev/null || true
} > "$OUT/10_memory_profile_grep.txt"

echo ""
echo "== 2. Inspect ContextPackage and conversation turn schemas =="
{
  echo "--- agent/gateway/message_types.py ---"
  sed -n '1,240p' agent/gateway/message_types.py 2>/dev/null || true

  echo ""
  echo "--- router schema ---"
  sed -n '1,220p' agent/router/router_schema.py 2>/dev/null || true
} > "$OUT/20_context_schemas.txt"

echo ""
echo "== 3. Inspect current selector and macro definitions =="
{
  echo "--- selector.py 1-280 ---"
  sed -n '1,280p' agent/action_macros/selector.py 2>/dev/null || true

  echo ""
  echo "--- open_browser_and_search.py ---"
  sed -n '1,180p' agent/action_macros/definitions/open_browser_and_search.py 2>/dev/null || true

  echo ""
  echo "--- play_random_youtube_video.py ---"
  sed -n '1,180p' agent/action_macros/definitions/play_random_youtube_video.py 2>/dev/null || true

  echo ""
  echo "--- action macro registry ---"
  sed -n '1,160p' agent/action_macros/registry.py 2>/dev/null || true

  echo ""
  echo "--- action macro executor ---"
  sed -n '1,220p' agent/action_macros/executor.py 2>/dev/null || true
} > "$OUT/30_action_macro_current.txt"

echo ""
echo "== 4. Search for open-ended/random handling =="
{
  grep -RInE "open_ended|__open_ended__|topic_hint|random|aleatorio|al azar|cualquiera|cualquier cosa|algo interesante|sorprendeme|sorpréndeme|recomiendame|recomiéndame" agent 2>/dev/null || true
} > "$OUT/40_open_ended_grep.txt"

echo ""
echo "== 5. Search where browser_search arguments are created =="
{
  grep -RInE "tool_name=.*browser_search|browser_search|arguments=.*query|target.*youtube|target.*web|target.*auto" agent 2>/dev/null || true
} > "$OUT/50_browser_search_arg_builders.txt"

echo ""
echo "== 6. Search for model/planner places that could resolve open-ended queries =="
{
  find agent -type f | grep -Ei "model|planner|tool|router|response|context|memory|gateway" | sort

  echo ""
  grep -RInE "ToolPlanner|tool_planner|tool_calls|selected_tools|task_instruction|system_prompt|main_model|ollama|chat|generate|complete|prompt|ContextBuilder|context_builder" agent 2>/dev/null || true
} > "$OUT/60_planner_model_grep.txt"

echo ""
echo "== 7. Runtime probe: selector only, no tools executed =="
cat > "$OUT/probe_selector_open_ended.py" <<'PY'
from agent.action_macros.selector import ActionMacroSelector
from agent.action_macros.registry import ActionMacroRegistry
from agent.gateway.message_types import ContextPackage
from agent.router.router_schema import RouterDecision

selector = ActionMacroSelector()
registry = ActionMacroRegistry()

tests = [
    {
        "name": "yt_open_no_context",
        "text": "ponme un video random en YouTube",
        "state": {},
    },
    {
        "name": "yt_open_with_interests",
        "text": "ponme un video random en YouTube",
        "state": {"interests": "Me gustan los agentes de IA locales, Ollama, tool calling, tecnología, diseño y misterio."},
    },
    {
        "name": "yt_open_topic",
        "text": "ponme un video random de misterio en YouTube",
        "state": {"interests": "Me gustan los agentes de IA locales y tecnología."},
    },
    {
        "name": "web_open_with_interests",
        "text": "busca algo interesante",
        "state": {"interests": "Me gustan Python, programación, diseño y agentes de IA locales."},
    },
    {
        "name": "yt_specific",
        "text": "busca en YouTube tutorial de Python para principiantes",
        "state": {"interests": "Me gustan los agentes de IA locales."},
    },
]

for case in tests:
    ctx = ContextPackage(
        system_prompt="",
        user_message=case["text"],
        session_state=case["state"],
        router_decision=RouterDecision(
            intent="action",
            domain="browser",
            action="search",
            route="action_ready",
            needs_tool=True,
            suggested_tools=["browser_search"],
        ),
    )

    plan = selector.select(ctx)
    print("\n==", case["name"], "==")
    print("prompt:", case["text"])
    print("state:", case["state"])
    print("plan:", plan.model_dump())

    if plan.selected:
        try:
            macro = registry.get(plan.workflow_name)
            steps = macro.build_steps(plan.inputs)
            for step in steps:
                print("step:", step.tool_name, step.arguments)
        except Exception as e:
            print("macro_error:", repr(e))
PY

PYTHONPATH="$PWD" python "$OUT/probe_selector_open_ended.py" > "$OUT/70_probe_selector_open_ended.txt" 2> "$OUT/70_probe_selector_open_ended.err"
cat "$OUT/70_probe_selector_open_ended.err"
cat "$OUT/70_probe_selector_open_ended.txt"

echo ""
echo "== 8. Static conclusions =="
python - <<PY > "$OUT/99_findings.txt"
from pathlib import Path

out = Path("$OUT")

def read(name):
    p = out / name
    return p.read_text(errors="ignore") if p.exists() else ""

memory = read("10_memory_profile_grep.txt")
selector = read("30_action_macro_current.txt")
openended = read("40_open_ended_grep.txt")
browser = read("50_browser_search_arg_builders.txt")
probe = read("70_probe_selector_open_ended.txt")
probe_err = read("70_probe_selector_open_ended.err")

findings = []

if "session_state" in memory or "recent_history" in memory or "ContextPackage" in memory:
    findings.append("FOUND: Context/memory carriers exist: session_state/recent_history/ContextPackage appear in code.")
else:
    findings.append("MISSING: No obvious context/memory carrier found.")

if "interests" in memory or "preferences" in memory or "profile" in memory or "memory" in memory:
    findings.append("FOUND: Some memory/profile/preference terms exist in repo; inspect 10_memory_profile_grep.txt.")
else:
    findings.append("MISSING: No obvious user profile/preferences system found by grep.")

if "open_ended" in selector and "topic_hint" in selector:
    findings.append("FOUND: selector.py already emits open_ended/topic_hint metadata.")
else:
    findings.append("MISSING: selector.py does not appear to emit open_ended/topic_hint consistently.")

if "__open_ended__" in probe and "step: browser_search {'query': '__open_ended__'" in probe:
    findings.append("BUG: __open_ended__ reaches browser_search step.")
elif "__open_ended__" in probe:
    findings.append("CHECK: __open_ended__ appears in plan, but verify final step query does not send it to browser.")
else:
    findings.append("OK: __open_ended__ not found in probe output.")

if "documental corto interesante" in probe:
    findings.append("FOUND: current macro uses fixed fallback for empty open-ended YouTube requests.")
else:
    findings.append("CHECK: no fixed fallback detected in probe output.")

if "macro_error" in probe or probe_err.strip():
    findings.append("BUG: selector/macro probe has errors. See 70_probe_selector_open_ended.err and output.")

if "user_context" in selector:
    findings.append("FOUND: user_context already appears in selector/macro current code.")
else:
    findings.append("MISSING: user_context is not currently passed from selector to macros.")

if "resolve_open_ended_search_query" in browser:
    findings.append("FOUND: a resolver function already exists or is referenced.")
else:
    findings.append("MISSING: no open-ended resolver currently wired into browser_search macro builders.")

print("\\n".join("- " + f for f in findings))
PY

cat "$OUT/99_findings.txt"

echo ""
echo "======================================"
echo "DONE"
echo "Report folder: $OUT"
echo ""
echo "Main files to paste:"
echo "cat $OUT/99_findings.txt"
echo "cat $OUT/70_probe_selector_open_ended.txt"
echo "cat $OUT/10_memory_profile_grep.txt | head -120"
echo "======================================"
