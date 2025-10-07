# Create a new Agent and test the MCP Tool

Ensure the local watsonx Orchestrate Lite chat is available.

>We will create a simple agent without any additional behavior instructions.
The basic agent will be able to invoke the tool without any additional prompting.

### Step 1: Press `Manage agents`

![](images/create-agent-test-tool-01.jpg)

### Step 2: Press `Create agent`

![](images/create-agent-test-tool-02.jpg)

### Step 3: Give the agent a name, a short description, and press `Create`

* Name: `GalaxiumTravelerAgent`
* Description: `This Agent manages all the required tasks a user would perform to list available flights.`

![](images/create-agent-test-tool-03.jpg)

### Step 4: Navigate to the Toolset and press `Add tool`

![](images/create-agent-test-tool-04.jpg)

### Step 5: In the new window, select `Add from local instance`

The `tool from the remote MCP server` is now available from our current watsonx Orchestrate instance.

![](images/create-agent-test-tool-05.jpg)

### Step 6: Select the tool `Galaxium-Travels-Bookin-MCP-remote:list_flights`

The name reflects that we are using the `list_flights` tool from the remote MCP server called `Galaxium-Travels-Booking-MCP-remote`.

![](images/create-agent-test-tool-06.jpg)

### Step 7: Ask the following question

Question: `Can you show me the available flights?`

![](images/create-agent-test-tool-07.gif)

### (Optional) Step 8: Access Langfuse and inspect the agent/tool trace

* URL: http://localhost:3010/
* Username: `orchestrate@ibm.com`
* Password: `orchestrate`

![](images/create-agent-test-tool-08.gif)