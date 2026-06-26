# Architecture

This codebase has moved beyond a simple MVP. The current design is an agentic system with explicit routing, execution layers, reflection, macro recipes, full workflows, live plans, and human-in-the-loop pauses.

## Core layers

### 1. Gateway
The `Gateway` is the public entry point for a user message.

- Loads or creates session state
- Runs routing
- Builds the runtime context
- Sends the request to `ResponseController`
- Records turns, memory, logs, and dev events
- Returns the final `AgentResponse`

### 2. Router
The router decides the high-level path for the turn.

Typical routes include:

- `chat`
- `clarification`
- `action_ready`
- `memory_lookup`
- `rag_lookup`
- `safety_confirmation`
- `refuse`

The router does not execute tools. It only chooses the route and related metadata.

### 3. Pipeline / `ContextPackage`
The pipeline converts the router decision plus session state into a `ContextPackage`.

`ContextPackage` is the runtime envelope used by downstream layers. It carries:

- user message
- router decision
- session state
- selected tools or knowledge snippets when applicable

### 4. `ResponseController`
`ResponseController` is the orchestration layer for a single turn.

It decides whether the turn is:

- a normal chat response
- a direct tool action
- an action macro
- a full workflow
- a clarification or safety pause

It also formats the public response and debug payloads.

### 5. `ActionRunner`
`ActionRunner` is the only module allowed to call `Executor.execute()` directly.

It wraps:

- one tool execution
- reflection
- retry logic
- stop decisions
- structured traces

### 6. `Executor`
`Executor` is the low-level tool execution boundary.

It knows how to run a single tool call, but it does not own retry policy or workflow logic.

### 7. `ReflectionChecker`
`ReflectionChecker` evaluates a tool result and decides whether to:

- retry
- stop
- continue

This is used by `ActionRunner` and anything layered above it.

## Execution types

### Tool simple
A tool simple is one direct action.

Example:

- open Chrome
- search the web
- tile a window

Execution shape:

`ResponseController -> ActionRunner -> Executor -> ReflectionChecker -> Finalizer -> Response`

### Action macro
An action macro is a fixed recipe of 2 to 5 predefined `ToolCall`s.

Rules:

- no model reasoning between steps
- the macro already knows the sequence
- each step still goes through `ActionRunner`
- if one step fails, the macro stops according to retry/reflection results

Examples:

- `play_random_youtube_video`
- `open_work_setup`
- `tile_active_window`
- `open_browser_and_search`

### Full workflow
A full workflow is a longer process with live planning, reasoning, optional validation, and human-in-the-loop pauses.

It can use:

- reasoning steps
- tools
- macros
- observation steps
- verification steps
- user prompts
- approvals

## Workflow support layers

### 8. Action Macros
Action macros are quick recipes.

They are selected by intent and expanded into a fixed list of `ToolCall`s. They are not full workflows and they do not ask the main model to reason between each step.

### 9. Full Workflows
Full workflows are structured multi-phase processes for larger tasks.

They are selected when the user intent requires planning, validation, or a staged result.

### 10. `WorkflowPlanManager`
`WorkflowPlanManager` owns the runtime workflow plan.

It can:

- create a plan
- load and save a plan
- render markdown
- update step status
- persist notes and state
- insert or skip steps
- manage human checkpoints

Each workflow execution has its own plan file under runtime storage, not a shared global project plan.

### 11. `RequirementChecker`
`RequirementChecker` checks whether the workflow has enough information to continue safely and sensibly.

It looks for:

- missing information
- user preference
- approval
- safety confirmation
- visual validation
- correction requests

It should ask only when the answer changes the result or reduces risk.

### 12. `HumanCheckpointManager`
`HumanCheckpointManager` creates and resolves pauses where the workflow needs the user.

Supported checkpoint kinds:

- `missing_info`
- `preference`
- `approval`
- `safety_confirmation`
- `visual_validation`
- `correction_request`

When the workflow pauses, the checkpoint is saved on the plan and can be resumed later.

### 13. `WorkflowLoopController`
`WorkflowLoopController` is the live execution engine for full workflows.

It runs the workflow step by step and enforces hard limits.

It coordinates:

- `ActionRunner` for tools
- `ActionMacroExecutor` for macros
- `WorkflowReasoner` for reasoning
- `HumanCheckpointManager` for pauses
- `WorkflowPlanManager` for updates

Current guardrails:

- max steps
- max tool calls
- max retries per tool
- max reasoning steps

If a limit is exceeded, the workflow stops with `workflow_limits_exceeded`.

### 14. Finalizers
Finalizers convert structured execution results into user-facing text.

There are separate finalizers for:

- tool results
- action macros
- full workflows

They should summarize what happened without pretending extra certainty.

### 15. Debug / dev events
Debug and dev events are internal observability surfaces.

They can include:

- router decisions
- context packages
- action runs
- reflection traces
- retry counts
- workflow plans
- workflow pauses

When `debug=False`, the public response should not expose internal debug detail.

## Golden rule

No module should call `Executor.execute()` directly except `ActionRunner`.

That keeps tool execution, reflection, and retries in one place.

## Definitions

### Tool simple
One direct action.

### Action macro
2 to 5 predefined `ToolCall`s, with no reasoning step between them.

### Full workflow
A longer process with a live plan, reasoning, tools, macros, observe, verify, and human-in-the-loop checkpoints.

## Ideal flow

### Normal turn

User
-> Gateway
-> Router
-> Context
-> ResponseController
-> Tool simple / Macro / Workflow
-> ActionRunner
-> Executor
-> ReflectionChecker
-> Finalizer
-> Response

### Workflow turn

Workflow starts
-> create live plan
-> RequirementChecker
-> HumanCheckpointManager if needed
-> WorkflowLoopController
-> ActionRunner / Macro / Reasoner
-> PlanManager update
-> Finalizer
-> Response

## Human-in-the-loop behavior

If a workflow pauses for missing information or approval, the pending checkpoint stays attached to the session. The next user reply should resume that workflow instead of starting a new intent, unless the user clearly changes topic or cancels the task.

## Notes

- Canva is still not implemented as a real product workflow.
- The architecture is designed so new workflows can be added without changing the execution contract for simple tools.
