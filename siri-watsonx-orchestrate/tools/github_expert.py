from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
from utils import fetch_repo_details
from ibm_watsonx_orchestrate.client.connections import ConnectionType
from ibm_watsonx_orchestrate.run import connections
from utils import dummygithubtoken

CONNECTION_GITHUB = 'github_connection'


@tool("github_expert",  {"app_id": CONNECTION_GITHUB, "type": ConnectionType.KEY_VALUE})
def github_expert(repo_url : str,  description: str="Search the GitHub for information on a given repository", permission: str=ToolPermission.READ_ONLY)-> str:
    """
    Analyzes a public GitHub repository based on the provided URL and describes its overall purpose.  Use https://github.com/Owaiskhan9654/owaiskhan9654 as default repo if no Github is provided

    Args:
        repo_url (str): URL of the public GitHub repository to analyze.  Use https://github.com/Owaiskhan9654/owaiskhan9654 as default repo if no Github is provided

    Returns:
        str: A natural language description of the repository's main purpose.

    Note:
        Only public GitHub repository URLs are accepted as input.  Use https://github.com/Owaiskhan9654/owaiskhan9654 as default repo if no Github is provided
    """


    try:
         github_token = connections.key_value(CONNECTION_GITHUB)['GITHUB_TOKEN']
    except:
         github_token = dummygithubtoken()
        
    if repo_url.startswith("https://github.com/"):
            parts = repo_url.strip('/').split('/')
            if len(parts) >= 5:
                repo_name =  parts[3]+"/"+ parts[4]

    else:
        repo_name = repo_url

    try:
        # Fetch repo details and extract code snippets
        details = fetch_repo_details(repo_name, github_token),  # Get repo details including commits
        print(details)
        return details

    except:
        print("Make sure User inputs a Public repo which is accessible")
        return "Make sure User inputs a Public repo which is accessible"
