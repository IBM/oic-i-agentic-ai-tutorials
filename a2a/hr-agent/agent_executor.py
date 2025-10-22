"""
HR Agent - Employee Onboarding Logic

This module contains the core business logic for processing employee onboarding
requests. It handles natural language input and generates structured employee records.
"""

import json
import re
import time


class HRAgent:
    """
    Handles employee onboarding through natural language processing.

    This agent accepts requests like "Onboard John Doe as Software Engineer"
    and creates employee records with auto-generated IDs and email addresses.
    """

    async def onboard_employee(self, user_text: str) -> str:
        """
        Process an employee onboarding request from natural language.

        The agent expects input in the format:
            "Onboard <Full Name> as <Job Title>"

        Examples:
            - "Onboard Sarah Williams as a Software Engineer"
            - "Onboard John Smith as Senior Data Analyst"
            - "Onboard Maria Garcia as Product Manager"

        Returns a human-readable confirmation message with embedded JSON
        that downstream systems can parse for automation.

        Args:
            user_text: Natural language onboarding request

        Returns:
            Formatted response with employee details and structured JSON
        """
        # Parse the request using a flexible pattern that handles variations
        # like "as Engineer", "as a Engineer", or "as an Engineer"
        name_role = re.search(
            r"Onboard\s+(.+?)\s+as\s+(?:a[n]?\s+)?(.+)$",
            user_text,
            re.IGNORECASE,
        )

        if not name_role:
            # If the pattern doesn't match, guide the user with an example
            return (
                "Please provide: Onboard <Full Name> as <Role>\n"
                "Example: Onboard Sarah Williams as a Software Engineer"
            )

        # Extract and clean up the name and role from the regex groups
        full_name = name_role.group(1).strip().rstrip(".")
        role = name_role.group(2).strip().rstrip(".")

        # Generate an email address by converting the name to lowercase
        # and replacing spaces/special chars with dots
        email_local = re.sub(r"[^a-z0-9]+", ".", full_name.lower())
        email = f"{email_local}@example.com"

        # Create a unique employee ID using the current timestamp
        # This ensures IDs are unique and roughly sequential
        employee_id = f"E-{int(time.time()) % 100000:05d}"

        # Build the structured employee record
        employee = {
            "employeeId": employee_id,
            "fullName": full_name,
            "email": email,
            "jobTitle": role
        }

        # Format the response with both human-readable text and machine-readable JSON
        # The JSON is wrapped in markers so downstream systems can extract it easily
        response_text = (
            "Employee onboarded successfully\n\n"
            f"• Employee ID: {employee_id}\n"
            f"• Full Name: {full_name}\n"
            f"• Email: {email}\n"
            f"• Job Title: {role}\n"
            "\n"
            "BEGIN_IT_JSON\n"
            f"{json.dumps(employee, separators=(',', ':'))}\n"
            "END_IT_JSON"
        )
        return response_text
