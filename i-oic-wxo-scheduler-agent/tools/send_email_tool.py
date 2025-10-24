import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pydantic import BaseModel, Field
from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
import os

class EmailResponse(BaseModel):
    message: str = Field(description="Result of sending the email.")


@tool(
    name= "send_email_notification",
    permission=ToolPermission.READ_ONLY,
    description="Send an email notification to a specified users."
)
def send_email_notification(to_email: str, quote: str) -> EmailResponse:
    """
    Sends an email using SMTP.
    You can configure this to use Gmail SMTP or any internal SMTP relay.
    """

    try:
        # SMTP configuration
        smtp_server = os.getenv("SMTP_SERVER", "example.ibm.com")
        smtp_port = os.getenv("SMTP_PORT", "25")
        sender_email = os.getenv("SENDER_EMAIL", "yourname@in.ibm.com")
        # Create message
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = to_email
        msg["Subject"] = "Wxo Scheduler Testing"
        msg.attach(MIMEText(quote, "plain"))


        # Send mail
        with smtplib.SMTP(smtp_server,smtp_port) as server:
            server.starttls()
            server.send_message(msg)

        return EmailResponse(message=f"Email sent successfully to {to_email}")

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        return EmailResponse(message=f"Error sending email: {repr(e)}\nTraceback:\n{tb}")

