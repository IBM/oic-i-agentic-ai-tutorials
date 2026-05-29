"""
Tools for calculating annualized rate of return
"""
from langchain_core.tools import tool


@tool
def calculate_annualized_return(
    initial_investment: float,
    current_value: float,
    months_invested: int
) -> dict:
    """
    Calculate the annualized rate of return for an investment.
    
    Args:
        initial_investment: The initial investment amount in dollars
        current_value: The current value of the investment in dollars
        months_invested: The number of months the money has been invested
        
    Returns:
        A dictionary containing the calculation results including:
        - annualized_return: The annualized rate of return as a percentage
        - total_return: The total return as a percentage
        - profit_loss: The profit or loss amount in dollars
    """
    if initial_investment <= 0:
        return {
            "error": "Initial investment must be greater than 0",
            "annualized_return": None,
            "total_return": None,
            "profit_loss": None
        }
    
    if months_invested <= 0:
        return {
            "error": "Months invested must be greater than 0",
            "annualized_return": None,
            "total_return": None,
            "profit_loss": None
        }
    
    # Calculate total return
    total_return = ((current_value - initial_investment) / initial_investment) * 100
    
    # Calculate profit/loss
    profit_loss = current_value - initial_investment
    
    # Calculate annualized return
    # Formula: ((Current Value / Initial Investment) ^ (12 / months)) - 1
    years = months_invested / 12
    annualized_return = (((current_value / initial_investment) ** (1 / years)) - 1) * 100
    
    return {
        "annualized_return": round(annualized_return, 2),
        "total_return": round(total_return, 2),
        "profit_loss": round(profit_loss, 2),
        "initial_investment": initial_investment,
        "current_value": current_value,
        "months_invested": months_invested,
        "years_invested": round(years, 2)
    }

# Made with Bob
