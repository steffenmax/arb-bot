#!/usr/bin/env python3
"""
Quick test script to verify Kalshi authentication works
"""

import json
from kalshi_client import KalshiClient

print("=" * 60)
print("Testing Kalshi Authentication")
print("=" * 60)

# Load config
with open('config/settings.json', 'r') as f:
    config = json.load(f)

kalshi_config = config['kalshi']

print(f"\nAPI Key: {kalshi_config['api_key'][:20]}...")
print(f"Private Key Path: {kalshi_config['private_key_path']}")

try:
    # Initialize client
    client = KalshiClient(
        api_key=kalshi_config['api_key'],
        private_key_path=kalshi_config['private_key_path']
    )
    
    # Test health check
    print("\nTesting API connection...")
    if client.health_check():
        print("\n✅ SUCCESS! Kalshi authentication is working!")
        
        # Try to search for a market
        print("\nSearching for NFL markets...")
        markets = client.search_markets(query="NFL", limit=5)
        if markets:
            print(f"\n✅ Found {len(markets)} markets:")
            for market in markets[:3]:
                print(f"  - {market.get('ticker')}: {market.get('title')}")
        
    else:
        print("\n❌ Health check failed. Check your credentials.")
        
except FileNotFoundError as e:
    print(f"\n❌ Error: {e}")
    print("Make sure kalshi_private_key.pem is in the parent directory")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)

