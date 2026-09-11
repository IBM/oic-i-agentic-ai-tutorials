from ast import literal_eval
from dataclasses import dataclass
from enum import Enum
import json
import sys
import textwrap
from typing import Dict, List, Optional, Tuple, Union

from tabulate import tabulate
import typer

from agent_ready_tools.clients.swagger_client import WxOSwaggerClient
from agent_ready_tools.utils.archer_api_data.api_data_parser import (
    ChatMessage,
    ChatThread,
    InterlocutorRole,
    StepDetail,
    StepHistory,
    StepType,
    ToolCalls,
    WxOApiDataParser,
)
from agent_ready_tools.utils.date_conversion import format_datetime

app = typer.Typer()


class DeploymentEnvironment(Enum):
    """Represents the different WXO software deployment environments."""

    LOCAL = "http://localhost:4321"
    DEV_WA = "https://dev-wa.watson-orchestrate.ibm.com/"
    STAGING_WA = "https://archer.staging-wa.watson-orchestrate.ibm.com"


@dataclass(frozen=True)
class AgentStep:
    """Represents a step in the agent's "reasoning" process."""

    name: str
    content: Optional[Union[Dict, str]]
    "Content can either be a message or a tool response."
    args: Dict
    is_duplicate: bool
    "ToolCalls Step is a duplicate that shouldn't be displayed."


@dataclass(frozen=True)
class DialogueTurn:
    """Represents a turn in dialogue."""

    role: InterlocutorRole
    text: str
    steps: Optional[List[AgentStep]]


class WxOApiDataNormalizer:
    """Parse data from the watsonx Orchestrate Server API."""

    @classmethod
    def normalize_messages(cls, chat_messages: List[ChatMessage]) -> List[DialogueTurn]:
        """
        Normalize API Messages into a standard format.

        API ChatMessage data contains different types which have slight changes in structure.
        Flatten these into a single format.

        Args:
            chat_messages: a list of ChatMessage objects.

        Returns:
            A list of normalized dialogue turns and their steps.
        """

        dialogue_turns: List[DialogueTurn] = []
        for turn in chat_messages:

            text = turn.content[0].text
            role = turn.role
            steps = None

            assert isinstance(role, InterlocutorRole)
            assert isinstance(text, str)

            step_history = turn.step_history
            if step_history and step_history is not None:
                steps = cls._normalize_step_history(step_history)

            dialogue_turns.append(
                DialogueTurn(
                    role=role,
                    text=text,
                    steps=steps,
                )
            )

        return dialogue_turns

    @classmethod
    def tools_calls_is_duplicate(
        cls, tools_call_step: ToolCalls, step_details: List[StepDetail]
    ) -> bool:
        """
        Determine whether a ToolsCalls is a duplicate of an earlier StepDetail.

        Assumption:
        While they are included in the chat messages, ToolsCalls are generally not
        displayed as individual reasoning steps in the web UI unless when there is not an
        analogous StepDetail.
        """
        if not tools_call_step.args:
            return False
        for step_detail in step_details:
            if step_detail.tool_calls is None:
                continue

            # Once a ToolCalls Step hits itself, stop searching for its duplicate.
            if step_detail.type is StepType.TOOL_CALLS and step_detail is tools_call_step:
                return False

            elif step_detail.type is StepType.TOOL_CALL:
                if not step_detail.name == tools_call_step.name:
                    continue

                # Tool_Calls do not have content by default.
                # So if the step_details, also doesn't have it. It means they're duplicates.
                if not step_detail.content:
                    return False

                if not step_detail.args == tools_call_step.args:
                    return False

        return True

    @classmethod
    def _normalize_step_history(cls, step_history: List[StepHistory]) -> List[AgentStep]:
        """
        Normalize the step history into a standard format.

        Args:
            step_history: The steps the AI went through from the wxo Server API.

        Returns:
            A list of normalized agent steps.
        """
        steps: List[AgentStep] = []
        for record in step_history:

            step_details = record.step_details

            tool_name = None
            args = None
            content = None

            for detail in step_details:

                step_type = detail.type

                if step_type is StepType.TOOL_CALL:
                    tool_name = detail.name
                    args = detail.args

                elif step_type is StepType.TOOL_RESPONSE:
                    content = detail.content if detail.content is not None else None
                    # The 'content' field sometimes contains text or a function dict response.
                    # Try and evaluate it when it's a dict for the cleanest formatting.
                    if content is not None and content.startswith("{"):
                        try:
                            content = literal_eval(content)
                        except ValueError:
                            if content is None:
                                continue
                            content = json.loads(content)

                # ToolCalls is a list of additional tool calls.
                elif step_type is StepType.TOOL_CALLS:
                    assert (
                        detail.tool_calls is not None
                    ), "Type is Tool Calls, but there is no tool call data."
                    for tool_calls_step in detail.tool_calls:
                        assert isinstance(
                            tool_calls_step.name, str
                        ), "Tool Calls step is missing a name."

                        steps.append(
                            AgentStep(
                                name=tool_calls_step.name,
                                content={},  # StepType.TOOL_CALLS do not have content.
                                args=tool_calls_step.args,
                                is_duplicate=cls.tools_calls_is_duplicate(
                                    tool_calls_step, step_details
                                ),
                            )
                        )

            if not any((tool_name, args, content)):
                continue

            assert isinstance(tool_name, str)
            assert isinstance(args, Dict)

            steps.append(
                AgentStep(
                    name=tool_name,
                    content=content,
                    args=args,
                    is_duplicate=False,
                )
            )
        return steps


