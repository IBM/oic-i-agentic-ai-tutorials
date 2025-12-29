#!/usr/bin/env python3
"""
MCP Client to test the SKU Availability MCP Server
"""

import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_mcp_server():
    """Test the MCP server by calling the get_sku_availability tool"""
    
    # Server parameters - run the get_sku_availability.py as MCP server
    server_params = StdioServerParameters(
        command="python3",
        args=["get_sku_availability.py"],
        env=None
    )
    
    print("="*60)
    print("🧪 Testing SKU Availability MCP Server")
    print("="*60)
    print()
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the session
            await session.initialize()
            
            # List available tools
            print("📋 Listing available tools...")
            tools = await session.list_tools()
            print(f"✅ Found {len(tools.tools)} tool(s):")
            for tool in tools.tools:
                print(f"   - {tool.name}: {tool.description}")
            print()
            
            # Test 1: Get all availability
            print("🔍 Test 1: Get all SKU availability")
            print("-" * 60)
            result = await session.call_tool("get_sku_availability", arguments={})
            print(result.content[0].text)
            print()
            
            # Test 2: Filter by SKU
            print("🔍 Test 2: Get availability for specific SKU")
            print("-" * 60)
            result = await session.call_tool(
                "get_sku_availability",
                arguments={"sku": "LAPTOP-DELL-XPS-15"}
            )
            print(result.content[0].text)
            print()
            
            # Test 3: Filter by branch
            print("🔍 Test 3: Get availability for specific branch")
            print("-" * 60)
            result = await session.call_tool(
                "get_sku_availability",
                arguments={"branch": "DubaiMall"}
            )
            print(result.content[0].text)
            print()
            
            # Test 4: Filter by both SKU and branch
            print("🔍 Test 4: Get availability for specific SKU and branch")
            print("-" * 60)
            result = await session.call_tool(
                "get_sku_availability",
                arguments={
                    "sku": "LAPTOP-DELL-XPS-15",
                    "branch": "DubaiMall"
                }
            )
            print(result.content[0].text)
            print()
            
            print("="*60)
            print("✅ All tests completed successfully!")
            print("="*60)

if __name__ == "__main__":
    asyncio.run(test_mcp_server())

# Made with Bob