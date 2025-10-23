"""
HR Agent Executor - A2A Protocol Implementation

This module implements the AgentExecutor interface from the A2A SDK,
managing the task lifecycle for employee onboarding requests.
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
    HR Onboarding Agent Executor for A2A Protocol.

    This executor manages the lifecycle of employee onboarding tasks,
    handling streaming updates and task state transitions according
    to the A2A protocol specification.
    """

    def __init__(self):
        """Initialize the executor with an HR agent instance."""
        self.agent = HRAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Execute an employee onboarding request.

        This method processes incoming A2A messages, manages task states,
        and streams progress updates back to the client.

        Args:
            context: Request context containing user message and task info
            event_queue: Queue for publishing task state changes

        Raises:
            ServerError: If validation fails or an error occurs during execution
        """
        # Validate the incoming request
        error = self._validate_request(context)
        if error:
            raise ServerError(error=InvalidParamsError())

        # Extract the user's query from the request
        query = context.get_user_input()

        # Get or create a task for this request
        task = context.current_task
        if not task:
            task = new_task(context.message)  # type: ignore
            await event_queue.enqueue_event(task)

        # Create a task updater for managing task state
        updater = TaskUpdater(event_queue, task.id, task.contextId)

        try:
            # Stream responses from the HR agent
            async for item in self.agent.stream(query, task.contextId):
                is_task_complete = item['is_task_complete']
                require_user_input = item['require_user_input']

                if not is_task_complete and not require_user_input:
                    # Task is in progress - send status update
                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            item['content'],
                            task.contextId,
                            task.id,
                        ),
                    )
                elif require_user_input:
                    # Task needs user input - transition to input_required state
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
                    # Task is complete - add result as artifact and mark done
                    await updater.add_artifact(
                        [Part(root=TextPart(text=item['content']))],
                        name='onboarding_result',
                    )
                    await updater.complete()
                    break

        except Exception as e:
            logger.error(f'An error occurred while streaming the response: {e}')
            raise ServerError(error=InternalError()) from e

    def _validate_request(self, context: RequestContext) -> bool:
        """
        Validate the incoming request.

        Currently performs no validation (returns False = no error).
        Can be extended to validate message format, authentication, etc.

        Args:
            context: Request context to validate

        Returns:
            False if valid, error object if invalid
        """
        return False

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        """
        Cancel a running task.

        Task cancellation is not supported in this implementation.

        Args:
            context: Request context for the task to cancel
            event_queue: Event queue for publishing cancellation

        Raises:
            ServerError: Always raises UnsupportedOperationError
        """
        raise ServerError(error=UnsupportedOperationError())
