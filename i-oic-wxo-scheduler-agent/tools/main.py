import asyncio
import logging
from pathlib import Path

from daily_quote_flow_min import build_daily_quote_flow
from ibm_watsonx_orchestrate.flow_builder.flows.flow import FlowRunStatus
from ibm_watsonx_orchestrate.flow_builder.types import FlowEventType

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

flow_run = None


def on_flow_end(result):
    """
    Callback function when the flow completes successfully.
    """
    print(f"✅ Custom Handler: Flow `{flow_run.name}` completed successfully!")
    print("👉 Result:")
    print(result)


def on_flow_error(error):
    """
    Callback function when the flow fails.
    """
    print(f"❌ Custom Handler: Flow `{flow_run.name}` failed with error:\n{error}")





async def main():
    """
    Demonstrates how to build, compile, deploy, and invoke the daily quote flow.
    """
    # Step 1: Build and deploy the flow
    print("🚀 Compiling and deploying `daily_quote_flow` ...")
    my_flow_definition = await build_daily_quote_flow().compile_deploy()

    # Step 2: Save the generated flow spec for inspection
    current_folder = Path(__file__).resolve().parent
    generated_folder = current_folder / "generated"
    generated_folder.mkdir(exist_ok=True)

    spec_file = generated_folder / "daily_quote_flow.json"
    my_flow_definition.dump_spec(str(spec_file))
    print(f"📄 Flow spec saved to: {spec_file}")

    # Step 3: Invoke the flow
    print("⚙️ Invoking flow...")
    global flow_run
    flow_run = await my_flow_definition.invoke(
        {},
        on_flow_end_handler=on_flow_end,
        on_flow_error_handler=on_flow_error,
        debug=True
    )

if __name__ == "__main__":
    asyncio.run(main())
