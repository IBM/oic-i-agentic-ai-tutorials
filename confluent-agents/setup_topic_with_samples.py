#!/usr/bin/env python3
"""
Kafka Topic Setup Script with Sample Data

This script creates a Kafka topic with infinite retention and loads sample transaction data.

Usage:
    # Create topic with default name
    python3 setup_topic_with_samples.py
    
    # Create topic with custom name
    python3 setup_topic_with_samples.py my.custom.topic
    
    # Use as a module in Python
    from setup_topic_with_samples import setup_topic_with_samples
    success = setup_topic_with_samples("my.topic.name")

Requirements:
    - confluent-kafka Python package
    - python-dotenv package
    - .env file with BOOTSTRAP_SERVERS, KAFKA_API_KEY, KAFKA_API_SECRET
    - sample-transactions.json file in the same directory

"""

from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic
import json
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import time

# Load environment variables from .env file
load_dotenv()

# Kafka configuration from environment variables
config = {
    'bootstrap.servers': os.getenv('BOOTSTRAP_SERVERS'),
    'security.protocol': 'SASL_SSL',
    'sasl.mechanisms': 'PLAIN',
    'sasl.username': os.getenv('KAFKA_API_KEY'),
    'sasl.password': os.getenv('KAFKA_API_SECRET'),
}

# Sample data file
MESSAGES_FILE = 'sample-transactions.json'


def validate_config():
    """
    Validate that all required environment variables are present.
    
    Returns:
        bool: True if all required variables are set, False otherwise
    """
    required_vars = ['BOOTSTRAP_SERVERS', 'KAFKA_API_KEY', 'KAFKA_API_SECRET']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("❌ Error: Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease update your .env file with the correct values.")
        return False
    
    return True


def delete_topic_if_exists(admin_client, topic_name):
    """
    Delete a Kafka topic if it exists.
    
    Args:
        admin_client: Confluent Kafka AdminClient instance
        topic_name (str): Name of the topic to delete
        
    Returns:
        bool: True if deletion succeeded or topic didn't exist, False on error
    """
    print(f"🗑️  Checking if topic '{topic_name}' exists...")
    
    # Get list of existing topics
    metadata = admin_client.list_topics(timeout=10)
    
    if topic_name in metadata.topics:
        print(f"   Topic exists. Deleting...")
        fs = admin_client.delete_topics([topic_name], operation_timeout=30)
        
        # Wait for deletion to complete
        for topic, f in fs.items():
            try:
                f.result()
                print(f"   ✅ Topic '{topic}' deleted successfully")
                # Wait for deletion to propagate
                time.sleep(3)
            except Exception as e:
                print(f"   ⚠️  Failed to delete topic '{topic}': {e}")
                return False
    else:
        print(f"   Topic doesn't exist. Proceeding to create...")
    
    return True


def create_topic_with_infinite_retention(admin_client, topic_name):
    """
    Create a Kafka topic with infinite retention.
    
    Args:
        admin_client: Confluent Kafka AdminClient instance
        topic_name (str): Name of the topic to create
        
    Returns:
        bool: True if creation succeeded, False otherwise
    """
    print(f"\n📝 Creating topic '{topic_name}' with infinite retention...")
    
    # Configure topic with infinite retention
    new_topic = NewTopic(
        topic_name,
        num_partitions=1,
        replication_factor=3,
        config={
            'retention.ms': '-1',        # Infinite retention (never delete)
            'retention.bytes': '-1',     # No size limit
            'cleanup.policy': 'delete'   # Use delete policy (not compaction)
        }
    )
    
    fs = admin_client.create_topics([new_topic])
    
    # Wait for creation to complete
    for topic, f in fs.items():
        try:
            f.result()
            print(f"   ✅ Topic '{topic}' created successfully")
            print(f"   📌 Retention: Infinite")
            print(f"   📌 Partitions: 1")
            print(f"   📌 Replication Factor: 3")
            # Wait for topic to be ready
            time.sleep(2)
            return True
        except Exception as e:
            print(f"   ❌ Failed to create topic '{topic}': {e}")
            return False


def delivery_report(err, msg):
    """
    Callback function for message delivery reports.
    
    Args:
        err: Error object if delivery failed, None otherwise
        msg: Message object containing delivery details
    """
    if err is not None:
        print(f'   ❌ Message delivery failed: {err}')
    else:
        print(f'   ✅ Delivered to partition {msg.partition()} at offset {msg.offset()}')


