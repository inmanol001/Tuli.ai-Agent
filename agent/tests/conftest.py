# ---------------------------------------------------------------------------
# Safety guard: tests must never control the real Mac.
# ---------------------------------------------------------------------------

import builtins
import os

import pytest

from agent.workflows.schemas import FullWorkflowPlan


class FakeWorkflowSelector:
    """Small shared fake used by legacy tests that reference it by name."""

    def __init__(self, plan):
        self.plan = plan
        self.calls = []

    def select(self, context):
        self.calls.append(context)
        return self.plan


# Some older tests reference these helpers without importing them. Keep them
# available through builtins while the suite is gradually cleaned up.
builtins.FullWorkflowPlan = FullWorkflowPlan
builtins.FakeWorkflowSelector = FakeWorkflowSelector


@pytest.fixture(autouse=True)
def block_real_desktop_tools_in_tests(monkeypatch):
    """
    In pytest, no test should open browser pages, launch apps, move windows,
    switch Spaces, or touch the real desktop unless it explicitly opts out.

    To opt out for a specific low-level real-tool test:
        monkeypatch.setenv("TULI_ALLOW_REAL_TOOLS_IN_TESTS", "1")
    """
    if os.environ.get("TULI_ALLOW_REAL_TOOLS_IN_TESTS") == "1":
        return

    def blocked(*args, **kwargs):
        raise AssertionError(
            "Real desktop/browser tool blocked during pytest. "
            "Use FakeExecutor/FakeTool instead of touching the real Mac."
        )

    patch_targets = [
        # Common Python browser opening
        ("webbrowser.open", blocked),
        ("webbrowser.open_new", blocked),
        ("webbrowser.open_new_tab", blocked),

        # Common subprocess path used by macOS tools
        ("subprocess.run", blocked),
        ("subprocess.Popen", blocked),
        ("subprocess.call", blocked),
        ("subprocess.check_call", blocked),
        ("subprocess.check_output", blocked),
    ]

    for dotted_name, replacement in patch_targets:
        module_name, attr = dotted_name.rsplit(".", 1)
        try:
            module = __import__(module_name)
            monkeypatch.setattr(module, attr, replacement)
        except Exception:
            pass
