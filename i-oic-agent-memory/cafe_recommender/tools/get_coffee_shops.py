
from ibm_watsonx_orchestrate.agent_builder.tools import tool


@tool
def get_coffee_shops(location: str) -> dict:
    """
    Returns nearby coffee shop recommendations based on location
    """

    coffee_data = {
        "bangalore": [
            {
                "name": "Third Wave Coffee",
                "rating": 4.5,
                "address": "Indiranagar"
            },
            {
                "name": "Chai Point",
                "rating": 4.2,
                "address": "Koramangala"
            },
            {
                "name": "Kaapi Kaate",
                "rating": 4.4,
                "address": "Jayanagar"
            }
        ],

        "hyderabad": [
            {
                "name": "Starbucks",
                "rating": 4.3,
                "address": "Banjara Hills"
            },
            {
                "name": "Roastery Coffee House",
                "rating": 4.7,
                "address": "Jubilee Hills"
            }
        ],

        "mysore": [
            {
                "name": "Depth N Green",
                "rating": 4.6,
                "address": "Gokulam"
            },
            {
                "name": "Old House Cafe",
                "rating": 4.3,
                "address": "Lakshmipuram"
            }
        ]
    }

    location = location.lower().strip()

    shops = coffee_data.get(location)

    if not shops:
        return {
            "location": location,
            "coffee_shops": [],
            "message": "No coffee shops found"
        }

    return {
        "location": location,
        "coffee_shops": shops
    }

