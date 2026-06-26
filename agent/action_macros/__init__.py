from agent.action_macros.executor import ActionMacroExecutor
from agent.action_macros.finalizer import (
    ActionMacroFinalizer,
    ActionMacroFinalizerResult,
)
from agent.action_macros.definitions import (
    OpenAppAndTileWindowWorkflow as OpenAppAndTileWindowWorkflowDef,
    OpenBrowserAndSearchWorkflow as OpenBrowserAndSearchWorkflowDef,
    OpenWorkSetupWorkflow as OpenWorkSetupWorkflowDef,
    PlayRandomYoutubeVideoWorkflow as PlayRandomYoutubeVideoWorkflowDef,
    TileActiveWindowWorkflow as TileActiveWindowWorkflowDef,
)
from agent.action_macros.registry import ActionMacroRegistry
from agent.action_macros.schemas import (
    ActionMacroPlan,
    ActionMacroResult,
    ActionMacroStepResult,
)
from agent.action_macros.selector import ActionMacroSelector


WorkflowExecutor = ActionMacroExecutor
WorkflowFinalizer = ActionMacroFinalizer
WorkflowFinalizerResult = ActionMacroFinalizerResult
WorkflowRegistry = ActionMacroRegistry
WorkflowPlan = ActionMacroPlan
WorkflowResult = ActionMacroResult
WorkflowStepResult = ActionMacroStepResult
WorkflowSelector = ActionMacroSelector
OpenAppAndTileWindowWorkflow = OpenAppAndTileWindowWorkflowDef
OpenBrowserAndSearchWorkflow = OpenBrowserAndSearchWorkflowDef
OpenWorkSetupWorkflow = OpenWorkSetupWorkflowDef
PlayRandomYoutubeVideoWorkflow = PlayRandomYoutubeVideoWorkflowDef
TileActiveWindowWorkflow = TileActiveWindowWorkflowDef