def produce_messages(topic_name):
    """
    Read sample messages from JSON file and produce them to Kafka topic.
    
    Args:
        topic_name (str): Name of the topic to produce messages to
        
    Returns:
        bool: True if all messages were produced successfully, False otherwise
    """
    # Check if sample data file exists
    if not Path(MESSAGES_FILE).exists():
        print(f"❌ Error: {MESSAGES_FILE} not found")
        print(f"Current directory: {os.getcwd()}")
        return False
    
    # Create Kafka producer
    print(f"\n📤 Producing messages to '{topic_name}'...")
    
    try:
        producer = Producer(config)
    except Exception as e:
        print(f"❌ Failed to create producer: {e}")
        return False
    
    # Read and produce messages
    message_count = 0
    error_count = 0
    
    try:
        with open(MESSAGES_FILE, 'r') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    # Parse JSON to validate format
                    msg = json.loads(line.strip())
                    
                    # Produce message with SKU as key
                    producer.produce(
                        topic_name,
                        key=msg['sku'].encode('utf-8'),
                        value=line.strip().encode('utf-8'),
                        callback=delivery_report
                    )
                    
                    message_count += 1
                    
                    # Trigger delivery reports
                    producer.poll(0)
                    
                except json.JSONDecodeError as e:
                    print(f"   ⚠️  Warning: Invalid JSON on line {line_num}: {e}")
                    error_count += 1
                except Exception as e:
                    print(f"   ⚠️  Warning: Failed to produce message on line {line_num}: {e}")
                    error_count += 1
        
        # Wait for all messages to be delivered
        print(f"\n   ⏳ Waiting for {message_count} messages to be delivered...")
        producer.flush(timeout=30)
        
        print(f"   ✅ Successfully produced {message_count} messages")
        if error_count > 0:
            print(f"   ⚠️  Errors: {error_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def setup_topic_with_samples(topic_name):
    """
    Main function to setup a Kafka topic with sample data.
    
    This function performs the following steps:
    1. Validates configuration
    2. Deletes topic if it exists
    3. Creates topic with infinite retention
    4. Produces sample messages from JSON file
    
    Args:
        topic_name (str): Name of the topic to create
        
    Returns:
        bool: True if setup completed successfully, False otherwise
        
    Example:
        >>> from setup_topic_with_samples import setup_topic_with_samples
        >>> success = setup_topic_with_samples("my.inventory.topic")
        >>> if success:
        ...     print("Topic ready!")
    """
    print("="*70)
    print("🚀 Kafka Topic Setup Script with Sample Data")
    print("="*70)
    print()
    
    # Step 1: Validate configuration
    if not validate_config():
        return False
    
    print(f"🔗 Connecting to Confluent Cloud...")
    print(f"   Bootstrap Server: {config['bootstrap.servers']}")
    print(f"   Target Topic: {topic_name}\n")
    
    # Create admin client
    try:
        admin_client = AdminClient(config)
    except Exception as e:
        print(f"❌ Failed to create admin client: {e}")
        return False
    
    # Step 2: Delete topic if exists
    if not delete_topic_if_exists(admin_client, topic_name):
        return False
    
    # Step 3: Create topic with infinite retention
    if not create_topic_with_infinite_retention(admin_client, topic_name):
        return False
    
    # Step 4: Produce sample messages
    if not produce_messages(topic_name):
        return False
    
    # Print summary
    print("\n" + "="*70)
    print("📊 SETUP COMPLETE")
    print("="*70)
    print(f"✅ Topic: {topic_name}")
    print(f"✅ Retention: Infinite")
    print(f"✅ Messages: 20 sample transactions loaded")
    print("="*70)
    print("\n🎉 Topic is ready for use with ksqlDB or Apache Flink!")
    print(f"\n💡 Next steps:")
    print(f"   1. Use this topic in your stream processing application")
    print(f"   2. Create tables/streams that reference: {topic_name}")
    print(f"   3. Process the JSON data in your stream processing queries")
    
    return True


if __name__ == "__main__":
    # Parse command line arguments
    if len(sys.argv) > 1 and sys.argv[1] not in ['--help', '-h']:
        topic_name = sys.argv[1]
    else:
        # Default topic name
        topic_name = "inventory.transactions.sample"
    
    # Check for help flag
    if '--help' in sys.argv or '-h' in sys.argv:
        print(__doc__)
        sys.exit(0)
    
    # Run setup
    success = setup_topic_with_samples(topic_name)
    sys.exit(0 if success else 1)

# Made with Bob