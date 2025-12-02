from langchain_experimental.utilities import PythonREPL
from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
import math




@tool("python_expert", permission=ToolPermission.READ_ONLY, description="This tool is used to execute python commands inside terminal. If you want to see the output of a value, you should print it out with print(...) in python3 terminal. Do NOT ask the user any questions. If information seems missing or unclear, make reasonable assumptions and continue.Never request clarification. Respond with a concise but complete answer.")
def python_expert(query:str) -> str:
    
    """Use this to execute mathematical equations python3 code in python3 terminal only. If you want to see the output of a value,you should print it out with print(...) in python3 terminal, handle syntax error and Import math package aswell
       Example : Input : 'What is the multiplication of 4, 5, 7?' Output: 'import math; print(4*5*7)' """

    # Define the Python REPL tool
    python_repl = PythonREPL()
    result=python_repl.run(query)
    print(result)
    return result



# python_expert('import math; print(4*5*7)')


