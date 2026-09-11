"""
Simple tool that returns a random motivational quote as a single text string.
"""
import random
from pydantic import BaseModel, Field
from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission


class Quote(BaseModel):
    quote: str = Field(description="A motivational quote with its author included as text.")


@tool(
    name="get_quote_min",
    permission=ToolPermission.READ_ONLY,
    description="Return a random motivational quote as a single string including the author."
)
def get_quote_min() -> Quote:
    quotes = [
        "Small steps every day add up to big results. — Unknown",
        "Focus on progress, not perfection. — Unknown",
        "Done is better than perfect. — Sheryl Sandberg",
        "Keep going — you’re closer than you think. — Unknown",
        "Dream big. Start small. Act now. — Robin Sharma",
    ]
    quote = random.choice(quotes)
    return Quote(quote=quote)

# print(get_quote_min())
