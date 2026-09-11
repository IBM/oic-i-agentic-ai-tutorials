import os
import re
from dotenv import load_dotenv
from github import Github
import datetime

# Load environment variables
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
EMAIL_TOKEN = os.getenv("EMAIL_TOKEN")



# Fetch repository files
def fetch_repo_files(repo_name,github_token):
    
    github = Github(github_token)


    repo = github.get_repo(repo_name)
    contents = repo.get_contents("")
    files = []
    
    while contents:
        file_content = contents.pop(0)
        if file_content.type == "file":
            files.append(file_content)
        elif file_content.type == "dir":
            contents.extend(repo.get_contents(file_content.path))
    
    return files

# Extract code snippets from the files
def extract_code_snippets(files):
    code_snippets = []
    for file in files:
        if file.name.endswith((".py", ".js", ".java", ".jsx", ".json", ".c", ".go", ".ipynb",".md")):  # Adjust extensions as needed
            content = file.decoded_content.decode("utf-8")
            code_snippets.append(content[:5000])  # Limit snippet size to avoid token overflow
    return code_snippets

# Extract function names using regex (customize for different languages)
def extract_function_names(code):
    function_names = []
    
    # Regex patterns for various language functions
    patterns = [
        r"def (\w+)\(",  # Python function definition
        r"function (\w+)\(",  # JavaScript function definition
        r"public\s+[\w<>\[\]]+\s+(\w+)\(",  # Java function definition
        r"(\w+)\s*=\s*function\s*\(",  # JS anonymous function
        r"func (\w+)\(",  # Go function definition
        r"fun (\w+)\(",  # Kotlin function definition
        r"fun (\w+)\s*\(",  # Dart function definition
        r"^\s*def\s+(\w+)\s*\(",  # Python function definition (indented code in Jupyter)
        r"(\w+)\s*\(\)\s*{",  # JSX function definition (React function component)
        r"const\s+(\w+)\s*=\s*\(\)\s*=>\s*{",  # JSX arrow function definition (React)
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, code)
        function_names.extend(matches)
    
    return function_names


# Function to fetch repo details and commit data
def fetch_repo_details(repo_name,github_token):
    github = Github(github_token)

    repo = github.get_repo(repo_name)
    open_issues = repo.get_issues(state='open')
    commits = repo.get_commits()
    description = repo.description
    commit_dates_messages = [(commit.commit.author.date.strftime("%Y-%m-%d %H:%M:%S %Z"),commit.commit.message) for commit in commits]

    files = fetch_repo_files(repo_name,github_token)

    code_snippets = extract_code_snippets(files)  # Extract code snippets from files

    
    return {
        "name": repo_name,
        "description": description,
        "commit_count": commits.totalCount,
        "commit_dates_messages": commit_dates_messages,
        "open_issues": str(list(open_issues)),
        # "ai_description": ai_description,  # Adding AI-generated description
        "code_snippets": code_snippets  # Including code snippets
    }


def dummyemailtoken():
    return EMAIL_TOKEN
    
def dummygithubtoken():
    return GITHUB_TOKEN


def format_text_to_html(text: str) -> str:
    """
    Converts arbitrary LLM output into clean HTML.
    - If text contains bullet markers (*, -, •), render as <ul><li>.
    - Otherwise, render paragraphs separated by <br>.
    """
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    
    # Detect bullets
    if any(line.startswith(("*", "-", "•")) for line in lines):
        items = [f"<li>{line.lstrip('*-• ').strip()}</li>" for line in lines if line]
        return "<html><body><ul>" + "".join(items) + "</ul></body></html>"
    else:
        # Treat as paragraph text
        return "<html><body>" + "<br>".join(lines) + "</body></html>"