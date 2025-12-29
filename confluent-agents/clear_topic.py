#!/usr/bin/env python3
"""
Clear Kafka Topic Messages
Deletes all messages from a Kafka topic by deleting and recreating it
"""

from confluent_kafka.admin import AdminClient, NewTopic
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
    """Clear all messages from the topic by deleting and recreating it"""
    
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
        
        print(f"📋 Deleting topic: {TOPIC_NAME}")
        
        # Delete the topic
        fs = admin_client.delete_topics([TOPIC_NAME], operation_timeout=30)
        
        # Wait for deletion to complete
        for topic, f in fs.items():
            try:
                f.result()  # The result itself is None
                print(f"✅ Topic {topic} deleted successfully")
            except Exception as e:
                print(f"⚠️  Failed to delete topic {topic}: {e}")
        
        # Wait a bit for deletion to propagate
        print("\n⏳ Waiting 5 seconds for deletion to propagate...")
        time.sleep(5)
        
        # Recreate the topic with infinite retention
        print(f"\n🔧 Recreating topic: {TOPIC_NAME}")
        
        new_topic = NewTopic(
            TOPIC_NAME,
            num_partitions=6,
            replication_factor=3,
            config={
                'retention.ms': '-1',  # Infinite retention
                'cleanup.policy': 'delete'
            }
        )
        
        fs = admin_client.create_topics([new_topic])
        
        # Wait for creation to complete
        for topic, f in fs.items():
            try:
                f.result()  # The result itself is None
                print(f"✅ Topic {topic} created successfully")
            except Exception as e:
                print(f"❌ Failed to create topic {topic}: {e}")
                sys.exit(1)
        
        print("\n" + "="*60)
        print("✅ SUCCESS")
        print("="*60)
        print(f"Topic {TOPIC_NAME} cleared and recreated")
        print("Retention: Infinite (keeps all messages)")
        print("Topic is now empty and ready for new messages.")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nNote: This operation requires admin permissions.")
        print("Make sure your API key has permissions to delete and create topics.")
        sys.exit(1)

if __name__ == "__main__":
    clear_topic()

# Made with Bob
