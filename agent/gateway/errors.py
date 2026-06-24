class AgentError(Exception):
    """Base error for the local agent."""


class ToolBlockedError(AgentError):
    """Raised when a tool is unavailable or inactive."""

