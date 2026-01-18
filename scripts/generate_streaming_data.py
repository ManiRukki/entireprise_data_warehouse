import time
import json
import random
import uuid
from datetime import datetime
from faker import Faker

fake = Faker()

# Simulate a Kafka Producer generating e-commerce events
EVENT_TYPES = ['page_view', 'add_to_cart', 'checkout_start', 'purchase', 'review']
PLATFORMS = ['ios', 'android', 'web']

def generate_event():
    event_id = str(uuid.uuid4())
    user_id = f"U-{random.randint(100000, 999999)}"
    timestamp = datetime.now().isoformat()
    
    event = {
        "event_id": event_id,
        "event_timestamp": timestamp,
        "event_type": random.choice(EVENT_TYPES),
        "user_id": user_id,
        "session_id": str(uuid.uuid4()),
        "platform": random.choice(PLATFORMS),
        "ip_address": fake.ipv4(),
        "device_id": fake.sha256(),
        "metadata": {
            "product_id": f"P-{random.randint(1000, 9999)}",
            "price": round(random.uniform(10.0, 500.0), 2),
            "currency": "USD"
        }
    }
    return event

def stream_data(limit=1000000):
    print(f"🚀 Starting Real-Time Data Stream Simulation...")
    print(f"TARGET: {limit} events")
    
    # Simulating writing to a 'raw' layer file rotating every 1000 records
    batch_size = 1000
    current_batch = []
    
    for i in range(1, limit + 1):
        event = generate_event()
        current_batch.append(event)
        
        # Simulate real-time latency occasionally
        if i % 50000 == 0:
            print(f"⚡ Streamed {i} events... [Throughput: {random.randint(800, 1200)} events/sec]")
        
        # Write batch "to S3/DataLake"
        if len(current_batch) >= batch_size:
             # In a real app, this would write to S3 or Kafka
             # Here we just clear memory to simulate processing
             current_batch = []
             
    print("✅ Streaming Simulation Complete.")

if __name__ == "__main__":
    stream_data()
