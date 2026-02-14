from beeai_framework.agents.requirement import RequirementAgent
from beeai_framework.agents.requirement.requirements.conditional import ConditionalRequirement
from beeai_framework.backend import ChatModel
from beeai_framework.memory import UnconstrainedMemory
from beeai_framework.middleware.trajectory import GlobalTrajectoryMiddleware
from beeai_framework.tools import Tool

from beeai_service.core.tools import ALL_TOOLS, get_vehicle_location
from beeai_service.config.settings import app_settings, watsonx_settings


def create_maintenance_agent() -> RequirementAgent:
    """Create and configure the predictive maintenance agent with IBM watsonx.ai"""
    
    print(f"  📊 Loading model: {app_settings.llm_model}")
    print(f"  🛠️ Tools loaded: {len(ALL_TOOLS)}")
    
    # Initialize LLM with watsonx.ai
    llm = ChatModel.from_name(
        app_settings.llm_model,
        api_key=watsonx_settings.api_key,
        url=watsonx_settings.url,
        project_id=watsonx_settings.project_id
    )
    
    # Agent instructions
    instructions = """
You are a Predictive Maintenance Agent for vehicle fleet management.
Always use the tools provided.
Never claim the vehicle is not known.
Never ask the user for more details.

Follow this workflow:
1. Call get_vehicle_location(vehicle_id) to find the vehicle's current city
2. Call get_driver_schedule("driver-1") to check driver availability
3. Call get_dealership_slots(city_from_step_1) to find available service slots
4. Call get_parts_inventory("Brake Pads") to check parts availability

Then provide a clear summary with:
- Vehicle location
- Driver availability windows
- Earliest available dealership slot
- Parts inventory status
- Recommended action plan
"""
    
    # Create agent
    agent = RequirementAgent(
        llm=llm,
        instructions=instructions,
        tools=ALL_TOOLS,
        requirements=[
            ConditionalRequirement(get_vehicle_location, force_at_step=1)
        ],
        middlewares=[
            GlobalTrajectoryMiddleware(
                included=[Tool],
                enabled=app_settings.log_intermediate_steps
            )
        ],
        memory=UnconstrainedMemory(),
        role="Predictive Maintenance Specialist"
    )
    
    print(f"  ✅ Agent initialized successfully\n")
    return agent