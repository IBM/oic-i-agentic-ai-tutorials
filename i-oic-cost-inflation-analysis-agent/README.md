
# i-oic-cost-inflation-analysis-agent

## Steps Overview
This tutorial demonstrates how an agent uses Groq for IBM watsonx Orchestrate , it provides a single-tenant cloud service where dedicated racks are provisioned exclusively for each user. This configuration enables the deployment of specific supported models that are selected by you, including compatible Bring Your Own Model (BYOM) options.

### Why Groq ?
Groq delivers ultra-low-latency, high-throughput AI inference through its innovative LPU (Language Processing Unit) architecture, enabling real-time reasoning and faster model execution at dramatically lower power and cost. By integrating Groq’s compute acceleration with IBM watsonx and Granite foundation models, enterprises gain the ability to deploy near-instant, on-prem or edge AI inference for mission-critical use cases - from financial analysis to conversational agents.

https://www.ibm.com/docs/en/watsonx/watson-orchestrate/base?topic=entitlements-licenses-groq

---

### Create Agents

In this tutorial , you will build an AI agent in watsonx Orchestrate that:
- Uses Groq's LLM to reason and orchestrate.
- Calls an agent that run those queries using Anthropic Clause Sonnet Model.
- Displays the summarized results via tool leveraging IBM Granite's nano Model.

---

## Step 1: Create Connections

In this step , you will Create a **connection** to Groq and Anthropic. These credentials will also be used when importing the external model in watsonx Orchestarte.

```
orchestrate connections add -a groq_credentials
orchestrate connections configure -a groq_credentials --env draft -k key_value -t team
orchestrate connections set-credentials -a groq_credentials --env draft -e "api_key=grok-api-key"

orchestrate connections configure -a groq_credentials --env live -k key_value -t team
orchestrate connections set-credentials -a groq_credentials --env live -e "api_key=grok-api-key"


orchestrate connections add -a anthropic_credentials
orchestrate connections configure -a anthropic_credentials --env draft -k key_value -t team
orchestrate connections set-credentials -a anthropic_credentials --env draft -e "api_key=anthropic_api_key"

orchestrate connections configure -a anthropic_credentials --env team -k key_value -t team
orchestrate connections set-credentials -a anthropic_credentials --env team -e "api_key=anthropic_api_key"


```
## Step 2: Import External LLM

In this tutorial, you'll import the Clause Sonnet and GPT OSS model. You can configure another model of your choice.
List to view if the model is imported properly or not .
**Note**: Please find the list of supported LLM providers [here](https://developer.watson-orchestrate.ibm.com/llm/managing_llm).

![external-model](./images/models_config.png)

```

orchestrate models import --file groq-openai.yaml --app-id groq_credentials

orchestrate models import --file anthropic-claude.yaml --app-id anthropic_credentials

orchestrate models list

```
![external-model](./images/models_list.png)

## Step 3: Import Tools

This step imports a tool that passes the analysis from an agent to the tool for summarization


```
orchestrate tools import -k python -f oic_granite_summary_tool.py -r requirements.txt
```

### Step 4 : Import Agents
In this step, you'll import the agent that:
- Uses Groq platform for reasoning .
- Uses the external LLM for inferencing ie.e Anthropics Clause Sonnet.

```
orchestrate agents import --file oic_cost_inflation_analysis_agent.yaml 

orchestrate agents import --file oic_cost_insights_master_agent.yaml

```
![agent](./images/import_agent.png)

## Conclusion 
In this tutorial, you:

- Imported an external LLM (e.g., GPT OSS 120B, Claude Sonnet )

This setup enables low-code, LLM-driven access to your data — directly within IBM watsonx Orchestrate.

## Tips

- Make sure all dependencies in requirements.txt are available during tool import.
- Always test tools independently before wiring them into an agent.