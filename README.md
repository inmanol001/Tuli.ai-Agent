# Tuli.ai Agent

Tuli.ai Agent is a local AI agent project focused on routing user intent, executing tools, managing workflows, and learning from memory over time.

The project is currently an MVP and is being actively developed.

## Current goals

- Build a local assistant that can understand user intent instead of relying only on keyword matching.
- Route messages into chat, actions, memory lookup, RAG lookup, safety confirmation, clarification, or refusal.
- Execute local tools and workflows safely.
- Improve behavior through persistent memory and completed-turn learning.
- Keep the system modular so routers, tools, skills, workflows, and memory can evolve independently.

## Project structure

```txt
agent/
  gateway/           Main message entrypoint and session flow
  router/            Intent routing, schema validation, and route correction
  response_action/   Response controller and action/chat orchestration
  executor/          Tool execution layer
  execution/         Action runner and retry/reflection flow
  memory/            User, tool, error, and learning memory
  workflows/         Full workflow selection, execution, and finalization
  action_macros/     Smaller reusable action sequences
  models/            Ollama-backed models, planners, and finalizers
  tests/             Test suite
```

## Requirements

- Python 3.11+
- Ollama
- Local models configured for routing and main responses

Python dependencies are declared in `pyproject.toml`.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Running tests

```bash
pytest
```

The test path is configured as:

```txt
agent/tests
```

## Development notes

This repository should prefer small, reviewable changes.

Recommended workflow:

1. Create a dedicated branch for each change.
2. Keep router fixes covered by tests.
3. Avoid adding duplicate regex patches when a capability registry or validator rule can handle the behavior more cleanly.
4. Do not merge directly to `main` without reviewing the diff.

## Near-term roadmap

- Clean duplicated router rules.
- Add more router intent tests.
- Introduce a capability registry for deterministic actions.
- Improve memory-based behavior without overloading the router.
- Document available tools, workflows, and agent commands.
