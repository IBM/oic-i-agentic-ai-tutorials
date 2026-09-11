#!/usr/bin/env python3
"""
MCP Server that exposes LangFlow RAG pipeline as a tool
"""

import os
import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Load environment variables
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("langflow-rag-tool")

# Configuration
LANGFLOW_API_URL = os.getenv("LANGFLOW_API_URL", "http://localhost:7860/api/v1")
LANGFLOW_FLOW_ID = os.getenv("LANGFLOW_FLOW_ID", "")


@mcp.tool("query_documents")
async def query_documents(question: str, top_k: int = 3) -> str:
    """
    Query your private documents using the LangFlow RAG pipeline.
    
    Args:
        question: The question to ask about your documents
        top_k: Number of relevant document chunks to retrieve (default: 3)
    
    Returns:
        A comprehensive answer based on retrieved documents
    """
    if not LANGFLOW_FLOW_ID:
        return "Error: LANGFLOW_FLOW_ID not configured. Please set it in .env file."
    
    try:
        # Call LangFlow API
        payload = {
            "input_value": question,
            "tweaks": {
                "retriever": {"k": top_k}
            }
        }
        
        response = requests.post(
            f"{LANGFLOW_API_URL}/run/{LANGFLOW_FLOW_ID}",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        response.raise_for_status()
        
        # Extract answer from response
        result = response.json()
        
        if "outputs" in result and len(result["outputs"]) > 0:
            answer = result["outputs"][0].get("text", "")
            return answer
        else:
            return "No answer generated. Please check your LangFlow configuration."
            
    except requests.exceptions.RequestException as e:
        return f"Error calling LangFlow API: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


if __name__ == "__main__":
    print("🚀 Starting LangFlow RAG MCP Tool server...")
    print(f"📡 LangFlow API: {LANGFLOW_API_URL}")
    print(f"🔑 Flow ID: {LANGFLOW_FLOW_ID or '⚠️  NOT SET - Please configure in .env'}")
    print("\nServer ready. Connect using MCP Inspector or watsonx Orchestrate.")
    mcp.run()
