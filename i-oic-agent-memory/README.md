# Building Personalized AI Agents with Memory in watsonx Orchestrate

A step-by-step guide to storing and retrieving user preferences in orchestration workflows using watsonx Orchestrate.

---

# Overview

This tutorial demonstrates how to build a personalized memory-enabled multi-agent workflow using watsonx Orchestrate. The application stores and retrieves user preferences using memory capabilities and provides personalized coffee shop recommendations based on user location.

The workflow includes:
- A custom LangGraph-based memory agent
- A coffee shop recommendation tool
- A main orchestration agent
- Embedded web chat integration
- User-scoped memory support

---

# Prerequisites

- Python 3.11
- Node.js and npm
- Active watsonx Orchestrate instance
- watsonx Orchestrate API Key
- watsonx Orchestrate Instance URL

---

# Clone the repository

```bash
git clone https://github.com/IBM/oic-i-agentic-ai-tutorials.git
```

Navigate to the tutorial folder:

```bash
cd i-oic-agent-memory
```

---

# Create and activate Python virtual environment

Create the virtual environment:

```bash
python3.11 -m venv .venv
```

## Activate on macOS/Linux

```bash
source .venv/bin/activate
```

## Activate on Windows

```bash
.venv\Scripts\activate
```

---

# Install dependencies

```bash
pip install ibm-watsonx-orchestrate==2.10.0
```

---

# Connect to the watsonx Orchestrate SaaS instance

Add and activate your watsonx Orchestrate SaaS environment using the following commands:

```bash
orchestrate env add -n <env-name> -u <WO_INSTANCE_URL>

orchestrate env activate <env-name> -a <WO_API_KEY>
```

Replace the following values:
- `<env-name>` — Name of the environment
- `<WO_INSTANCE_URL>` — Your watsonx Orchestrate instance URL
- `<WO_API_KEY>` — Your watsonx Orchestrate API key

---

# Navigate to the cafe recommender project

```bash
cd cafe_recommender
```

---

# Import the user preference processor agent

This custom LangGraph-based agent stores and retrieves user preferences using watsonx Orchestrate memory capabilities.

```bash
orchestrate agents import \
  --experimental-package-root agents/user_preference_processor
```

---

# Import the coffee shop recommendation tool

This tool returns coffee shop recommendations based on the provided location.

```bash
orchestrate tools import -f tools/get_coffee_shops.py -k python
```

---

# Import the cafe recommendation agent

This is the main orchestration agent responsible for handling conversations, retrieving stored user preferences, and providing personalized coffee shop recommendations.

```bash
orchestrate agents import -f agents/cafe_recommendation_agent/agent.yaml
```

---

# Deploy the agent

1. Open watsonx Orchestrate.
2. Navigate to **Manage Agents**.
3. Open the `cafe_recommendation_agent`.
4. Click **Deploy**.

---

# Configure embedded web chat

1. After deploying the agent, click the **Channels** tab.
2. Select **Embedded web chat**.
3. Click **Live**.
4. Copy the embedded web chat Configuration Script.

---

# Run the web application

Navigate to the web application folder:

```bash
cd ..
cd chat-ui
```

Install dependencies:

```bash
npm install
```

Start the application:

```bash
node server.js
```

Open the `index.html` file in any browser.

---

# Enable User-Specific Memory

To maintain user-specific memory, the application must uniquely identify each user.

For this, the application must send the User Identity (`sub`) value, which is used to track and retrieve the user’s memory context. To securely send the user identity, security must be enabled.


## 1. Configure Security

If security is already enabled for your watsonx Orchestrate instance:

- Use the existing generated security keys.
- In the **Security Setup** section, select **"Yes, I have client Private Key"**.
- Paste the IBM private key.
<img width="2944" height="1444" alt="image" src="https://github.com/user-attachments/assets/de71fc12-ca9e-4732-8fe6-f6c8859a245c" />

### Otherwise

1. Navigate to the **Security Setup** section.
2. Select **"No, enable security for me"**.
3. Choose the deployment type:
   - **IBM Cloud SaaS**, or
   - **AWS**
4. Enter the following details:
   - **watsonx Orchestrate API Key**
   - **watsonx Orchestrate Instance URL**
5. Click **"Rotate & Generate Keys"**.

The application will automatically generate and configure the required security keys.


<img width="1470" height="781" alt="Screenshot 2026-06-09 at 11 59 45 PM" src="https://github.com/user-attachments/assets/6d42589a-20e8-4451-8684-f3c3f3d719b9" />



## 2. Configure Embedded Web Chat

Paste the Embedded Web Chat Configuration Script into the sample UI.
<img width="2960" height="1596" alt="image" src="https://github.com/user-attachments/assets/481378ab-f7f7-4061-8052-5bd09fcfc721" />


## 3. Load the Agent

Enter the User Identity (`sub`) value and load the agent.

Each user maintains an independent memory context.

For example:

- User1 can store Bangalore as the preferred location
- User2 can independently store Mysore as the preferred location

During future interactions, the agent automatically retrieves the stored preferences for the respective user.

---

# Example prompts

```text
Show me nearby coffee shops
```


```text
Recommend cafes near me
```

---

# Architecture Flow

```text
                    User / Web Application
                               |
                               v
                watsonx Orchestrate Main Agent
                  (Cafe Recommendation Agent)
                               |
             -----------------------------------
             |                                 |
             v                                 v
 User Preference Processor Agent      Coffee Shop Tool
      (LangGraph Agent)               (get_coffee_shops)
             |
             v
      watsonx Orchestrate
             Memory
```

Workflow:
1. User asks for nearby coffee shops
2. Main agent checks stored user location
3. If location exists → fetch coffee shops
4. If location missing → ask user and store it
5. Return personalized recommendations

---

# Summary

This tutorial demonstrates how to build a personalized memory-enabled multi-agent workflow using watsonx Orchestrate, LangGraph, and embedded web chat integration. The application stores and retrieves user preferences using memory capabilities and delivers personalized coffee shop recommendations across conversations.

For an in-depth explanation of state management, user-scoped memory, and checkpointers in watsonx Orchestrate, see the detailed [wxO_Memory_and_Checkpointers_Guide.md](https://github.com/IBM/oic-i-agentic-ai-tutorials/blob/main/i-oic-agent-memory/wxO_Memory_and_Checkpointers_Guide.md).
