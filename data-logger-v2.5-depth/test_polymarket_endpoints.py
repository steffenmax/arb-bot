#!/usr/bin/env python3
"""
Test different Polymarket endpoints to find which one works
"""

import requests

print("=" * 70)
print("TESTING POLYMARKET ENDPOINTS")
print("=" * 70)
print()

# Portland vs OKC condition ID from our discovery
condition_id = "0xf1b682404d9a324e94c9d3cccf4869e12331553fd638835f5c1656115dbb670e"

print(f"Condition ID: {condition_id[:20]}...")
print()

# Try different endpoints
endpoints = [
    ("Gamma /markets", f"https://gamma-api.polymarket.com/markets/{condition_id}"),
    ("Gamma /conditions", f"https://gamma-api.polymarket.com/conditions/{condition_id}"),
    ("CLOB /markets", f"https://clob.polymarket.com/markets/{condition_id}"),
]

for name, url in endpoints:
    print(f"Testing: {name}")
    print(f"  URL: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"  ✓ SUCCESS!")
            data = response.json()
            print(f"  Keys: {list(data.keys())[:5]}")
            
            # Check for token IDs
            if 'clobTokenIds' in data:
                print(f"  Has clobTokenIds: YES")
                print(f"  Value: {data['clobTokenIds']}")
            elif 'tokens' in data:
                print(f"  Has tokens array: YES")
            break
        elif response.status_code == 422:
            print(f"  ✗ 422 Error: {response.json()}")
        else:
            print(f"  ✗ Error: {response.status_code}")
    except Exception as e:
        print(f"  ✗ Exception: {e}")
    
    print()

print()
print("=" * 70)
print("Trying to fetch by slug instead...")
print("=" * 70)
print()

# The slug we know works (from discovery script)
slug = "nba-trail-blazers-thunder-2025-12-31"
print(f"Slug: {slug}")
print()

url = f"https://gamma-api.polymarket.com/events/slug/{slug}"
print(f"URL: {url}")

try:
    response = requests.get(url, timeout=10)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        event = response.json()
        print("✓ Event fetched successfully!")
        print()
        
        markets = event.get('markets', [])
        print(f"Markets in event: {len(markets)}")
        
        if markets:
            market = markets[0]
            print()
            print("First market:")
            print(f"  conditionId: {market.get('conditionId')}")
            print(f"  question: {market.get('question')}")
            
            # Check if this matches our condition ID
            if market.get('conditionId') == condition_id:
                print("  ✓ Condition ID MATCHES!")
            else:
                print(f"  ✗ Different condition ID:")
                print(f"    Expected: {condition_id}")
                print(f"    Got:      {market.get('conditionId')}")
            
            print()
            print("Checking for token IDs...")
            if 'clobTokenIds' in market:
                token_ids = market['clobTokenIds']
                print(f"  clobTokenIds: {token_ids}")
                print(f"  Type: {type(token_ids)}")
                
                if isinstance(token_ids, str):
                    import json
                    token_ids = json.loads(token_ids)
                    print(f"  Parsed: {token_ids}")
                
                print()
                print("=" * 70)
                print("✅ SOLUTION FOUND!")
                print("=" * 70)
                print()
                print("We need to:")
                print("1. Store event SLUG (not just condition ID)")
                print("2. Fetch by slug: /events/slug/{slug}")
                print("3. Extract market data from event.markets[0]")
                print("4. Get clobTokenIds from market")
                print("5. Use CLOB API with token IDs")
            else:
                print("  ✗ No clobTokenIds in market data")
                print(f"  Available keys: {list(market.keys())}")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

print()

