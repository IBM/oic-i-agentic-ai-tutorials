import json
import re
import time

from collections.abc import AsyncIterable
from typing import Any, Literal

from pydantic import BaseModel


class ResponseFormat(BaseModel):
    """Respond to the user in this format."""

    status: Literal['input_required', 'completed', 'error'] = 'input_required'
    message: str
    employee_data: dict | None = None


class HRAgent:
    """HRAgent - a specialized assistant for employee onboarding."""

    SYSTEM_INSTRUCTION = (
        'You are a specialized HR assistant for employee onboarding. '
        'Your sole purpose is to create employee records from natural language requests. '
        'You expect input in the format: "Onboard <Full Name> as <Job Title>". '
        'If the user asks about anything other than employee onboarding, '
        'politely state that you cannot help with that topic and can only assist with onboarding new employees.'
    )

    SUPPORTED_CONTENT_TYPES = ['text', 'text/plain']

    def __init__(self):
        pass

    async def stream(self, query: str, context_id: str) -> AsyncIterable[dict[str, Any]]:
        """Process an employee onboarding request from natural language.

        The agent expects input in the format:
            "Onboard <Full Name> as <Job Title>"

        Examples:
            - "Onboard Sarah Williams as a Software Engineer"
            - "Onboard John Smith as Senior Data Analyst"
            - "Onboard Maria Garcia as Product Manager"

        Yields status updates during processing.

        Args:
            query: Natural language onboarding request
            context_id: Context ID for tracking conversation

        Yields:
            Dictionary with task status and content
        """
        # First yield: Processing status
        yield {
            'is_task_complete': False,
            'require_user_input': False,
            'content': 'Processing employee onboarding request...\n',
        }

        # Parse the request using a flexible pattern
        name_role = re.search(
            r"Onboard\s+(.+?)\s+as\s+(?:a[n]?\s+)?(.+)$",
            query,
            re.IGNORECASE,
        )

        if not name_role:
            # If the pattern doesn't match, ask for more information
            yield {
                'is_task_complete': False,
                'require_user_input': True,
                'content': (
                    "Please provide the onboarding request in the format:\n"
                    "Onboard <Full Name> as <Job Title>\n\n"
                    "Example: Onboard Sarah Williams as a Software Engineer"
                ),
            }
            return

        # Extract and clean up the name and role
        full_name = name_role.group(1).strip().rstrip(".")
        role = name_role.group(2).strip().rstrip(".")

        # Second yield: Creating employee record
        yield {
            'is_task_complete': False,
            'require_user_input': False,
            'content': f'Creating employee record for {full_name}...\n',
        }

        # Generate an email address
        email_local = re.sub(r"[^a-z0-9]+", ".", full_name.lower())
        email = f"{email_local}@example.com"

        # Create a unique employee ID
        employee_id = f"E-{int(time.time()) % 100000:05d}"

        # Build the structured employee record
        employee = {
            "employeeId": employee_id,
            "fullName": full_name,
            "email": email,
            "jobTitle": role
        }

        # Format the response - clean output without visible JSON
        response_text = (
            "Employee onboarded successfully!\n\n"
            f"Employee ID: {employee_id}\n"
            f"Full Name: {full_name}\n"
            f"Email: {email}\n"
            f"Job Title: {role}"
        )

        # Final yield: Completed task
        yield {
            'is_task_complete': True,
            'require_user_input': False,
            'content': response_text,
            'employee_data': employee,
        }

    def get_agent_response(self, response_data: dict) -> dict:
        """Get the agent response in the expected format.

        Args:
            response_data: Response data from streaming

        Returns:
            Dictionary with task completion status
        """
        return {
            'is_task_complete': response_data.get('is_task_complete', False),
            'require_user_input': response_data.get('require_user_input', False),
            'content': response_data.get('content', ''),
        }
