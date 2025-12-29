#!/usr/bin/env python3
"""
FastMCP Server for SKU Availability
Provides tools to query inventory availability from ksqlDB
"""

import requests
import json
import os
from typing import Optional
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
from fastmcp import FastMCP

# Load environment variables
load_dotenv()

# ksqlDB Configuration
KSQLDB_ENDPOINT = os.getenv('KSQLDB_ENDPOINT')
KSQLDB_API_KEY = os.getenv('KSQLDB_API_KEY')
KSQLDB_API_SECRET = os.getenv('KSQLDB_API_SECRET')

# Create FastMCP server
mcp = FastMCP("SKU Availability Server")

def validate_config():
    """Validate that all required configuration is present"""
    required_vars = ['KSQLDB_ENDPOINT', 'KSQLDB_API_KEY', 'KSQLDB_API_SECRET']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    if 'xxxxx' in str(KSQLDB_ENDPOINT) or 'your-ksqldb-api-key' in str(KSQLDB_API_KEY):
        raise ValueError("Please update .env file with your actual ksqlDB credentials")

def query_ksqldb(query: str) -> list:
    """
    Execute a query against ksqlDB
    
    Args:
        query: SQL query to execute
    
    Returns:
        List of result records
    """
    validate_config()
    
    url = f"{KSQLDB_ENDPOINT}/query-stream"
    headers = {
        'Content-Type': 'application/vnd.ksql.v1+json'
    }
    
    payload = {
        "sql": query,
        "properties": {}
    }
    
    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            auth=HTTPBasicAuth(KSQLDB_API_KEY, KSQLDB_API_SECRET),
            stream=True,
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
        
        results = []
        
        # Read streaming response
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line.decode('utf-8'))
                    
                    # Skip header row
                    if 'header' in data or 'columnNames' in data or 'columnTypes' in data:
                        continue
                    
                    # Process data row
                    if isinstance(data, list) and len(data) >= 3:
                        results.append({
                            'sku': data[0],
                            'branch': data[1],
                            'available_quantity': data[2]
                        })
                    
                except json.JSONDecodeError:
                    continue
                except Exception:
                    continue
        
        return results
        
    except Exception as e:
        raise Exception(f"Failed to query ksqlDB: {str(e)}")

@mcp.tool()
def get_sku_availability(sku: str = "", branch: str = "") -> str:
    """
    Get real-time inventory availability for SKUs across branches.
    
    Query the INVENTORY_AVAILABILITY table which aggregates inventory transactions.
    Returns current stock levels calculated from all inventory adds and sales.
    
    Args:
        sku: Optional SKU filter (e.g., 'LAPTOP-DELL-XPS-15'). Leave empty to get all SKUs.
        branch: Optional branch filter (e.g., 'DubaiMall', 'MallOfEgypt'). Leave empty to get all branches.
    
    Returns:
        JSON string with availability records
    """
    try:
        # Build query - treat empty strings as no filter
        if sku and branch:
            query = f"SELECT * FROM INVENTORY_AVAILABILITY WHERE SKU='{sku}' AND BRANCH='{branch}';"
        elif sku:
            query = f"SELECT * FROM INVENTORY_AVAILABILITY WHERE SKU='{sku}';"
        elif branch:
            query = f"SELECT * FROM INVENTORY_AVAILABILITY WHERE BRANCH='{branch}';"
        else:
            query = "SELECT * FROM INVENTORY_AVAILABILITY;"
        
        # Execute query
        results = query_ksqldb(query)
        
        # Format response
        if not results:
            return json.dumps({"message": "No inventory records found", "results": []})
        
        return json.dumps({"results": results}, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)})

if __name__ == "__main__":
    mcp.run()

# Made with Bob
