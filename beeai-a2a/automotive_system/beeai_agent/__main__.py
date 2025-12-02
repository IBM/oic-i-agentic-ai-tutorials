#!/usr/bin/env python3
"""
BeeAI A2A Server - Predictive Maintenance Demo (Final Working Version)
Matches BeeAI sample pattern with RequirementAgent + ConditionalRequirement.
"""

from beeai_framework.adapters.a2a import A2AServer, A2AServerConfig
from beeai_framework.agents.requirement import RequirementAgent
from beeai_framework.agents.requirement.requirements.conditional import ConditionalRequirement
from beeai_framework.backend import ChatModel
from beeai_framework.memory import UnconstrainedMemory
from beeai_framework.middleware.trajectory import GlobalTrajectoryMiddleware
from beeai_framework.tools import Tool
from beeai_framework.adapters.a2a.agents import A2AAgent, A2AAgentUpdateEvent
from .tools_dummy import (
    get_vehicle_location,
    get_driver_schedule,
    get_dealership_slots,
    get_parts_inventory
)

def main():

    llm = ChatModel.from_name("ollama:granite4:3b")

    instructions = """
You are a Predictive Maintenance Agent.
Always use the tools provided.
Never claim the vehicle is not known.
Never ask the user for more details.

Follow this workflow:
1. Call get_vehicle_location(vehicle_id)
2. Call get_driver_schedule("driver-1")
3. Call get_dealership_slots(city_from_step_1)
4. Call get_parts_inventory("Brake Pads")

Then summarize:
- Location
- Driver availability
- Earliest dealership slot
- Parts status
"""

    agent = RequirementAgent(
        llm=llm,
        instructions=instructions,
        tools=[
            get_vehicle_location,
            get_driver_schedule,
            get_dealership_slots,
            get_parts_inventory
        ],
        # Forces at least 1 tool call at beginning
        requirements=[ConditionalRequirement(get_vehicle_location, force_at_step=1)],
        middlewares=[GlobalTrajectoryMiddleware(included=[Tool])],
        memory=UnconstrainedMemory(),
        role="Predictive Maintenance Specialist"
    )

    A2AServer(
        config=A2AServerConfig(port=9999, protocol="jsonrpc")
    ).register(
        agent,
        agent_factory=A2AAgent,
        expose_tools=True,
        send_trajectory=True
    ).serve()



if __name__ == "__main__":
    main()
