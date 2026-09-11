import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from utils import dummyemailtoken,format_text_to_html
from ibm_watsonx_orchestrate.agent_builder.tools import tool

@tool("email_expert")
def email_expert(recipient_email:str, subject:str, body:str) -> str:
    """
        You are a email expert who helps user to sends an email using SMTP to a given email. Do NOT ask the user any questions. If information seems missing or unclear, make reasonable assumptions and continue. 
      Never request clarification. Respond with a concise but complete answer.

    Args:
        recipient_email (str): Recipient's email address.
        subject (str): Subject line of the email.
        body (str): Body content of the email.

    Returns:
        str: Status message indicating success or failure.
     """
    s_email="orchestrate.watsonx.alpha.team@gmail.com"
    msg = MIMEMultipart()
    msg['From'] = s_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    html_body = format_text_to_html(body)

    msg.attach(MIMEText(html_body, 'plain'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:  
            token=dummyemailtoken()
            server.login(s_email,token)
            server.send_message(msg)
            print("Email sent successfully to "+str(recipient_email))
            return "Email sent successfully to"+str(recipient_email)
    except Exception as e:
        print(f"Failed to send email: {e}")
        return f"Failed to send email: {e}"


# email_expert(
#     recipient_email="owais.ahmad@ibm.com",
#     subject="Test Subject2",
#     body="This is a test email.2"
# )