from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
import requests
import json
import traceback
from pydantic import Field
from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
from ibm_watsonx_orchestrate.agent_builder.connections import ConnectionType
from ibm_watsonx_orchestrate.run import connections

MY_APP_ID="oic_llm_creds"
 
@tool(
    name="oic_granite_summary_tool",
    description=(
        "Calls a Granite model endpoint hosted on vLLM on Red Hat OpenShift to summarize or analyze text input. "
        "The input must be a trend, analysis, or insight derived from knowledge sources. It gives sentitment analysis for customer feedback of the product"
    ),
    expected_credentials=[
        {"app_id": MY_APP_ID, "type": ConnectionType.KEY_VALUE}
    ],
    permission=ToolPermission.READ_ONLY
)
def call_granite_as_endpoint(prompt: str) -> str:
    """
    Sends a POST request to the Granite Ollama API with the provided text prompt
    and returns the models generated response as a string.
    """

    # Get credentials
    creds = connections.key_value(MY_APP_ID)
    VLLM_ROUTE_OCP = creds['url_name']

    #Granite nano model is hosted and accessed as ollama API
    url = f"https://{VLLM_ROUTE_OCP}/v1/chat/completions"
    headers = {"Content-Type": "application/json"}

    payload = {
        "model": "ibm-granite/granite-4.0-350m",
        "messages": [{"role": "user", "content": "Summarize the following input :"+prompt}],
        "temperature": 0.5,     # Randomness (0 = deterministic, 1 = creative)
        "max_tokens": 150,      # Max tokens in the output
        "top_p": 0.9,           # Nucleus sampling
        "top_k": 40,            # Top-k sampling (if supported)
        "stop": ["\n\n"],        # Optional stop sequence(s)
        "stream": False
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        result = response.json()

        # Extract the model’s response text
        message = result.get("choices", [{}])[0].get("message", {}).get("content", "No response found.")
        return message

    except requests.exceptions.RequestException as e:
        return f" Request error while calling Granite endpoint: {traceback.format_exc()}"
    except Exception as e:
        return f"Unexpected error:\n{traceback.format_exc()}"

# Optional standalone run for local testing
if __name__ == "__main__":
    import sys
    print(len(sys.argv))
    print(sys.argv[1:])
    user_input = "Generate a one sentence summary for this. Based on the data, here are insights about YouTube Premium pricing:\n\nPrice Trend (Brazil - Individual Plan):\n- 2022: 20.90\n- 2023: 25.90 (23.92% increase)\n- 2024: 28.90 (11.58% increase)\n- 2025: 34.90 (20.76% increase)\n\nKey Insights:\n1. YouTube Premium prices have increased 67% over 3 years (from 20.90 to 34.90)\n2. User sentiment has declined from positive to negative, with users considering cancellation\n3. Users mention considering ad blockers as an alternative due to continuous price increases\n4. The comment \"Prices keep climbing, might cancel\"\n\nFor Future Planning:\n- Expect continued annual price increases\n- Budget for potential annual increases\n- Monitor your budget closely as streaming costs compete with essential expenses like rent"
    print(call_granite_as_endpoint(user_input))