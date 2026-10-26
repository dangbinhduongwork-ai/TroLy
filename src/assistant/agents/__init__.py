"""Module kiến trúc đa agent chuyên trách (spec, orchestrator)."""

from assistant.agents.orchestrator import (
    delegate_to_agent,
    get_orchestrator_router,
    run_subagent,
    set_orchestrator_router,
)
from assistant.agents.spec import (
    SPECIALIZED_AGENTS,
    AgentSpec,
    coder_agent,
    document_agent,
    file_organizer_agent,
    research_agent,
)

__all__ = [
    "AgentSpec",
    "SPECIALIZED_AGENTS",
    "file_organizer_agent",
    "document_agent",
    "research_agent",
    "coder_agent",
    "delegate_to_agent",
    "run_subagent",
    "set_orchestrator_router",
    "get_orchestrator_router",
]
