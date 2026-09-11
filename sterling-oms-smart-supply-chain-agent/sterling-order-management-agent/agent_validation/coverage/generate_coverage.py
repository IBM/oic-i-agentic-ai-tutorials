import argparse
from collections import defaultdict
from dataclasses import asdict
import json
import os
from pathlib import Path
from typing import List, Optional

from agent_validation.coverage.coverage_report import AgentCoverageReport, ManagerCoverageReport
from agent_validation.util import file_system
from agent_validation.util.logger import get_logger
from import_utils.tool_importer.agent_yamls_data import AgentYamlsData
from tabulate import tabulate

MANAGER_AGENT_TEMPLATE_PATH = Path("collaborator_agents/manager_agent_template.yaml")


class GenerateCoverageReportADK:
    """A class that handles loading test suites and generate tool coverage reports from ADK test
    cases."""

    expected_fields = ["agent", "goals", "story", "goal_details"]

    def __init__(self, paths: List[str], output_dir: Optional[str] = None):
        """
        Args:
            paths: paths to test suite files or directories
            output_dir: output directory to save a JSON output of the
                coverage report
        """
        self.logger = get_logger(self.__class__.__name__)
        self.test_suite_paths = sorted(
            file_system.list_all_files(
                paths,
                file_types=[file_system.FileType.JSON],
            )
        )
        self.output_dir = output_dir

    def _verify_adk_test(self, test_case: dict) -> bool:
        """
        Checks if the test case is valid by verifying all expected fields are present. For ADK test
        cases only.

        Args:
            test_case: test case as a dictionary

        Returns:
            a boolean indicating whether it's valid
        """
        return all(f in test_case for f in self.expected_fields)

    def coverage_report_to_table(self, manager_reports: List[ManagerCoverageReport]) -> str:
        """
        Converts a list of managers' coverage reports to a table.

        Args:
            manager_reports: a list of managers' coverage reports
                containing the manager agent report and its collaborator
                agents' reports

        Returns:
            string of the coverage reports in a table format
        """
        result = []
        for manager_report in manager_reports:
            rows = []
            # Add manager row
            rows.append(
                [
                    manager_report.report.name,
                    f"{manager_report.report.tool_coverage * 100:.2f}%",
                    manager_report.report.test_count,
                    manager_report.report.tools_count,
                    manager_report.report.untested_tool_count,
                ]
            )
            # Add collaborator_reports rows
            collaborator_reports = manager_report.collaborator_reports
            for i, report in enumerate(collaborator_reports):
                prefix = "└──" if i == len(collaborator_reports) - 1 else "├──"
                rows.append(
                    [
                        f"{prefix} {report.name}",
                        f"{report.tool_coverage* 100:.2f}%",
                        f"{report.test_count if report.test_count is not None else '-'}",
                        report.tools_count,
                        report.untested_tool_count,
                    ]
                )

            table = tabulate(
                rows,
                headers=["name", "coverage", "test_count", "tools_count", "untested_tools_count"],
            )

            # Add tools not covered
            tool_list = ", ".join(manager_report.tools_not_covered)
            table += f"\n❗ Tools not covered: {tool_list}\n"
            result.append(table)

        return "\n".join(result)

    def dump_to_json(self, reports: List[ManagerCoverageReport]) -> None:
        """
        Dump a list of coverage reports to a JSON file.

        Args:
            reports: A list of manager coverage reports, containing
                coverage data for the manager and its collaborator
                agents
        """
        if self.output_dir:

            json_output = {r.report.name: asdict(r) for r in reports}

            output_path = os.path.join(self.output_dir, "coverage.json")
            self.logger.info(f"Saving coverage report to {output_path}.")
            with open(output_path, "w") as fp:
                json.dump(json_output, fp, indent=4, sort_keys=True)

    def calculate_coverage_adk(self, test_cases: list[dict]) -> list[ManagerCoverageReport]:
        """
        Calculate test coverage given a list of ADK test cases.

        Args:
            test_cases: a list of ADK test cases

        Returns:
            a list of coverage report, one for each manager agent
        """

        # tally test count and tool calls per manager agent
        tests_per_agent: defaultdict[str, int] = defaultdict(int)

        tools_called = set()

        for test_case in test_cases:
            tests_per_agent[test_case["agent"]] += 1
            for tool in test_case.get("goal_details", {}):
                if "tool_name" in tool:
                    tools_called.add(tool["tool_name"])

        # calculate coverage for each manager agent
        manager_agents = list(tests_per_agent)

        agent_data = AgentYamlsData(manager_filepath=MANAGER_AGENT_TEMPLATE_PATH)
        coverage_reports = []

        for manager in manager_agents:
            manager_filepath = agent_data.yaml_data.get(manager, {}).get("filepath", "")
            agent_data = AgentYamlsData(manager_filepath=Path(manager_filepath))

            # calculate coverage for the manager agent
            manager_name, tools = agent_data.get_tool_dependencies()
            coverage = len(tools_called.intersection(tools)) / len(tools)

            # find tools not covered
            tools_not_covered = set(tools).difference(tools_called.intersection(tools))

            # create manager report
            manager_report = AgentCoverageReport(
                name=manager_name,
                tool_coverage=coverage,
                test_count=tests_per_agent[manager],
                tools_count=len(tools),
                untested_tool_count=len(tools_not_covered),
            )

            # caculate coverage for collaborators and create reports
            collaborator_agents = agent_data.yaml_data[manager_name]["collaborators"]
            collaborator_reports = []
            for collaborator in collaborator_agents:
                collaborator_tools = agent_data.yaml_data[collaborator]["tools"]
                tools_tested = tools_called.intersection(collaborator_tools)
                untested_tool_count = len(collaborator_tools) - len(tools_tested)
                collaborator_coverage = len(tools_tested) / len(collaborator_tools)

                report = AgentCoverageReport(
                    name=collaborator,
                    tool_coverage=collaborator_coverage,
                    test_count=None,
                    tools_count=len(collaborator_tools),
                    untested_tool_count=untested_tool_count,
                )
                collaborator_reports.append(report)

            # aggregate
            coverage_reports.append(
                ManagerCoverageReport(
                    report=manager_report,
                    tools_not_covered=list(sorted(tools_not_covered)),
                    collaborator_reports=collaborator_reports,
                )
            )

        return coverage_reports

    def run(self) -> None:
        """Runs coverage report generation from end to end."""

        self.logger.info("Running coverage calculation on ADK test cases.")

        test_cases = []
        for p in self.test_suite_paths:
            # TODO load using EvaluationData from ADK framework to verify test cases when it gets supported
            with open(p, "r") as f:
                test_case: dict = json.load(f)
            if self._verify_adk_test(test_case):
                test_cases.append(test_case)

        self.logger.info(f"{len(test_cases)} test cases loaded successfully.")
        reports = self.calculate_coverage_adk(test_cases)
        table = self.coverage_report_to_table(reports)
        self.logger.info(f"\n{table}")

        self.dump_to_json(reports)


def main() -> None:
    """Sets up arg parsing."""
    parser = argparse.ArgumentParser(description="Calculate test suite tool coverage.")
    parser.add_argument(
        "--paths",
        nargs="+",
        help="Directory or file paths for test suite",
    )

    parser.add_argument("--output_dir", help="Optional directory to dump json output")

    args = parser.parse_args()

    if args.paths is None:
        args.paths = ["agent_validation/adk_test_cases"]

    GenerateCoverageReportADK(paths=args.paths, output_dir=args.output_dir).run()


if __name__ == "__main__":
    main()
