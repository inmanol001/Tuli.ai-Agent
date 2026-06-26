#!/usr/bin/env bash
set -u

OUT_DIR="audit_reports"
TS="$(date +"%Y%m%d_%H%M%S")"
OUT="$OUT_DIR/suspects_audit_$TS"
mkdir -p "$OUT"

echo "======================================"
echo " Tuli suspects audit"
echo " Output: $OUT"
echo "======================================"

echo ""
echo "== Python / project info =="
{
  pwd
  python -V
  which python
  echo ""
  find agent -maxdepth 3 -type f | sort | sed 's#^\./##' | head -300
} | tee "$OUT/00_project_info.txt"

echo ""
echo "== py_compile =="
python -m py_compile $(find agent -name "*.py") > "$OUT/01_py_compile.txt" 2>&1
PY_COMPILE_STATUS=$?
cat "$OUT/01_py_compile.txt"
echo "py_compile_status=$PY_COMPILE_STATUS" | tee -a "$OUT/01_py_compile.txt"

echo ""
echo "== Suspect 1: Router / RouterValidator files =="
{
  echo "--- router files ---"
  find agent/router -type f -maxdepth 3 -print | sort
  echo ""
  echo "--- grep mission/window/youtube/canva/action_ready/chat/clarification ---"
  grep -RInE "mission control|mision control|misión control|macos_space|window_native_tiling|youtube|YouTube|canva|Canva|action_ready|clarification|needs_tool|route *=|route=|suggested_tools|pending_confirmation|confirm" agent/router agent/gateway agent/response_action 2>/dev/null || true
} > "$OUT/10_router_grep.txt"

echo ""
echo "== Suspect 2: Finalizer / chat response =="
{
  echo "--- finalizer/response files ---"
  find agent -type f | grep -Ei "finalizer|response|controller|chat" | sort
  echo ""
  echo "--- grep execution claims ---"
  grep -RInE "se ha activado|activado correctamente|estoy ejecutando|ejecutado correctamente|se ha abierto|he abierto|abrí|abriré|envié la acción|tool_result|final_tool_result|no_tool|No ejecuté|sin tool|tool_call" agent/response_action agent/gateway agent/models agent/action_macros agent/workflows 2>/dev/null || true
} > "$OUT/20_finalizer_grep.txt"

echo ""
echo "== Suspect 3: Skills instructions =="
{
  echo "--- skills files ---"
  find agent -type f \( -iname "*skill*" -o -iname "SKILL.md" -o -path "*skills*" \) -print | sort
  echo ""
  echo "--- all skill headings/rules ---"
  grep -RInE "^#|Cuándo usar|No uses|Reglas|Mission Control|mission control|mision control|youtube|YouTube|random|azar|cualquiera|claración|aclaración|tool_result|No respondas|No digas|low-risk|permission|confirm" agent 2>/dev/null | grep -Ei "skill|skills|SKILL|browser_search|macos" || true
} > "$OUT/30_skills_grep.txt"

echo ""
echo "== Suspect 4: Action macros =="
{
  echo "--- action macro files ---"
  find agent/action_macros -type f -print | sort
  echo ""
  echo "--- grep macro selection/order/tools ---"
  grep -RInE "play_random_youtube|youtube|browser_search|open_browser|open_work|tile_active|window|open_url|ToolCall|selected|workflow_name|looks_like|random|azar|cualquiera|action_runner|executor" agent/action_macros 2>/dev/null || true
} > "$OUT/40_macros_grep.txt"

echo ""
echo "== Suspect 5: Pending confirmation / pending action =="
{
  grep -RInE "pending_confirmation|pending_action|pending_workflow|pending_clarification|confirmation|needs_confirmation|confirm|sí|si activalo|approval" agent 2>/dev/null || true
} > "$OUT/50_pending_grep.txt"

echo ""
echo "== Suspect 6: ToolPlanner =="
{
  find agent -type f | grep -Ei "tool.*planner|planner|tools" | sort
  echo ""
  grep -RInE "class ToolPlanner|tool_calls|no_native_tool_call|no_tool_reason|browser_search|open_app|window_native_tiling|macos_space|selected_tools|task_instruction|system_prompt|raw|ollama|llama3-groq|xlam" agent 2>/dev/null || true
} > "$OUT/60_toolplanner_grep.txt"

echo ""
echo "== Suspect 7: Workflows / RequirementChecker =="
{
  find agent/workflows -type f -print | sort
  echo ""
  grep -RInE "RequirementChecker|design_canva|canva|Canva|missing_info|needs_user_input|waiting_user_input|waiting_approval|format|style|topic|FullWorkflowRunner|WorkflowLoopController|phases|create_plan|check" agent/workflows agent/response_action agent/router 2>/dev/null || true
} > "$OUT/70_workflows_grep.txt"

echo ""
echo "== Executor direct calls check =="
{
  grep -RInE "\.execute\(.*tool|executor\.execute|self\.executor\.execute|Executor\(" agent 2>/dev/null || true
} > "$OUT/80_executor_calls.txt"

echo ""
echo "== Router-only deterministic test =="
cat > "$OUT/router_probe.py" <<'PY'
import json
from agent.router.xlam_router import XlamRouter

