# AGENTS.md

Guidance for AI coding agents working on this repository.

## Project intent

Tuli.ai Agent is a local AI agent MVP. The project should evolve through small, safe, testable changes.

The main goal is to improve the agent's ability to route intent, execute tools, manage workflows, and learn from memory without adding unnecessary patches or duplicated logic.

## Working rules

- Do not commit directly to `main`.
- Create one focused branch per task.
- Keep pull requests small and reviewable.
- Prefer tests before refactors.
- Do not add duplicate regex patches when an existing rule can be cleaned or generalized.
- Preserve current behavior unless the task explicitly asks to change it.
- Avoid broad rewrites without first adding characterization tests.
- Do not claim that a tool/action executed unless there is a real tool result proving it.

## Recommended validation

Before opening a PR, run:

```bash
python -m compileall agent
pytest
```

If a test cannot run because it needs macOS, Ollama, or a local tool, document that clearly in the PR.

## Router guidelines

- Router fixes should include tests for the user phrases being corrected.
- Deterministic guards are acceptable for known capabilities, but duplicated guards should be removed.
- The router should classify intent; it should not become an unmaintainable list of one-off patches.
- If a capability grows, prefer moving it toward a capability registry instead of adding more inline logic.

## Memory guidelines

- Treat user memory separately from action routing.
- Questions like "what do you remember about me?" should not trigger tool execution.
- Memory writes should be explicit, debuggable, and safe.

## Tool/action guidelines

- Always distinguish between planning an action and executing a tool.
- Final responses must not say an action succeeded unless `tool_result.success` is true.
- If the planner fails to generate a valid tool call, return a clear error instead of pretending success.

## PR style

Each PR should include:

- Summary
- Files changed
- Tests run
- Any limitations or local-only checks
