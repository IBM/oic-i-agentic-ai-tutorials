import os
import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)

try:
    from .agent_executor import HRAgentExecutor
except ImportError:
    from agent_executor import HRAgentExecutor


if __name__ == '__main__':
    # Get configuration from environment
    PORT = int(os.getenv('PORT', '8080'))

    # Handle Code Engine environment
    CE_SUBDOMAIN = os.getenv('CE_SUBDOMAIN', '')
    CE_DOMAIN = os.getenv('CE_DOMAIN', '')

    if CE_SUBDOMAIN and CE_DOMAIN:
        PUBLIC_URL = f'https://{CE_SUBDOMAIN}.{CE_DOMAIN}/'
    else:
        PUBLIC_URL = os.getenv('PUBLIC_URL', f'http://localhost:{PORT}/')
        if not PUBLIC_URL.endswith('/'):
            PUBLIC_URL += '/'

    # Define the HR agent skill
    onboarding_skill = AgentSkill(
        id='employee_onboarding',
        name='Employee Onboarding',
        description='Creates employee records from natural language onboarding requests',
        tags=['hr', 'onboarding', 'employee'],
        examples=[
            'Onboard Sarah Williams as a Software Engineer',
            'Onboard John Smith as Senior Data Analyst',
            'Onboard Maria Garcia as Product Manager'
        ],
    )

    # Create the public-facing agent card
    public_agent_card = AgentCard(
        name='HR Agent',
        description='HR agent that creates employee records from natural language',
        url=PUBLIC_URL,
        version='1.0.0',
        default_input_modes=['text'],
        default_output_modes=['text'],
        capabilities=AgentCapabilities(streaming=True),
        skills=[onboarding_skill],
        supports_authenticated_extended_card=False,
    )

    # Create request handler with HR agent executor
    request_handler = DefaultRequestHandler(
        agent_executor=HRAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    # Build the A2A server application
    server = A2AStarletteApplication(
        agent_card=public_agent_card,
        http_handler=request_handler,
    )

    print(f"Starting HR Agent on port {PORT}")
    print(f"Agent Card: {PUBLIC_URL}.well-known/agent-card.json")
    uvicorn.run(server.build(), host='0.0.0.0', port=PORT)
