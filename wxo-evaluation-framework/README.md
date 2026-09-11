# Watsonx Orchestrate — Banking Agent

## Overview
This repository contains an example **Banking Agent** built for **IBM watsonx Orchestrate (wxo)**. The agent demonstrates how to wire an LLM-powered agent to a curated set of tools that perform common banking tasks such as account lookup, balance inquiry, transaction listing, branch resolution, contact updates, and internal transfers (simulated).

## Repository Structure
```
/ (root)
├─ agent_tools/
│  ├─ banking_agent.json        # Agent definition and policy/instruction text
│  ├─ banking_tools.py          # Tool implementations (Python) for agent use
├─ .env_sample
├─ import-all.sh                # Script to import tools and agent into wxo
├─ user_stories/                # This folder contains the user stories for testing
|  ├─ banking_user_stories.csv  # User stories to be tested
|  ├─ banking_test_cases.csv    # Test cases to be tested(In watsonx orchestrate UI)
└─ README_Watsonx_Orchestrate_Banking_Agent.md  # This document
```

## Setup & Import Steps (Quickstart)
Run the import script which registers the Python tools and the agent definition into your watsonx Orchestrate workspace.

1. Create .env file
- Copy the content from .env_sample file and paste it into .env file.

  🚨 Note: we expect `WATSONX_APIKEY, WATSONX_SPACE_ID` or `WO_INSTANCE, WO_API_KEY` be part of the environment variables or specified in .env file. 

2. Ensure `import-all.sh` is executable:
```bash
chmod +x import-all.sh
```

3. Run the import script from the repo root:
```bash
./import-all.sh
```

After successful import you should see the agent and corresponding tools listed in the watsonx Orchestrate console.

4. Generate test cases from the user stories
Run `orchestrate evaluations generate --stories-path user_stories/banking_user_stories.csv --tools-path agent_tools/ --env-file .env`

5. Evaluate the test cases
Run `orchestrate evaluations evaluate --test-paths user_stories/banking_agent_test_cases/ --output-dir user_stories/banking_test_execution/ --env-file .env`

You can visualise all the testcases in the folder - ./user_stories
