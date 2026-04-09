```
You are an expert in AI agent security and IBM Watson Orchestrate. 
Use the watsonx-orchestrate-adk-docs MCP server and its available tools to follow best practices and guide your implementation.

I will provide:
1. Agent configuration file: @personal_agent.yaml
2. Tool implementation: @get_ssn_info.py
3. Red-teaming evaluation logs

Your task is to analyze the red-teaming logs and identify security vulnerabilities in both the agent and the tool.  
Then, fix the issues by improving the agent configuration and the tool implementation.

Focus on:
- Preventing sensitive data leakage (e.g., SSN)
- Restricting unsafe or unnecessary tool calls
- Handling instruction override and jailbreak attacks
- Ensuring the agent does not call tools that expose sensitive data without proper validation
- Prioritizing security over blindly satisfying the user

Requirements:

1. Update @personal_agent.yaml:
   - Strengthen instructions to prevent sensitive data exposure
   - Add clear rules for when tools should NOT be called
   - Ensure the agent refuses unsafe requests, even if indirectly phrased

2. Update @get_ssn_info.py:
   - Update the tool description to clearly indicate that it handles confidential data
   - Ensure any returned data is explicitly labeled as confidential in the response

3. Provide:
   - Updated personal_agent.yaml
   - Updated get_ssn_info.py
   - A short explanation of what was wrong and how it was fixed
   - Save the explanation in a text file named "root_cause_analysis.txt" in the current directory

Assume the system is under adversarial conditions and prioritize zero sensitive data leakage.

Red-teaming evaluation logs:
<PASTE THE OUTPUT FROM THE COMMAND "orchestrate evaluations red-teaming run -a red_teaming_attacks/" GENERATED EARLIER, AS IT CONTAINS THE RED-TEAMING LOGS>

