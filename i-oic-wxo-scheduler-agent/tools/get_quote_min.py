"""
Simple tool that returns a random motivational quote.
"""
import random
from pydantic import BaseModel, Field
from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission

class Quote(BaseModel):
    text: str = Field(description="The quote text.")
    author: str = Field(description="The quote's author.")

@tool(
    name="get_quote_min",
    permission=ToolPermission.READ_ONLY,
    description="Return a random motivational quote."
)
def get_quote_min() -> Quote:
    quotes = [
        ("Small steps every day add up to big results.", "Unknown"),
        ("Focus on progress, not perfection.", "Unknown"),
        ("Done is better than perfect.", "Sheryl Sandberg"),
        ("Keep going — you’re closer than you think.", "Unknown"),
        ("Dream big. Start small. Act now.", "Robin Sharma")
    ]
    text, author = random.choice(quotes)
    return Quote(text=text, author=author)


# print(get_quote_min())
