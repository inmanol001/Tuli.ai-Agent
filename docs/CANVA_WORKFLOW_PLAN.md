# Canva Workflow Plan

This document describes the conceptual base for the future Canva workflow.

It is intentionally not implemented yet. No real Canva tools are active in the codebase at this stage.

## Goal

The Canva workflow will sit on top of the existing agentic execution stack:

- `WorkflowPlanManager`
- `RequirementChecker`
- `HumanCheckpointManager`
- `WorkflowLoopController`
- `ActionRunner`
- `ActionMacroExecutor`

That means Canva will not be a special one-off path. It will be a normal workflow with live planning, requirement checks, human checkpoints, and structured execution.

## Future tools

The following tools are expected for the Canva layer:

- `open_canva`
- `canva_search_template`
- `canva_create_design`
- `canva_insert_text`
- `canva_upload_image`
- `take_screenshot`
- `screen_analysis`
- `canva_verify_design_state`
- `canva_export_design`

These names are reserved as a conceptual target only. They are not implemented yet.

## Future workflow shape

The intended Canva workflow will look like this:

1. Receive the user goal.
2. Ask for format, style, or assets if important details are missing.
3. Create a live workflow plan.
4. Open Canva.
5. Search for a suitable template.
6. Insert text and other content.
7. Take a screenshot.
8. Validate the result visually.
9. Ask the user for approval when needed.
10. Apply corrections if the user asks for changes.
11. Export the final design.

## Design principles

- The workflow must use the same human-in-the-loop system as the rest of the agent.
- The workflow must not call `Executor.execute()` directly.
- The workflow must route tools through `ActionRunner`.
- The workflow must keep plan state, checkpoints, and retries visible in structured form.
- The workflow must be able to pause and resume cleanly.

## Notes

- This document is only a conceptual contract.
- It does not activate Canva behavior.
- It does not add real Canva integrations.
