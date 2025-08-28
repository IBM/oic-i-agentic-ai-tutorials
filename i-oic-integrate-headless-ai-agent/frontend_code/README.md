# Integrate watsonx Orchestrate AI Agents in Custom UI - Frontend Components

## Front End Instructions

### Disclaimer
- This is PoC quality code not meant to be deployed as-is in Production.
- Clearly, it can be improved.

This project was bootstrapped with [Create React App](https://github.com/facebook/create-react-app).

### Install the Packages
```bash
npm install
```

### Start the Application
Run the following command to start the application:
```bash
npm start
```

Open [http://localhost:3000](http://localhost:3000) to view it in your browser.

The page will automatically reload when you make changes.

>**Note**: [JavaScript code](https://github.com/IBM/oic-i-agentic-ai-tutorials/blob/main/i-oic-integrate-headless-ai-agent/frontend_code/src/App.js) explanation :
        >- `agent_id` and `thread_id` (optional) are passed as query parameters to match the backend API.
        >- The front-end calls the _/chat/v2_ endpoint of the wrapper service that is deployed on IBM Code Engine.
        >- The response stream is read and parsed by FastAPI .
        >- JSON content is extracted and shown in the chat UI in real time.
        >- Any HTTP or JSON errors are detected and displayed in the chat window for user feedback. -->