class ConversationFormatter:
    """Create a readable version of the human-AI conversation."""

    def __init__(self):

        self.formatted_conversation = []
        self.bug_report_preamble = [
            "EXPECTED BEHAVIOR",
            "What were the earliest dialogue turn and reasoning step containing something unexpected?",
            "Dialogue Turn:",
            "Reasoning Step:",
            "The expected output at this line was:",
            "\n",
        ]

    def _add_heading(self, heading: str) -> None:
        """Add Markdown H2 Header."""
        self.formatted_conversation.append(f"## {heading}")

    def _add_newline(self, number: int = 1) -> None:
        """Add one or more new lines."""
        self.formatted_conversation.extend(["\n" for _ in range(number)])

    def _create_code_block(self, code: str, language: Optional[str]) -> str:
        """Create a Markdown code block."""
        if language:
            return f"```{language}\n{code}\n```"
        return f"```\n{code}\n```"

    def _format_data(self, data: Dict) -> str:
        """Format a dictionary for printing."""
        return json.dumps(data, indent=4, ensure_ascii=False)

    def _add_speech_block(
        self, line_number: int, role: InterlocutorRole, dialogue: str, markdown: bool
    ) -> None:
        """Add a speech block."""

        formatted_role = f"{line_number}. {role.value.upper()}"

        if markdown:
            speech_block = f"**{formatted_role}**: {dialogue}"
        else:
            speech_block = f"{formatted_role}: {dialogue}"

        self.formatted_conversation.append(speech_block)

    def line_count(self, data: Union[str, Dict]) -> int:
        """Get the line count of data."""
        return len(str(data).strip().splitlines())

    def _add_step(self, step_number: int, step: AgentStep, markdown: bool) -> None:
        """Add an agent step."""

        formatted_step_number = f"Step {step_number}:"

        if markdown:
            formatted_step_number = f"**{formatted_step_number}**"

        formatted_step_number = f"\n{formatted_step_number}"

        self.formatted_conversation.append(formatted_step_number)
        self._add_newline()

        tool_name = f"Tool: {step.name}"

        self.formatted_conversation.append(tool_name)
        self._add_newline()

        tool_input = self._format_data(step.args)
        input_lines_term = "Lines" if self.line_count(tool_input) > 1 else "Line"
        self.formatted_conversation.append(
            f"Input - {self.line_count(tool_input)} {input_lines_term}"
        )
        if markdown:
            tool_input = self._create_code_block(tool_input, language="python")
        self.formatted_conversation.append(tool_input)
        self._add_newline()

        # Don't add content if there isn't any.
        if step.content is None:
            return

        if isinstance(step.content, Dict):
            tool_output = self._format_data(step.content)
        else:
            tool_output = step.content
        output_lines_term = "Lines" if self.line_count(tool_output) > 1 else "Line"
        self.formatted_conversation.append(
            f"Output - {self.line_count(tool_output)} {output_lines_term}"
        )
        if markdown:
            language = "python" if not tool_output.startswith("Transferring to") else None
            tool_output = self._create_code_block(tool_output, language=language)
        self.formatted_conversation.append(tool_output)

    def format_conversation(
        self,
        dialogue_turns: List[DialogueTurn],
        include_steps: bool,
        markdown: bool,
        bug_report: bool,
    ) -> str:
        """Create a human readable version of a human-ai interaction."""

        if bug_report:
            self.formatted_conversation.extend(self.bug_report_preamble)

        for line_number, turn in enumerate(dialogue_turns, start=1):

            if include_steps and turn.steps is not None:
                filtered_steps = [step for step in turn.steps if not step.is_duplicate]
                for num, step in enumerate(filtered_steps, start=1):
                    self._add_step(num, step, markdown)
            self._add_speech_block(
                line_number=line_number, role=turn.role, dialogue=turn.text, markdown=markdown
            )

        return "\n".join(self.formatted_conversation)


