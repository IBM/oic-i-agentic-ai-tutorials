import json
import re
import time

from collections.abc import AsyncIterable
from typing import Any, Literal

from pydantic import BaseModel


class ResponseFormat(BaseModel):
    """Response format for structured output."""

    status: Literal['input_required', 'completed', 'error'] = 'input_required'
    message: str
    employee_data: dict | None = None


class HRAgent:
    """
    Simple agent that creates employee records from text like:
    "Onboard Sarah Williams as a Software Engineer"

    No LLM needed - just regex parsing and some basic logic.
    """

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
        """
        Parse the onboarding request and create an employee record.

        Expects: "Onboard <Full Name> as <Job Title>"
        Example: "Onboard Sarah Williams as a Software Engineer"

        Streams progress updates back to the caller.
        """
        # Send initial status
        yield {
            'is_task_complete': False,
            'require_user_input': False,
            'content': 'Processing employee onboarding request...\n',
        }

        # Try to parse the request - handles variations like "Onboard X as a Y" or "Onboard X as Y"
        name_role = re.search(
            r"Onboard\s+(.+?)\s+as\s+(?:a[n]?\s+)?(.+)$",
            query,
            re.IGNORECASE,
        )

        if not name_role:
            # Couldn't parse it - ask for the right format
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

        # Extract name and job title, clean up any trailing periods
        full_name = name_role.group(1).strip().rstrip(".")
        role = name_role.group(2).strip().rstrip(".")

        # Send progress update
        yield {
            'is_task_complete': False,
            'require_user_input': False,
            'content': f'Creating employee record for {full_name}...\n',
        }

        # Generate email from name (replace spaces/special chars with dots)
        email_local = re.sub(r"[^a-z0-9]+", ".", full_name.lower())
        email = f"{email_local}@example.com"

        # Simple ID generation using timestamp
        employee_id = f"E-{int(time.time()) % 100000:05d}"

        # Build the employee record
        employee = {
            "employeeId": employee_id,
            "fullName": full_name,
            "email": email,
            "jobTitle": role
        }

        # Format a nice response
        response_text = (
            "Employee onboarded successfully!\n\n"
            f"Employee ID: {employee_id}\n"
            f"Full Name: {full_name}\n"
            f"Email: {email}\n"
            f"Job Title: {role}"
        )

        # Send final result
        yield {
            'is_task_complete': True,
            'require_user_input': False,
            'content': response_text,
            'employee_data': employee,
        }

    def get_agent_response(self, response_data: dict) -> dict:
        """Extract the response in a consistent format."""
        return {
            'is_task_complete': response_data.get('is_task_complete', False),
            'require_user_input': response_data.get('require_user_input', False),
            'content': response_data.get('content', ''),
        }
