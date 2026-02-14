#!/usr/bin/env python3
import requests
import json

url = "https://ec4e-2405-201-d043-7027-3012-5f61-3e3d-3fda.ngrok-free.app"

# Test different method names
methods_to_try = [
    ("tasks/run", {"input": {"prompt": "Predict maintenance for TRUCK-22"}}),
    ("tasks/run", {"prompt": "Predict maintenance for TRUCK-22"}),
    ("agent.run", {"prompt": "Predict maintenance for TRUCK-22"}),
    ("run", {"prompt": "Predict maintenance for TRUCK-22"}),
]

for method, params in methods_to_try:
    payload = {
        "jsonrpc": "2.0",
        "id": "test-1",
        "method": method,
        "params": params
    }
    
    print(f"\n{'='*60}")
    print(f"Testing method: {method}")
    print(f"Params: {json.dumps(params, indent=2)}")
    print(f"{'='*60}")
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        data = response.json()
        if "error" not in data:
            print(f"\n✅ SUCCESS! Use method='{method}' with params structure:")
            print(json.dumps(params, indent=2))
            break
    except Exception as e:
        print(f"❌ Error: {e}")