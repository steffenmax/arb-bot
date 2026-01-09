#!/usr/bin/env python3
"""
Polymarket Token ID Sanity Check
Verifies all token IDs in markets.json have valid orderbooks
"""

import json
import requests
import sys
from pathlib import Path

def load_markets():
    """Load markets.json and extract all Polymarket token IDs"""
    markets_path = Path(__file__).parent.parent / "config" / "markets.json"
    
    with open(markets_path, 'r') as f:
        config = json.load(f)
    
    tokens = []
    for market in config.get('markets', []):
        event_id = market.get('event_id', '')
        poly_tokens = market.get('poly_token_ids', {})
        
        for team, token_id in poly_tokens.items():
            if token_id:
                tokens.append({
                    'event_id': event_id,
                    'team': team,
                    'token_id': str(token_id)
                })
    
    return tokens

def check_token_orderbook(token_id: str):
    """
    Fetch orderbook for a token ID
    Returns: (best_bid, best_ask, bid_count, ask_count) or None on error
    """
    url = f"https://clob.polymarket.com/book?token_id={token_id}"
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            return None
        
        data = response.json()
        bids = data.get('bids', [])
        asks = data.get('asks', [])
        
        best_bid = float(bids[0]['price']) if bids else None
        best_ask = float(asks[0]['price']) if asks else None
        
        return (best_bid, best_ask, len(bids), len(asks))
    
    except Exception as e:
        print(f"  ✗ Error fetching {token_id[:20]}...: {e}")
        return None

def main():
    print("="*70)
    print("POLYMARKET TOKEN ID SANITY CHECK")
    print("="*70)
    
    tokens = load_markets()
    print(f"\nFound {len(tokens)} token IDs in markets.json\n")
    
    if len(tokens) == 0:
        print("⚠️  No Polymarket token IDs found. Run resolve_markets_v2.py first.")
        return
    
    valid_count = 0
    empty_count = 0
    error_count = 0
    
    for item in tokens:
        token_id = item['token_id']
        event_id = item['event_id']
        team = item['team']
        
        print(f"\n[{event_id}] {team}")
        print(f"  Token: {token_id[:30]}...")
        
        result = check_token_orderbook(token_id)
        
        if result is None:
            print(f"  ✗ ERROR: Failed to fetch orderbook")
            error_count += 1
        else:
            best_bid, best_ask, bid_count, ask_count = result
            
            if best_bid is None and best_ask is None:
                print(f"  ⚠️  EMPTY: No bids or asks")
                empty_count += 1
            else:
                print(f"  ✓ VALID: Bid ${best_bid} / Ask ${best_ask}")
                print(f"    Depth: {bid_count} bids, {ask_count} asks")
                valid_count += 1
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Total tokens checked: {len(tokens)}")
    print(f"Valid (non-empty):    {valid_count}")
    print(f"Empty orderbooks:     {empty_count}")
    print(f"Errors:               {error_count}")
    print()
    
    if valid_count == 0:
        print("⚠️  WARNING: No valid Polymarket orderbooks found!")
        print("   This is expected if Polymarket doesn't have active markets.")
        sys.exit(1)
    elif valid_count < len(tokens):
        print("⚠️  Some tokens have no liquidity. Bot will only show prices for valid tokens.")
        sys.exit(0)
    else:
        print("✓ All tokens have valid orderbooks!")
        sys.exit(0)

if __name__ == "__main__":
    main()

