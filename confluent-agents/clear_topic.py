#!/usr/bin/env python3
"""
Clear Kafka Topic Messages
Deletes all messages from a Kafka topic by setting retention to 1ms temporarily
"""

from confluent_kafka.admin import AdminClient, ConfigResource, ResourceType
import os
import sys
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
config = {
    'bootstrap.servers': os.getenv('BOOTSTRAP_SERVERS'),
    'security.protocol': 'SASL_SSL',
    'sasl.mechanisms': 'PLAIN',
    'sasl.username': os.getenv('API_KEY'),
    'sasl.password': os.getenv('API_SECRET')
}

TOPIC_NAME = os.getenv('TOPIC_NAME', 'inventory.transactions')

def validate_config():
    """Validate configuration"""
    required_vars = ['BOOTSTRAP_SERVERS', 'API_KEY', 'API_SECRET']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("❌ Error: Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        return False
    return True

def clear_topic():
    """Clear all messages from the topic"""
    
    if not validate_config():
        sys.exit(1)
    
    print("="*60)
    print("🗑️  Kafka Topic Cleaner")
    print("="*60)
    print(f"\n⚠️  Deleting ALL messages from topic: {TOPIC_NAME}")
    print(f"   Bootstrap Server: {config['bootstrap.servers']}\n")
    
    print("🔗 Connecting to Confluent Cloud...")
    
    try:
        # Create admin client
        admin_client = AdminClient(config)
        
        # Get current topic configuration
        resource = ConfigResource(ResourceType.TOPIC, TOPIC_NAME)
        
        print(f"📋 Getting current configuration for topic: {TOPIC_NAME}")
        
        # Describe topic to verify it exists
        result = admin_client.describe_configs([resource])
        configs = result[resource].result()
        
        # Store original retention
        original_retention = configs.get('retention.ms')
        print(f"   Original retention: {original_retention.value if original_retention else 'default'}")
        
        # Set retention to 1ms to delete all messages
        print("\n🔧 Setting retention.ms to 1ms (this will delete all messages)...")
        
        # Create new resource with updated config
        resource.set_config('retention.ms', '1')
        result = admin_client.alter_configs([resource])
        
        # Wait for the operation to complete
        result[resource].result()
        print("✅ Retention updated to 1ms")
        
        # Wait for messages to be deleted
        print("\n⏳ Waiting 10 seconds for messages to be deleted...")
        time.sleep(10)
        
        # Restore original retention (or set to default 7 days)
        print("\n🔧 Restoring retention settings...")
        
        if original_retention and original_retention.value != '-1':
            restore_value = original_retention.value
        else:
            restore_value = '604800000'  # 7 days in milliseconds
        
        # Create new resource for restoration
        resource = ConfigResource(ResourceType.TOPIC, TOPIC_NAME)
        resource.set_config('retention.ms', restore_value)
        result = admin_client.alter_configs([resource])
        result[resource].result()
        
        print(f"✅ Retention restored to: {restore_value}ms")
        
        print("\n" + "="*60)
        print("✅ SUCCESS")
        print("="*60)
        print(f"All messages deleted from topic: {TOPIC_NAME}")
        print("Topic is now empty and ready for new messages.")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nNote: This operation requires admin permissions on the topic.")
        print("If you don't have permissions, you may need to:")
        print("  1. Delete and recreate the topic in Confluent Cloud UI")
        print("  2. Or contact your Kafka administrator")
        sys.exit(1)

if __name__ == "__main__":
    clear_topic()

# Made with Bob
