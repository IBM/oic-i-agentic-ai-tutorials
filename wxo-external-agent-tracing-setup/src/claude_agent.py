import os
import anthropic

client = anthropic.Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"]
)

AGENT_ID = "agent_01GKq3KC6L1BpJfqqoCrnZ8p"
ENVIRONMENT_ID = "env_0127KSYtpGVMoMStTmF3rzK9"

# Create a session and start the first task
session = client.beta.sessions.create(
    agent=AGENT_ID,
    environment_id=ENVIRONMENT_ID,
    title="WXO observability test",
    initial_events=[
        {
            "type": "user.message",
            "content": [
                {
                    "type": "text",
                    "text": "Hello! Explain your purpose in one sentence."
                }
            ],
        }
    ],
)

print("Agent ID:", AGENT_ID)
print("Session ID:", session.id)
print("Task submitted successfully.")