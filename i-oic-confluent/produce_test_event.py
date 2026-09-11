#!/usr/bin/env python3
"""
Produce test events to Kafka inventory-events topic
"""
import json
import os
from datetime import datetime
from confluent_kafka import Producer
from dotenv import load_dotenv

load_dotenv()

def create_test_event(product_id: str, quantity: int, action: str):
    """Create a test inventory event"""
    return {
        "event_id": f"test-{datetime.now().timestamp()}",
        "product_id": product_id,
        "product_name": f"Product {product_id}",
        "quantity": quantity,
        "action": action,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "warehouse": "WH-001"
    }

def delivery_callback(err, msg):
    """Callback for message delivery"""
    if err:
        print(f"ERROR: Message delivery failed: {err}")
    else:
        print(f"SUCCESS: Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}")

def produce_events(num_events=5):
    """Produce test events to Kafka"""

    # Configure producer
    conf = {
        'bootstrap.servers': os.getenv('BOOTSTRAP_SERVER'),
        'security.protocol': 'SASL_SSL',
        'sasl.mechanisms': 'PLAIN',
        'sasl.username': os.getenv('API_KEY'),
        'sasl.password': os.getenv('API_SECRET'),
    }

    producer = Producer(conf)

    print(f"Producing {num_events} test events to 'inventory-events' topic...")
    print()

    # Sample events
    events = [
        create_test_event("WIDGET-001", 100, "restock"),
        create_test_event("GADGET-002", 50, "restock"),
        create_test_event("TOOL-003", 25, "sold"),
        create_test_event("PART-004", 200, "restock"),
        create_test_event("ITEM-005", 75, "returned"),
    ]

    for i, event in enumerate(events[:num_events], 1):
        try:
            # Produce message
            producer.produce(
                topic='inventory-events',
                key=event['product_id'].encode('utf-8'),
                value=json.dumps(event).encode('utf-8'),
                callback=delivery_callback
            )

            print(f"Event {i}: {event['product_id']} - {event['action']} ({event['quantity']} units)")

            # Trigger delivery reports
            producer.poll(0)

        except Exception as e:
            print(f"ERROR: Error producing event {i}: {e}")

    # Wait for all messages to be delivered
    print()
    print("Flushing producer...")
    producer.flush(timeout=10)
    print()
    print("SUCCESS: All events produced successfully!")
    print()
    print("You can now test the agent with:")
    print("  - 'How many events are in the queue?'")
    print("  - 'Show me the next inventory event'")

if __name__ == "__main__":
    import sys
    num = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    produce_events(num)