def row_selection_is_valid(row: str, threads: List[ChatThread]) -> Tuple[bool, str]:
    """Validate a thread selection is valid."""

    if not row.isnumeric():
        return False, "Please enter a number. '{row} isn't a number."

    normalized_thread_selection = int(row) - 1

    if 0 > normalized_thread_selection:
        return False, "Row number can't be lower than 0."

    if normalized_thread_selection > (len(threads) - 1):
        return False, f"Row number can't be higher than the number of threads. {len(threads)}."

    return True, "Success"


def get_thread_selection(threads: List[ChatThread]) -> str:
    """Prompt the user with a menu to select a thread."""

    thread_id = None
    while not thread_id:
        print()
        print(
            tabulate(
                [
                    [
                        "\n".join(textwrap.wrap(thread.title, width=90)),  # Opening Line.
                        format_datetime(thread.created_on),
                        format_datetime(thread.updated_at),
                        thread.id,
                    ]
                    for thread in threads
                ],
                headers=[
                    "No.",
                    "Opening Line",
                    "Created On",
                    "Updated On",
                    "Thread ID",
                ],
                showindex=range(1, len(threads) + 1),
            )
        )
        print()
        thread_selection = input("Select a thread number: ")
        print()

        row_valid, message = row_selection_is_valid(thread_selection, threads)
        if not row_valid:
            print(message)
        else:
            thread_id = threads[int(thread_selection) - 1].id

    return thread_id


@app.command()
def main(
    thread_id: Optional[str] = typer.Option(
        None, help="The ID for the conversation to print to the console."
    ),
    api_url: Optional[str] = typer.Option(
        None,
        help="The URL of the swagger API to use Eg. 'https://archer.staging-wa.watson-orchestrate.ibm.com'.",
    ),
    token: Optional[str] = typer.Option(
        None,
        help="The token to use to authenticate requests made to the WxO Swagger API. Required if api_url is in a SaaS env.",
    ),
    env_name: Optional[str] = typer.Option(
        None,
        help=f"The developer environment name. Defaults to local. Options: {[dev.name for dev in DeploymentEnvironment]}",
    ),
    markdown: bool = typer.Option(False, help="Format the conversation in markdown."),
    steps: bool = typer.Option(False, help="Include the agent's steps in the report."),
    bug_report: bool = typer.Option(True, help="Create a bug report for the report."),
) -> None:
    """Collect a conversation thread for easy viewing."""

    if api_url and "localhost" not in api_url:
        if not token:
            print("--token arg is required if non-local --api_url is provided.")
            sys.exit(1)

    if env_name and api_url:
        print("--api_url should not be provided if env_name is provided.")
        sys.exit(1)

    client_args = {}
    if api_url:
        client_args["base_url"] = api_url
    if token:
        client_args["bearer_token"] = token
    if env_name:
        try:
            client_args["base_url"] = DeploymentEnvironment[env_name.upper()].value
        except KeyError:
            print(
                f"--env_name value '{env_name}' is not a valid deployment environment. Valid options are: {[dev.name for dev in DeploymentEnvironment]}."
            )
            sys.exit(1)

    client = WxOSwaggerClient(**client_args)
    threads_response = client.get_request("api/v1/threads")

    if not thread_id:
        threads = sorted(
            WxOApiDataParser().parse_threads(threads_response),
            key=lambda thread: thread.updated_at,
            reverse=True,
        )

        if not threads:
            print(
                "Note: There are no chat threads available to export. Please chat with the agent and rerun."
            )
            sys.exit()
        thread_id = get_thread_selection(threads)

    messages_response = client.get_request(f"api/v1/threads/{thread_id}/messages")
    api_messages = WxOApiDataParser.parse_messages(messages_response)
    chat_messages = WxOApiDataNormalizer.normalize_messages(api_messages)

    conversation = ConversationFormatter().format_conversation(
        dialogue_turns=chat_messages,
        include_steps=steps,
        markdown=markdown,
        bug_report=bug_report,
    )
    print(conversation)


if __name__ == "__main__":
    app()
