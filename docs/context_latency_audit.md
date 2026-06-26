# Context and Latency Audit

This audit is for measuring why Tuli may feel slower or overloaded before adding more memory/RAG layers.

It does not change agent behavior. It runs messages through the existing `Gateway` with `debug=True` and reports:

- total turn latency
- router latency
- context builder latency
- response controller latency
- main model latency when used
- tool planner latency when used
- action runner latency when used
- tool finalizer latency when used
- context JSON size
- selected tools, skills, RAG snippets, behavior, history, and session state sizes

## Run from local clone

```bash
cd ~/Desktop/Tuli-GitHub
source .venv/bin/activate
python3 scripts/audit_context_latency.py
```

## Run with specific messages

```bash
python3 scripts/audit_context_latency.py \
  "hola Tuli" \
  "abre github" \
  "llévame a GitHub" \
  "busca documentación de ollama" \
  "abre el primero"
```

## JSON output

```bash
python3 scripts/audit_context_latency.py --json \
  "hola Tuli" \
  "abre github" \
  "llévame a GitHub"
```

## What to look for

### Too much context

Look at:

- `context.total_json_chars`
- `context.recent_history_json_chars`
- `context.selected_skills_json_chars`
- `context.selected_tools_json_chars`
- `context.behavior_json_chars`
- `context.session_state_json_chars`

If these grow too much on simple turns, the router/main/tool planner may be carrying more context than needed.

### Slow model calls

Look at:

- `router_ms`
- `main_model_ms`
- `tool_planner_ms`
- `response_controller_ms`
- `total_ms`

If simple commands like `abre github` spend most time in `tool_planner_ms`, the next fix should route simple website actions directly or reduce tool planner context.

### Keyword vs semantic routing

Compare:

```txt
abre github
llévame a GitHub
entra a GitHub
quiero ver GitHub
muéstrame la página de OpenAI
```

They should resolve to the same action family. If only exact phrases work, the next fix should be semantic action interpretation before adding Chroma.

## Current goal

Use this audit before step 9. The goal is to make the existing base fast and reliable before adding semantic memory.
