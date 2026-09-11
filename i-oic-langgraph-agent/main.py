"""
Main script to run the Annualized Rate of Return Agent
"""
import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from agent import create_react_agent, format_response


def main():
    """
    Main function to run the agent interactively.
    """
    # Load environment variables
    load_dotenv()
    
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not found in environment variables.")
        print("Please create a .env file with your OpenAI API key:")
        print("OPENAI_API_KEY=your-api-key-here")
        return
    
    # Create the agent
    print("Initializing Annualized Rate of Return Agent...")
    agent = create_react_agent()
    print("Agent ready!\n")
    
    # Configuration for thread
    config = {"configurable": {"thread_id": "1"}}
    
    print("=" * 70)
    print("Annualized Rate of Return Calculator Agent")
    print("=" * 70)
    print("\nThis agent can help you calculate the annualized rate of return")
    print("for your investments. Just provide:")
    print("  - Initial investment amount")
    print("  - Current value")
    print("  - Number of months invested")
    print("\nType 'quit' or 'exit' to end the conversation.\n")
    print("=" * 70)
    
    # Interactive loop
    while True:
        try:
            # Get user input
            user_input = input("\nYou: ").strip()
            
            # Check for exit commands
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nThank you for using the Annualized Rate of Return Agent!")
                break
            
            if not user_input:
                continue
            
            # Create message
            message = HumanMessage(content=user_input)
            
            # Invoke the agent
            print("\nAgent: ", end="", flush=True)
            response = agent.invoke(
                {"messages": [message]},
                config=config
            )
            
            # Format and print response
            formatted_response = format_response(response)
            print(formatted_response)
            
        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Exiting...")
            break
        except Exception as e:
            print(f"\nError: {str(e)}")
            print("Please try again or type 'quit' to exit.")


def run_example():
    """
    Run an example calculation without interactive mode.
    """
    # Load environment variables
    load_dotenv()
    
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not found in environment variables.")
        return
    
    # Create the agent
    print("Running example calculation...\n")
    agent = create_react_agent()
    
    # Configuration for thread
    config = {"configurable": {"thread_id": "example"}}
    
    # Example query
    query = """
    I invested $10,000 and now it's worth $12,500. 
    I've been invested for 18 months. 
    What's my annualized rate of return?
    """
    
    print(f"Query: {query.strip()}\n")
    
    # Invoke the agent
    message = HumanMessage(content=query)
    response = agent.invoke(
        {"messages": [message]},
        config=config
    )
    
    # Print response
    print("Agent Response:")
    print(format_response(response))


if __name__ == "__main__":
    import sys
    
    # Check if example mode is requested
    if len(sys.argv) > 1 and sys.argv[1] == "--example":
        run_example()
    else:
        main()

# Made with Bob