tests = [
    # Mission Control
    "activa mission control",
    "abre mision control",
    "activa tu mission control",
    "mostrar mission control",
    "open mission control",
    # Spaces
    "cambia al siguiente escritorio",
    "vuelve al escritorio anterior",
    "en qué escritorio estoy",
    # Windows
    "mueve la ventana activa a la derecha",
    "mueve la ventana activa a la izquierda",
    "move the active window to the left",
    "center the active window",
    # Browser / YouTube
    "ponme un video random en YouTube",
    "ponme un video random de tecnología en YouTube",
    "busca en YouTube un video de inteligencia artificial",
    "busca en internet noticias de inteligencia artificial",
    "abre https://chatgpt.com",
    # Canva
    "haz un post en Canva del día del padre",
    "hazme un post en Canva para Bellamar",
    "créame un diseño en Canva para una promoción de Bellamar",
    "diseñame un flyer en Canva",
    # Ambiguous
    "busca algo",
    "mueve la ventana",
]

router = XlamRouter()

rows = []
for text in tests:
    try:
        result = router.route(text)
        d = result.decision.model_dump()
        rows.append({
            "prompt": text,
            "intent": d.get("intent"),
            "domain": d.get("domain"),
            "action": d.get("action"),
            "route": d.get("route"),
            "needs_tool": d.get("needs_tool"),
            "needs_clarification": d.get("needs_clarification"),
            "missing_info": d.get("missing_info"),
            "suggested_plugins": d.get("suggested_plugins"),
            "suggested_skills": d.get("suggested_skills"),
            "suggested_tools": d.get("suggested_tools"),
            "model_used": getattr(result, "model_used", None),
            "corrected": getattr(result, "corrected", None),
            "raw": getattr(result, "raw", None),
            "error": getattr(result, "error", None),
        })
    except Exception as e:
        rows.append({"prompt": text, "error": repr(e)})

print(json.dumps(rows, indent=2, ensure_ascii=False))
PY

python "$OUT/router_probe.py" > "$OUT/90_router_probe.json" 2> "$OUT/90_router_probe.stderr"
ROUTER_STATUS=$?
echo "router_probe_status=$ROUTER_STATUS" > "$OUT/90_router_probe.status"

python - <<PY > "$OUT/91_router_probe_summary.txt"
import json
from pathlib import Path
p = Path("$OUT/90_router_probe.json")
try:
    rows = json.loads(p.read_text())
except Exception as e:
    print("Could not parse router probe:", e)
    raise SystemExit(0)

for r in rows:
    print(
        f"{r.get('prompt')} | route={r.get('route')} | action={r.get('action')} | "
        f"needs_tool={r.get('needs_tool')} | needs_clarification={r.get('needs_clarification')} | "
        f"tools={r.get('suggested_tools')} | missing={r.get('missing_info')} | corrected={r.get('corrected')}"
    )
PY

cat "$OUT/91_router_probe_summary.txt"

echo ""
echo "== Static bug detector =="
python - <<PY > "$OUT/99_findings.txt"
import json
from pathlib import Path

out = Path("$OUT")
findings = []

def read(name):
    p = out / name
    return p.read_text(errors="ignore") if p.exists() else ""

router_summary = read("91_router_probe_summary.txt")
router_grep = read("10_router_grep.txt")
finalizer_grep = read("20_finalizer_grep.txt")
skills_grep = read("30_skills_grep.txt")
macros_grep = read("40_macros_grep.txt")
pending_grep = read("50_pending_grep.txt")
executor_calls = read("80_executor_calls.txt")

for line in router_summary.splitlines():
    low = line.lower()
    if "mission control" in low or "mision control" in low:
        if "route=action_ready" not in line or "macos_space_mission_control" not in line:
            findings.append("BUG: Mission Control prompt not routed to macos_space_mission_control: " + line)
    if "youtube" in low and "random" in low:
        if "route=clarification" in line or "needs_tool=True" not in line:
            findings.append("BUG: YouTube random may not route directly to browser_search/macro: " + line)
    if "hazme un post en canva" in low or "créame" in low or "diseñame" in low:
        if "route=chat" in line:
            findings.append("BUG: Canva creative prompt routed to chat: " + line)
    if "move the active window to the left" in low:
        if "window_native_tiling" not in line:
            findings.append("BUG: English window command not routed to window_native_tiling: " + line)

if "se ha activado" in finalizer_grep or "activado correctamente" in finalizer_grep or "estoy ejecutando" in finalizer_grep:
    findings.append("CHECK: Finalizer/chat contains execution-claim phrases. Verify guarded by tool_result.")

if "open_url" in macros_grep:
    findings.append("CHECK: Action macros reference open_url. Verify open_url is active/declared or replace it.")

if "pending_confirmation" not in pending_grep and "pending_action" not in pending_grep:
    findings.append("CHECK: No obvious pending confirmation/action implementation found.")

bad_executor_lines = []
for line in executor_calls.splitlines():
    if "agent/execution/action_runner.py" not in line and "test" not in line.lower():
        bad_executor_lines.append(line)
if bad_executor_lines:
    findings.append("BUG: Possible direct Executor.execute calls outside ActionRunner:\\n" + "\\n".join(bad_executor_lines[:20]))

if not findings:
    findings.append("No obvious static findings. Review grep files manually.")

print("\\n".join(f"- {f}" for f in findings))
PY

cat "$OUT/99_findings.txt"

echo ""
echo "======================================"
echo "DONE"
echo "Report folder: $OUT"
echo "Main files:"
echo "  $OUT/91_router_probe_summary.txt"
echo "  $OUT/99_findings.txt"
echo "  $OUT/10_router_grep.txt"
echo "  $OUT/20_finalizer_grep.txt"
echo "  $OUT/30_skills_grep.txt"
echo "  $OUT/40_macros_grep.txt"
echo "======================================"
