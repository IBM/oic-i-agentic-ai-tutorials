"""
HR Agent Server - A2A Protocol Implementation

This module sets up and runs the HR Agent as an A2A-compliant server
using the official a2a-sdk. The server exposes an agent card for discovery
and handles employee onboarding requests via JSON-RPC 2.0.
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


# Load environment variables from .env file if present
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def health_check(request):
    """Health check endpoint for monitoring and load balancers."""
    return JSONResponse({"status": "healthy"})


@click.command()
@click.option('--host', 'host', default='0.0.0.0', help='Host to bind to')
@click.option('--port', 'port', default=8080, help='Port to listen on')
def main(host, port):
    """
    Start the HR Agent A2A server.

    This server implements the A2A protocol for employee onboarding,
    providing automated employee record creation from natural language requests.
    """
    try:
        # Define agent capabilities
        capabilities = AgentCapabilities(
            streaming=True,  # Support real-time status updates
            push_notifications=True  # Support push notifications
        )

        # Define the employee onboarding skill
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

        # Determine the public agent URL for the agent card
        # Priority: AGENT_URL env var > Code Engine auto-detect > localhost
        agent_url = os.getenv('AGENT_URL')
        if not agent_url:
            # Check for IBM Code Engine environment variables
            ce_subdomain = os.getenv('CE_SUBDOMAIN')
            ce_domain = os.getenv('CE_DOMAIN')
            if ce_subdomain and ce_domain:
                # Running in Code Engine - use auto-detected public URL
                agent_url = f'https://{ce_subdomain}.{ce_domain}/'
            else:
                # Local development - use host and port
                agent_url = f'http://{host}:{port}/'

        # Create the agent card for discovery
        # This will be exposed at /.well-known/agent.json
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

        # Set up HTTP client for push notifications
        httpx_client = httpx.AsyncClient()

        # Configure push notification system
        push_config_store = InMemoryPushNotificationConfigStore()
        push_sender = BasePushNotificationSender(
            httpx_client=httpx_client,
            config_store=push_config_store
        )

        # Create the request handler with all components
        request_handler = DefaultRequestHandler(
            agent_executor=HRAgentExecutor(),  # Our custom executor
            task_store=InMemoryTaskStore(),  # In-memory task storage
            push_config_store=push_config_store,
            push_sender=push_sender
        )

        # Build the A2A Starlette application
        # This automatically sets up:
        # - /.well-known/agent.json (agent card)
        # - / (JSON-RPC 2.0 endpoint)
        a2a_app = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler
        )

        # Build the Starlette app and add custom health check endpoint
        server = a2a_app.build()
        server.routes.append(Route('/health', health_check, methods=['GET']))

        # Log startup information
        logger.info(f"Starting HR Agent on {host}:{port}")
        logger.info(f"Agent URL: {agent_url}")
        logger.info(f"Agent Card: {agent_url}.well-known/agent.json")

        # Start the server
        uvicorn.run(server, host=host, port=port)

    except Exception as e:
        logger.error(f'An error occurred during server startup: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
