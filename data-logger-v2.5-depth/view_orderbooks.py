#!/usr/bin/env python3
"""
Quick Orderbook Comparison - Arizona vs LA Rams
Shows side-by-side orderbooks from Kalshi and Polymarket
"""

import json
from kalshi_client import KalshiClient
from polymarket_client import PolymarketClient

def format_orderbook_table(title, bids, asks, max_rows=10):
    """Format orderbook as a table"""
    print(f"\n{title}")
    print("=" * 80)
    print(f"{'BIDS (Buy Orders)':^40} | {'ASKS (Sell Orders)':^40}")
    print(f"{'Price':>15} {'Size':>20} | {'Price':>15} {'Size':>20}")
    print("-" * 80)
    
    max_len = max(len(bids), len(asks), max_rows)
    for i in range(min(max_len, max_rows)):
        # Bids
        if i < len(bids):
            bid_price, bid_size = bids[i][0], bids[i][1]
            bid_str = f"${bid_price:>6.2f} {bid_size:>20,}"
        else:
            bid_str = " " * 40
        
        # Asks
        if i < len(asks):
            ask_price, ask_size = asks[i][0], asks[i][1]
            ask_str = f"${ask_price:>6.2f} {ask_size:>20,}"
        else:
            ask_str = " " * 40
        
        print(f"{bid_str} | {ask_str}")

# Load config
with open('config/settings.json', 'r') as f:
    config = json.load(f)

print("=" * 100)
print("🏈 ARIZONA vs LA RAMS - ORDERBOOK COMPARISON")
print("=" * 100)

# Initialize clients
kalshi = KalshiClient(
    api_key=config['kalshi']['api_key'],
    private_key_path=config['kalshi']['private_key_path']
)
polymarket = PolymarketClient()

print("\n" + "=" * 100)
print("📊 KALSHI ORDERBOOKS")
print("=" * 100)

# Get Kalshi orderbooks for both markets
arizona_ticker = "KXNFLGAME-26JAN04ARILA-ARI"
rams_ticker = "KXNFLGAME-26JAN04ARILA-LA"

ari_raw = kalshi._make_request('GET', f'/markets/{arizona_ticker}/orderbook', params={'depth': 10})
rams_raw = kalshi._make_request('GET', f'/markets/{rams_ticker}/orderbook', params={'depth': 10})

if ari_raw and rams_raw:
    ari_ob = ari_raw['orderbook']
    rams_ob = rams_raw['orderbook']
    
    # Arizona YES orderbook (Arizona to win)
    print("\n🔵 ARIZONA YES (to buy Arizona to win)")
    arizona_yes_bids = [(float(p), s) for p, s in ari_ob.get('yes_dollars', [])]
    # Arizona YES asks come from Arizona NO bids: NO bid at X = YES ask at (1-X)
    arizona_yes_asks = [(1.0 - float(p), s) for p, s in ari_ob.get('no_dollars', [])]
    arizona_yes_asks.sort()  # Sort by price ascending
    
    format_orderbook_table("Arizona YES Orderbook (Kalshi)", arizona_yes_bids[:10], arizona_yes_asks[:10])
    
    # Arizona NO orderbook (Arizona to lose = Rams to win)
    print("\n\n🔴 ARIZONA NO (to buy Arizona to lose)")
    arizona_no_bids = [(float(p), s) for p, s in ari_ob.get('no_dollars', [])]
    # Arizona NO asks come from Arizona YES bids: YES bid at X = NO ask at (1-X)
    arizona_no_asks = [(1.0 - float(p), s) for p, s in ari_ob.get('yes_dollars', [])]
    arizona_no_asks.sort()  # Sort by price ascending
    
    format_orderbook_table("Arizona NO Orderbook (Kalshi)", arizona_no_bids[:10], arizona_no_asks[:10])
    
    # LA Rams YES orderbook (Rams to win)
    print("\n\n🔵 LA RAMS YES (to buy LA Rams to win)")
    rams_yes_bids = [(float(p), s) for p, s in rams_ob.get('yes_dollars', [])]
    # Rams YES asks come from Rams NO bids: NO bid at X = YES ask at (1-X)
    rams_yes_asks = [(1.0 - float(p), s) for p, s in rams_ob.get('no_dollars', [])]
    rams_yes_asks.sort()  # Sort by price ascending
    
    format_orderbook_table("LA Rams YES Orderbook (Kalshi)", rams_yes_bids[:10], rams_yes_asks[:10])
    
    # LA Rams NO orderbook (Rams to lose = Arizona to win)
    print("\n\n🔴 LA RAMS NO (to buy LA Rams to lose)")
    rams_no_bids = [(float(p), s) for p, s in rams_ob.get('no_dollars', [])]
    # Rams NO asks come from Rams YES bids: YES bid at X = NO ask at (1-X)
    rams_no_asks = [(1.0 - float(p), s) for p, s in rams_ob.get('yes_dollars', [])]
    rams_no_asks.sort()  # Sort by price ascending
    
    format_orderbook_table("LA Rams NO Orderbook (Kalshi)", rams_no_bids[:10], rams_no_asks[:10])

