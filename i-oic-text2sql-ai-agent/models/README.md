# i-oic-text2sql-ai-agent

## Steps Overview
This tutorial demonstrates how to import an external third-party Large Language Model (LLM) in IBM watsonx Orchestrate (WXO).
In this section , you will be able to **create connection** for the external LLM provider and import the **external LLM** in watsonx Orchestrate .
**Note**: Detailed steps are mentioned under `i-oic-text2sql-ai-agent/README.md`.

#### Create Connections 

```
orchestrate connections add -a openai_creds

orchestrate connections configure -a openai_creds --env draft -k key_value -t team

orchestrate connections set-credentials -a openai_creds --env draft -e "api_key=YOUR_API_KEY"

```
#### Create a model yaml file and import it 

```
orchestrate models import --file openai-gpt-4o-mini.yaml --app-id openai_creds
```