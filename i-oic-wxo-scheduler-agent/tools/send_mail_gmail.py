import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
from ibm_watsonx_orchestrate.run import connections
from ibm_watsonx_orchestrate.agent_builder.connections import ConnectionType
from pydantic import BaseModel, Field


class EmailResponse(BaseModel):
    message: str = Field(description="Result of sending the email.")


@tool(
    name="send_gmail_notification", 
    description="Send email using gmail",
    permission=ToolPermission.ADMIN,  # Changed from WRITE to ADMIN
    expected_credentials=[{
        "app_id": "gmail_connection", 
        "type": ConnectionType.KEY_VALUE
    }]
)
def send_gmail_notification(recipient_email: str, quote: str) -> str:
    """
    Sends an email using Gmail SMTP server.
    
    Args:
        to_email: The recipient's email address.
        quote: The body content of the email.
        
    Returns:
        Success or error message
    """
    
    try:
        # Access credentials from the key_value connection
        conn = connections.key_value("gmail_connection")
        sender_email = conn["GMAIL_USER"]
        app_password = conn["GMAIL_APP_PASSWORD"]
        
        # Create the email
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = recipient_email
        msg["Subject"] = "Wxo Scheduler Testing"
        msg.attach(MIMEText(quote, "plain"))
        
        # Connect to Gmail SMTP server
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, app_password)
        
        # Send email
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()
        
        return EmailResponse(message=f"Email sent successfully to {recipient_email}")

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        return EmailResponse(message=f"Error sending email: {repr(e)}\nTraceback:\n{tb}")
    