#!/usr/bin/env python3
"""Debug Polymarket API calls"""

import requests
import json

# Test with one of the condition IDs from markets.json
condition_id = "0xf1b682404d9a324e94c9d3cccf4869e12331553fd638835f5c1656115dbb670e"

print(f"Testing Polymarket APIs for condition: {condition_id}\n")
print("=" * 70)

# Step 1: Get market info from CLOB API
print("\n1. Fetching market from CLOB API...")
response = requests.get(
    f"https://clob.polymarket.com/markets/{condition_id}",
    timeout=10
)

print(f"Status: {response.status_code}")

if response.status_code == 200:
    market = response.json()
    print(f"\nMarket keys: {list(market.keys())}")
    
    if 'tokens' in market:
        tokens = market['tokens']
        print(f"\nNumber of tokens: {len(tokens)}")
        print(f"\nToken 0: {json.dumps(tokens[0], indent=2)}")
        print(f"\nToken 1: {json.dumps(tokens[1], indent=2)}")
        
        # Get token IDs
        token_0_id = tokens[0].get('token_id')
        token_1_id = tokens[1].get('token_id')
        
        print(f"\nToken IDs:")
        print(f"  Token 0 ID: {token_0_id}")
        print(f"  Token 1 ID: {token_1_id}")
        
        # Step 2: Get orderbook for each token
        print("\n" + "=" * 70)
        print("\n2. Fetching orderbooks from CLOB API...")
        
        for i, token_id in enumerate([token_0_id, token_1_id]):
            print(f"\nToken {i} orderbook ({token_id}):")
            ob_response = requests.get(
                "https://clob.polymarket.com/book",
                params={'token_id': token_id},
                timeout=10
            )
            
            print(f"Status: {ob_response.status_code}")
            
            if ob_response.status_code == 200:
                ob_data = ob_response.json()
                bids = ob_data.get('bids', [])
                asks = ob_data.get('asks', [])
                
                print(f"  Bids: {len(bids)}")
                print(f"  Asks: {len(asks)}")
                
                if bids:
                    print(f"  Best bid: {bids[0]}")
                if asks:
                    print(f"  Best ask: {asks[0]}")
                
                if not bids and not asks:
                    print("  ⚠️  NO BIDS OR ASKS!")

