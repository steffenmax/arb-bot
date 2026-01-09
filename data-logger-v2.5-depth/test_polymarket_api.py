#!/usr/bin/env python3
"""
Test Polymarket API to debug 422 errors
"""

import requests
import json

print("=" * 70)
print("TESTING POLYMARKET API")
print("=" * 70)
print()

# Test condition ID (Portland vs OKC)
condition_id = "0xf1b682404d9a324e94c9d3cccf4869e12331553fd638835f5c1656115dbb670e"

print(f"Testing condition ID: {condition_id[:20]}...")
print()

# Step 1: Get market info from Gamma API
print("STEP 1: Fetching market from Gamma API")
print("-" * 70)

try:
    response = requests.get(
        f"https://gamma-api.polymarket.com/markets/{condition_id}",
        timeout=10
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        market = response.json()
        print("✓ Successfully fetched market data")
        print()
        
        # Check for clobTokenIds
        print("Checking for clobTokenIds...")
        has_token_ids = 'clobTokenIds' in market
        print(f"  Has clobTokenIds field: {has_token_ids}")
        
        if has_token_ids:
            token_ids = market['clobTokenIds']
            print(f"  Token IDs type: {type(token_ids)}")
            
            # Parse if string
            if isinstance(token_ids, str):
                print("  Token IDs is a string, parsing JSON...")
                token_ids = json.loads(token_ids)
            
            print(f"  Token IDs: {token_ids}")
            print()
            
            if isinstance(token_ids, list) and len(token_ids) >= 2:
                yes_token = token_ids[0]
                no_token = token_ids[1]
                
                print(f"  YES token: {yes_token}")
                print(f"  NO token:  {no_token}")
                print()
                
                # Step 2: Test CLOB API
                print("STEP 2: Fetching orderbook from CLOB API")
                print("-" * 70)
                
                ob_response = requests.get(
                    "https://clob.polymarket.com/book",
                    params={'token_id': yes_token},
                    timeout=10
                )
                
                print(f"Status Code: {ob_response.status_code}")
                
                if ob_response.status_code == 200:
                    ob_data = ob_response.json()
                    print("✓ Successfully fetched orderbook")
                    print()
                    
                    bids = ob_data.get('bids', [])
                    asks = ob_data.get('asks', [])
                    
                    print(f"  Bids: {len(bids)} orders")
                    print(f"  Asks: {len(asks)} orders")
                    
                    if bids and asks:
                        best_bid = float(bids[0]['price'])
                        best_ask = float(asks[0]['price'])
                        mid = (best_bid + best_ask) / 2
                        
                        print()
                        print(f"  Best Bid: ${best_bid:.4f}")
                        print(f"  Best Ask: ${best_ask:.4f}")
                        print(f"  Mid Price: ${mid:.4f}")
                        print()
                        print("=" * 70)
                        print("✅ SUCCESS! Both APIs work correctly")
                        print("=" * 70)
                        print()
                        print("The polymarket_client.py code should work!")
                    else:
                        print()
                        print("⚠️  Warning: No bids or asks in orderbook")
                else:
                    print(f"✗ CLOB API failed")
                    print(f"Response: {ob_response.text[:200]}")
                    print()
                    print("=" * 70)
                    print("❌ FAILED at CLOB API step")
                    print("=" * 70)
            else:
                print("✗ Token IDs is not a list or has < 2 items")
                print(f"  Value: {token_ids}")
        else:
            print("✗ No clobTokenIds field in response")
            print()
            print("Available fields:")
            for key in list(market.keys())[:10]:
                print(f"  - {key}")
            
            print()
            print("=" * 70)
            print("❌ FAILED - No token IDs in response")
            print("=" * 70)
            print()
            print("Possible reasons:")
            print("  1. API response structure changed")
            print("  2. Condition ID is invalid or market closed")
            print("  3. Need different endpoint")
    
    elif response.status_code == 422:
        print("✗ Got 422 error from Gamma API")
        print(f"Response: {response.text[:200]}")
        print()
        print("=" * 70)
        print("❌ FAILED - 422 Error")
        print("=" * 70)
        print()
        print("Possible reasons:")
        print("  1. Condition ID format wrong")
        print("  2. Market doesn't exist")
        print("  3. API endpoint changed")
    else:
        print(f"✗ Unexpected status code: {response.status_code}")
        print(f"Response: {response.text[:200]}")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    print()
    print("=" * 70)
    print("❌ EXCEPTION")
    print("=" * 70)

print()

