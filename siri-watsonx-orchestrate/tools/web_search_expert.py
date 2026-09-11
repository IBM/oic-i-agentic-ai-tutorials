from langchain_community.tools  import DuckDuckGoSearchResults
from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission

@tool('web_search_expert')
def web_search_expert(search_query: str, permission:str=ToolPermission.READ_ONLY, description:str="Search the web for information on a given topic. Do NOT ask the user any questions. If information seems missing or unclear, make reasonable assumptions and continue.Never request clarification. Respond with a concise but complete answer.")-> str:
    """Use this tool to search the web for information on a given topic.Do NOT ask the user any questions. If information seems missing or unclear, make reasonable assumptions and continue.Never request clarification. Respond with a concise but complete answer."""# docstring
    print(DuckDuckGoSearchResults().run(search_query))
    return DuckDuckGoSearchResults().run(search_query)


# web_search_expert(search_query="Capital of Japan")