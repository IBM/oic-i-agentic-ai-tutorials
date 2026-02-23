from typing import List, Optional

from pydantic.dataclasses import dataclass


@dataclass
class AgentCoverageReport:
    """Coverage report for a single agent."""

    name: str
    tool_coverage: float
    test_count: Optional[int]
    tools_count: int = 0  # number of tools under the agent
    untested_tool_count: int = 0  # number of untested tools


@dataclass
class ManagerCoverageReport:
    """Coverage reports under a manager agent."""

    report: AgentCoverageReport
    tools_not_covered: List[str]
    collaborator_reports: List[AgentCoverageReport]