print("\n\n" + "=" * 100)
print("📊 POLYMARKET ORDERBOOKS")
print("=" * 100)

# Get Polymarket orderbook
poly_slug = "nfl-ari-la-2026-01-04"
token_data = polymarket.get_token_ids_from_slug(poly_slug)

if token_data and token_data['tokens']:
    for token in token_data['tokens']:
        team_name = token['outcome']
        token_id = token['token_id']
        current_price = token['price']
        
        print(f"\n{'🔵' if 'Cardinals' in team_name else '🔴'} {team_name.upper()}")
        print(f"Current Price: ${current_price:.2f}")
        
        # Get orderbook
        orderbook = polymarket.get_orderbook(token_id)
        
        if orderbook:
            bids = orderbook['bids']
            asks = orderbook['asks']
            
            format_orderbook_table(f"{team_name} Orderbook (Polymarket)", bids[:10], asks[:10])
            
            # VWAP analysis
            print(f"\n💰 Trade Cost Analysis (buying {team_name} YES):")
            print("-" * 80)
            for size in [100, 500, 1000, 2000, 5000]:
                vwap, filled, remaining, slippage = polymarket.calculate_vwap(asks, size)
                if vwap and filled == size:
                    print(f"  {size:>5,} contracts: ${vwap:.4f} VWAP | Slippage: {slippage:>5.2f}% | Cost: ${vwap * size:>10,.2f}")
                elif vwap:
                    print(f"  {size:>5,} contracts: ${vwap:.4f} VWAP | Filled: {filled:,}/{size:,} | ⚠️  Partial fill")
                else:
                    print(f"  {size:>5,} contracts: ❌ Insufficient liquidity")

# Summary
print("\n\n" + "=" * 100)
print("📊 SUMMARY")
print("=" * 100)

# Get current top-of-book prices
ari_market = kalshi.get_market(arizona_ticker)
rams_market = kalshi.get_market(rams_ticker)

print("\n🏈 Current Market Prices:")
print("-" * 100)
print(f"{'Platform':<15} {'Arizona':^30} {'LA Rams':^30}")
print(f"{'':15} {'Bid':>12} {'Ask':>12} {'Spread':>6} {'Bid':>12} {'Ask':>12} {'Spread':>6}")
print("-" * 100)

kalshi_ari_spread = f"{((ari_market['yes_ask'] - ari_market['yes_bid']) / ari_market['yes_bid'] * 100):.1f}%"
kalshi_rams_spread = f"{((rams_market['yes_ask'] - rams_market['yes_bid']) / rams_market['yes_bid'] * 100):.1f}%"

print(f"{'Kalshi':<15} ${ari_market['yes_bid']:>10.2f} ${ari_market['yes_ask']:>10.2f} {kalshi_ari_spread:>6} "
      f"${rams_market['yes_bid']:>10.2f} ${rams_market['yes_ask']:>10.2f} {kalshi_rams_spread:>6}")

if token_data and len(token_data['tokens']) == 2:
    ari_token = [t for t in token_data['tokens'] if 'Cardinals' in t['outcome']][0]
    rams_token = [t for t in token_data['tokens'] if 'Rams' in t['outcome']][0]
    
    ari_ob = polymarket.get_orderbook(ari_token['token_id'])
    rams_ob = polymarket.get_orderbook(rams_token['token_id'])
    
    if ari_ob and rams_ob and ari_ob['bids'] and ari_ob['asks'] and rams_ob['bids'] and rams_ob['asks']:
        poly_ari_bid = ari_ob['bids'][0][0]
        poly_ari_ask = ari_ob['asks'][0][0]
        poly_ari_spread = f"{((poly_ari_ask - poly_ari_bid) / poly_ari_bid * 100):.1f}%"
        
        poly_rams_bid = rams_ob['bids'][0][0]
        poly_rams_ask = rams_ob['asks'][0][0]
        poly_rams_spread = f"{((poly_rams_ask - poly_rams_bid) / poly_rams_bid * 100):.1f}%"
        
        print(f"{'Polymarket':<15} ${poly_ari_bid:>10.2f} ${poly_ari_ask:>10.2f} {poly_ari_spread:>6} "
              f"${poly_rams_bid:>10.2f} ${poly_rams_ask:>10.2f} {poly_rams_spread:>6}")

print("\n💡 Note: Kalshi uses two markets per game (one for each team)")
print("   Polymarket uses one market with two outcomes")

# Cleanup
kalshi.close()
polymarket.close()

print("\n" + "=" * 100)
print("✅ Complete!")
print("=" * 100)

