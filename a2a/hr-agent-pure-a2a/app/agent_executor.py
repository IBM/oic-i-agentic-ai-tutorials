"""
HR Agent Executor - A2A Protocol Implementation

Bridges the A2A SDK with our HR agent logic. Handles task lifecycle,
state transitions, and streaming responses.
"""

import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    InternalError,
    InvalidParamsError,
    Part,
    TaskState,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils import (
    new_agent_text_message,
    new_task,
)
from a2a.utils.errors import ServerError

from app.agent import HRAgent


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HRAgentExecutor(AgentExecutor):
    """
    Executor that connects the A2A protocol handler to our HR agent.

    Manages task states (working -> completed/input_required) and
    streams progress updates back through the event queue.
    """

    def __init__(self):
        self.agent = HRAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Process an onboarding request and stream updates back to the client.

        Handles the full task lifecycle: creation, status updates, and completion.
        """
        # Validate the request (placeholder for future validation logic)
        error = self._validate_request(context)
        if error:
            raise ServerError(error=InvalidParamsError())

        # Get the user's message text
        query = context.get_user_input()

        # Get or create a task - each conversation turn might reuse an existing task
        task = context.current_task
        if not task:
            task = new_task(context.message)  # type: ignore
            await event_queue.enqueue_event(task)

        # TaskUpdater handles sending state changes back through the event queue
        updater = TaskUpdater(event_queue, task.id, task.contextId)

        try:
            # Process the request and stream updates
            async for item in self.agent.stream(query, task.contextId):
                is_task_complete = item['is_task_complete']
                require_user_input = item['require_user_input']

                if not is_task_complete and not require_user_input:
                    # Still working - send progress update
                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            item['content'],
                            task.contextId,
                            task.id,
                        ),
                    )
                elif require_user_input:
                    # Need more info from the user
                    await updater.update_status(
                        TaskState.input_required,
                        new_agent_text_message(
                            item['content'],
                            task.contextId,
                            task.id,
                        ),
                        final=True,
                    )
                    break
                else:
                    # All done - attach the result as an artifact
                    await updater.add_artifact(
                        [Part(root=TextPart(text=item['content']))],
                        name='onboarding_result',
                    )
                    await updater.complete()
                    break

        except Exception as e:
            logger.error(f'Error during task execution: {e}')
            raise ServerError(error=InternalError()) from e

    def _validate_request(self, context: RequestContext) -> bool:
        """
        Validate the request before processing.

        Returns False (no error) for now. Could be extended to check
        message format, authentication, rate limits, etc.
        """
        return False

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        """
        Cancel a task in progress.

        Not implemented yet - raises an error if called.
        """
        raise ServerError(error=UnsupportedOperationError())
