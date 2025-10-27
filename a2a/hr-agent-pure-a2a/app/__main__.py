"""
HR Agent Server - A2A Protocol Implementation

Employee onboarding agent that implements the A2A protocol for watsonx Orchestrate.
Handles natural language requests like "Onboard John Smith as Software Engineer".
"""

import logging
import os
import sys

import click
import httpx
import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    BasePushNotificationSender,
    InMemoryPushNotificationConfigStore,
    InMemoryTaskStore,
)
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from dotenv import load_dotenv
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.agent import HRAgent
from app.agent_executor import HRAgentExecutor


load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def health_check(request):
    """Health check endpoint for container orchestration platforms."""
    return JSONResponse({"status": "healthy"})


@click.command()
@click.option('--host', 'host', default='0.0.0.0', help='Host to bind to')
@click.option('--port', 'port', default=8080, help='Port to listen on')
def main(host, port):
    """Start the HR onboarding agent server."""
    try:
        # Configure what the agent supports
        capabilities = AgentCapabilities(
            streaming=True,  # Send progress updates in real-time
            push_notifications=True  # Enable async notifications
        )

        # Define the skill exposed in the agent card
        skill = AgentSkill(
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

        # Determine the public URL for the agent
        # Priority: AGENT_URL env var > IBM Code Engine detection > localhost
        agent_url = os.getenv('AGENT_URL')
        if not agent_url:
            ce_subdomain = os.getenv('CE_SUBDOMAIN')
            ce_domain = os.getenv('CE_DOMAIN')
            if ce_subdomain and ce_domain:
                agent_url = f'https://{ce_subdomain}.{ce_domain}/'
            else:
                agent_url = f'http://{host}:{port}/'

        # Create the agent card for discovery (served at /.well-known/agent.json)
        agent_card = AgentCard(
            name='HR Agent',
            description='HR agent that creates employee records from natural language',
            url=agent_url,
            version='1.0.0',
            default_input_modes=HRAgent.SUPPORTED_CONTENT_TYPES,
            default_output_modes=HRAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[skill],
        )

        # Set up push notifications for async task updates
        httpx_client = httpx.AsyncClient()
        push_config_store = InMemoryPushNotificationConfigStore()
        push_sender = BasePushNotificationSender(
            httpx_client=httpx_client,
            config_store=push_config_store
        )

        # Wire up the request handler with our custom executor
        request_handler = DefaultRequestHandler(
            agent_executor=HRAgentExecutor(),
            task_store=InMemoryTaskStore(),  # Using in-memory storage (no persistence)
            push_config_store=push_config_store,
            push_sender=push_sender
        )

        # Initialize the A2A application
        a2a_app = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler
        )

        # Build the server and add health check endpoint
        # Note: The SDK doesn't provide /health by default, so we add it manually
        server = a2a_app.build()
        server.routes.append(Route('/health', health_check, methods=['GET']))

        logger.info(f"Starting HR Agent on {host}:{port}")
        logger.info(f"Agent URL: {agent_url}")
        logger.info(f"Agent Card: {agent_url}.well-known/agent.json")

        uvicorn.run(server, host=host, port=port)

    except Exception as e:
        logger.error(f'Startup failed: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
