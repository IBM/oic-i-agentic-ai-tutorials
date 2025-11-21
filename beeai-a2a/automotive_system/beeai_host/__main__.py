#!/usr/bin/env python3
import asyncio
import sys
import traceback

from beeai_framework.adapters.a2a.agents import A2AAgent, A2AAgentUpdateEvent
from beeai_framework.emitter import EventMeta
from beeai_framework.errors import FrameworkError
from beeai_framework.memory.unconstrained_memory import UnconstrainedMemory


async def main() -> None:
    agent = A2AAgent(
        url="http://127.0.0.1:9999",
        memory=UnconstrainedMemory()
    )

    prompt = sys.argv[1] if len(sys.argv) > 1 else "Predict maintenance for TRUCK-22"

    def print_update(data: A2AAgentUpdateEvent, event: EventMeta) -> None:
        value = data.value
        debug_info = value[1] if isinstance(value, tuple) else value
        print("Agent 🤖 (debug): ", debug_info)

    response = await agent.run(prompt).on("update", print_update)

    print("\nAgent 🤖 Final:\n", response.last_message.text)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except FrameworkError:
        traceback.print_exc()
        sys.exit(1)
