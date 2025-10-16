# import smtplib
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart
# from pydantic import BaseModel, Field
# from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission


# class EmailRequest(BaseModel):
#     to_email: str = Field(description="Recipient email address")
#     subject: str = Field(description="Subject line of the email")
#     body: str = Field(description="Body text of the email")


# class EmailResponse(BaseModel):
#     status: str = Field(description="Result of email sending")


# @tool(
#     permission=ToolPermission.WRITE_ONLY,
#     description="Send an email notification to a specified users."
# )
# def send_email_notification(to_email: str, subject: str, body: str) -> str:
#     """
#     Sends an email using SMTP.
#     You can configure this to use Gmail SMTP or any internal SMTP relay.
#     """

#     try:
#         # SMTP configuration (example using Gmail)
#         SENDER_EMAIL = "askq2cerrornotif@ibm.com"  # Replace with your email

#         # Create message
#         msg = MIMEMultipart()
#         msg["From"] = SENDER_EMAIL
#         msg["To"] = "sagarn32@in.ibm.com"
#         msg["Subject"] = "test"
#         msg.attach(MIMEText(body, "plain"))

#         # Send mail
#         with smtplib.SMTP('na.relay.ibm.com',"25") as server:
#             server.starttls()
#             server.send_message(msg)

#         return EmailResponse(status=f"Email sent successfully to {to_email}")

#     except Exception as e:
#         import traceback
#         tb = traceback.format_exc()
#         return EmailResponse(status=f"Error sending email: {repr(e)}\nTraceback:\n{tb}")

# # print(send_email_notification("sagarn32@in.ibm.com", "Test Email", "Test Email Body"))

# from mailersend import emails
# from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission

# api_key = ""

# @tool(
#     permission=ToolPermission.READ_WRITE
# )
# def send_email(receiver_email: str, receiver_name: str, email_message: str):
#   """
#   Sends an email using the input parameters
#   :param receiver_email: The email address to which the email is sent to
#   :param receiver_name: The name of the person to which the email is sent to
#   :param email_message: The message to be sent
#   """
#   mailer = emails.NewEmail("mlsn.27a83c66b693c43e55af35ca90d39fa90100df37898c02a0fef2b1bd1ade25ca")

#   # define an empty dict to populate with mail values
#   mail_body = {}

#   mail_from = {
#       "name": "wxo-sdk",
#       "email": "email_addr"
#   }

#   recipients = [
#       {
#           "name": receiver_name,
#           "email": receiver_email
#       }
#   ]

#   reply_to = [
#       {
#           "name": "wxo-sdk",
#           "email": "email_addr"
#       }
#   ]

#   message_to_send = ("<h3>Hello " + receiver_name + "!</h3><p>" + email_message + "</p>")

#   mailer.set_mail_from(mail_from, mail_body)
#   mailer.set_mail_to(recipients, mail_body)
#   mailer.set_subject("Message from wxo-sdk", mail_body)
#   mailer.set_html_content(message_to_send, mail_body)
#   #mailer.set_plaintext_content("This is the text content", mail_body)
#   mailer.set_reply_to(reply_to, mail_body)

#   # using print() will also return status code and data
#   mailer.send(mail_body)



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
            "to": [{"email": "sgar3484@gmail.com"}],
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

# print(send_email_mailersend("sgar3484@gmail.com", "Test Email", "Test Email Body"))