import os
import requests
from pydantic import BaseModel, Field
from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission

class EmailRequest(BaseModel):
    to_email: str = Field(description="Recipient email address")
    subject: str = Field(description="Subject of the email")
    body: str = Field(description="Body text of the email")


class EmailResponse(BaseModel):
    status: str = Field(description="Status of email send request")


@tool(
    name="send_email_mailersend",
    permission=ToolPermission.READ_ONLY,
    description="Send an email using the MailerSend transactional email API.",
)
def send_email_mailersend(to_email: str, subject: str, body: str) -> EmailResponse:
    """
    Sends an email using the MailerSend API.
    Requires MAILERSEND_API_KEY and MAILERSEND_FROM_EMAIL in environment variables.
    """
    try:
        
        api_key = os.getenv("MAILERSEND_API")
        from_email = os.getenv("MAILERSEND_DOMAIN")
        if not api_key:
            return EmailResponse(status="❌ Missing MAILERSEND_API_KEY environment variable")

        url = "https://api.mailersend.com/v1/email"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "from": {"email": from_email, "name": "Watson Orchestrate Agent"},
            "to": [{"email": "<receiver email>"}],
            "subject": subject,
            "text": body
        }

        response = requests.post(url, json=payload, headers=headers, timeout=10)

        if response.status_code in [200, 202]:
            return EmailResponse(status=f"✅ Email successfully sent to {to_email}")
        else:
            return EmailResponse(
                status=f"❌ MailerSend API Error: {response.status_code} - {response.text}"
            )

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        return EmailResponse(status=f"❌ Exception: {repr(e)}\nTraceback:\n{tb}")
