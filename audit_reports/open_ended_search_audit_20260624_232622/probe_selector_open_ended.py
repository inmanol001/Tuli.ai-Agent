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
