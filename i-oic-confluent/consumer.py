import json
import os
from queue import Queue

from confluent_kafka import Consumer


def start_consumer(queue: Queue):
    consumer = Consumer(
        {
            "bootstrap.servers": os.environ["BOOTSTRAP_SERVER"],
            "security.protocol": "SASL_SSL",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": os.environ["API_KEY"],
            "sasl.password": os.environ["API_SECRET"],
            "group.id": "wxo-agent-consumer-v2",
            "auto.offset.reset": "earliest",
        }
    )

    consumer.subscribe(["inventory-events"])

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"Kafka error: {msg.error()}")
                continue

            event = json.loads(msg.value().decode("utf-8"))
            queue.put(event)

    finally:
        consumer.close()
