from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
import requests
import json

OLLAMA_ROUTE_OCP = "REPLACE_WITH_OLLAMA_ROUTE_OCP"

@tool(
    name="oic_granite_summary_tool",
    description=(
        "Calls a Granite model endpoint hosted on Ollama on Red Hat OpenShift to summarize or analyze text input. "
        "The input must be a trend, analysis, or insight derived from knowledge sources. It gives sentitment analysis for customer feedback of the product"
    ),
    permission=ToolPermission.READ_ONLY
)
def call_granite_as_endpoint(prompt: str) -> str:
    """
    Sends a POST request to the Granite Ollama API with the provided text prompt
    and returns the model’s generated response as a string.
    """

    #Granite nano model is hosted and accessed as ollama API
    url = f"https://{OLLAMA_ROUTE_OCP}/v1/chat/completions"
    headers = {"Content-Type": "application/json"}

    payload = {
        "model": "granite4:350m-h",
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
        return f" Request error while calling Granite endpoint: {str(e)}"
    except Exception as e:
        return f" Unexpected error: {str(e)}"

# Optional standalone run for local testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python ollama_api_call.py '<your text prompt>'")
    else:
        user_input = " ".join(sys.argv[1:])
        print("\n Granite Response:\n")
        print(call_granite_as_endpoint(user_input))
