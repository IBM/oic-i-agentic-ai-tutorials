"""
BeeAI Service - Main Entry Point
Single unified service for WXO integration with IBM watsonx.ai
"""
import sys
import traceback
from beeai_framework.errors import FrameworkError
from beeai_service.config.settings import app_settings, watsonx_settings
from beeai_service.core.agent import create_maintenance_agent
from beeai_service.servers.wxo_server import WXOServer


def main():
    """Main entry point"""
    try:
        print("=" * 60)
        print("🚀 BeeAI Predictive Maintenance Service")
        print("=" * 60)
        print(f"🤖 Model: {app_settings.llm_model}")
        print(f"🔌 Server: {app_settings.wxo_host}:{app_settings.wxo_port}")
        print("=" * 60)
        
        # Create agent
        print("\n🤖 Creating BeeAI Maintenance Agent...")
        agent = create_maintenance_agent()
        
        # Create and start WXO server
        print("🚀 Starting WXO HTTP Server...\n")
        server = WXOServer(agent)
        server.serve()
        
    except FrameworkError as e:
        print(f"❌ Framework Error: {e}")
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()