#!/usr/bin/env python3
"""
Quick Orderbook Infrastructure Test

Tests both Kalshi and Polymarket orderbook depth APIs
to ensure everything is ready for Sunday data collection.

Run this 1 hour before games start to verify infrastructure.
"""

import json
import sys
from datetime import datetime
from kalshi_client import KalshiClient
from polymarket_client import PolymarketClient

def format_orderbook_levels(orders, max_levels=5):
    """Format orderbook levels for display"""
    lines = []
    for i, level in enumerate(orders[:max_levels], 1):
        if len(level) == 2:  # Polymarket format (price, size)
            price, size = level
            lines.append(f"    {i}. ${price:.3f} × {size:,.0f} contracts")
        elif len(level) == 3:  # Kalshi format (price, size, count)
            price, size, count = level
            lines.append(f"    {i}. ${price:.3f} × {size:,.0f} contracts ({count} orders)")
    return lines

def test_vwap_tiers(client, orders, side_name):
    """Test VWAP at different trade sizes"""
    test_sizes = [100, 500, 1000, 2000, 5000]
    
    print(f"\n  💰 VWAP Analysis ({side_name}):")
    print("  " + "-" * 60)
    
    for size in test_sizes:
        vwap, filled, remaining, slippage = client.calculate_vwap(orders, size)
        
        if vwap and filled == size:
            print(f"    ${size:,} trade: ${vwap:.4f} VWAP | Slippage: {slippage:.2f}% ✅")
        elif vwap and filled > 0:
            print(f"    ${size:,} trade: ${vwap:.4f} VWAP | Filled: {filled:,}/{size:,} | Slippage: {slippage:.2f}% ⚠️")
        else:
            print(f"    ${size:,} trade: Insufficient liquidity ❌")

def main():
    print("=" * 100)
    print("🔬 ORDERBOOK INFRASTRUCTURE TEST - v2.5-depth")
    print("=" * 100)
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Load config
    try:
        with open('config/settings.json', 'r') as f:
            config = json.load(f)
        
        with open('config/markets.json', 'r') as f:
            markets_data = json.load(f)
            markets = markets_data.get('markets', [])
    except FileNotFoundError as e:
        print(f"\n❌ Config file not found: {e}")
        print("Make sure you're running from the data-logger-v2.5-depth directory")
        sys.exit(1)
    
    if not markets:
        print("\n❌ No markets configured!")
        sys.exit(1)
    
    # Pick first market for testing
    test_market = markets[0]
    test_game = test_market['description']
    kalshi_ticker = test_market['kalshi']['markets']['main']
    poly_slug = test_market['polymarket']['markets']['slug']
    
    print(f"\n🏈 Test Game: {test_game}")
    print(f"   Kalshi: {kalshi_ticker}")
    print(f"   Polymarket: {poly_slug}")
    
    # Initialize clients
    print("\n" + "=" * 100)
    print("📡 INITIALIZING CLIENTS")
    print("=" * 100)
    
    try:
        kalshi = KalshiClient(
            api_key=config['kalshi']['api_key'],
            private_key_path=config['kalshi']['private_key_path']
        )
        kalshi_ok = True
    except Exception as e:
        print(f"❌ Kalshi client failed: {e}")
        kalshi_ok = False
        kalshi = None
    
    try:
        polymarket = PolymarketClient()
        poly_ok = True
    except Exception as e:
        print(f"❌ Polymarket client failed: {e}")
        poly_ok = False
        polymarket = None
    
    # Test Kalshi Orderbook
    print("\n" + "=" * 100)
    print("🔍 TESTING KALSHI ORDERBOOK")
    print("=" * 100)
    
    kalshi_depth_ok = False
    if kalshi_ok and kalshi:
        try:
            print(f"\nFetching orderbook for: {kalshi_ticker}")
            print("-" * 100)
            
            orderbook = kalshi.get_market_orderbook(kalshi_ticker, depth=10)
            
            if orderbook and (orderbook['yes_asks'] or orderbook['no_asks']):
                print("\n✅ Kalshi orderbook retrieved successfully!")
                
                # Display YES side
                if orderbook['yes_asks']:
                    print("\n  📊 YES Side:")
                    print(f"     Bids: {len(orderbook['yes_bids'])} levels")
                    print("\n".join(format_orderbook_levels(orderbook['yes_bids'])))
                    print(f"\n     Asks: {len(orderbook['yes_asks'])} levels")
                    print("\n".join(format_orderbook_levels(orderbook['yes_asks'])))
                    
                    test_vwap_tiers(kalshi, orderbook['yes_asks'], "YES Asks")
                
                # Display NO side
                if orderbook['no_asks']:
                    print("\n  📊 NO Side:")
                    print(f"     Bids: {len(orderbook['no_bids'])} levels")
                    print("\n".join(format_orderbook_levels(orderbook['no_bids'])))
                    print(f"\n     Asks: {len(orderbook['no_asks'])} levels")
                    print("\n".join(format_orderbook_levels(orderbook['no_asks'])))
                    
                    test_vwap_tiers(kalshi, orderbook['no_asks'], "NO Asks")
                
                kalshi_depth_ok = True
            else:
                print("\n⚠️  Kalshi orderbook is empty (game may not have started yet)")
                print("    This is NORMAL before games begin.")
                print("    Test again 1 hour before kickoff.")
                kalshi_depth_ok = "pending"
                
        except Exception as e:
            print(f"\n❌ Kalshi orderbook test failed: {e}")
            kalshi_depth_ok = False
    else:
        print("\n❌ Kalshi client not available")
    
    # Test Polymarket Orderbook
    print("\n" + "=" * 100)
    print("🔍 TESTING POLYMARKET ORDERBOOK")
    print("=" * 100)
    
    poly_depth_ok = False
    if poly_ok and polymarket:
        try:
            print(f"\nStep 1: Fetching token IDs for: {poly_slug}")
            print("-" * 100)
            
            token_data = polymarket.get_token_ids_from_slug(poly_slug)
            
            if token_data and token_data['tokens']:
                print(f"\n✅ Token IDs retrieved!")
                print(f"   Condition ID: {token_data['condition_id']}")
                
                for token in token_data['tokens']:
                    print(f"\n   {token['outcome']}:")
                    print(f"      Token ID: {token['token_id']}")
                    print(f"      Current Price: ${token['price']:.3f}" if token['price'] else "      Price: N/A")
                
                # Test orderbook for both outcomes
                poly_depth_ok = True
                for token in token_data['tokens']:
                    print(f"\n{'=' * 100}")
                    print(f"Step 2: Fetching orderbook for {token['outcome']}")
                    print("-" * 100)
                    
                    orderbook = polymarket.get_orderbook(token['token_id'])
                    
                    if orderbook and (orderbook['bids'] or orderbook['asks']):
                        print(f"\n✅ {token['outcome']} orderbook retrieved!")
                        
                        print(f"\n  📊 Bids (buy orders): {len(orderbook['bids'])} levels")
                        print("\n".join(format_orderbook_levels(orderbook['bids'])))
                        
                        print(f"\n  📊 Asks (sell orders): {len(orderbook['asks'])} levels")
                        print("\n".join(format_orderbook_levels(orderbook['asks'])))
                        
                        test_vwap_tiers(polymarket, orderbook['asks'], f"{token['outcome']} Asks")
                    else:
                        print(f"\n⚠️  {token['outcome']} orderbook is empty")
                        poly_depth_ok = "partial"
            else:
                print("\n❌ Failed to retrieve token IDs")
                poly_depth_ok = False
                
        except Exception as e:
            print(f"\n❌ Polymarket orderbook test failed: {e}")
            poly_depth_ok = False
    else:
        print("\n❌ Polymarket client not available")
    
    # Summary
    print("\n" + "=" * 100)
    print("📋 TEST SUMMARY")
    print("=" * 100)
    
    print(f"\n✓ Configuration:")
    print(f"  - Markets configured: {len(markets)} games")
    print(f"  - Test game: {test_game}")
    
    print(f"\n✓ Client Initialization:")
    print(f"  - Kalshi: {'✅ OK' if kalshi_ok else '❌ FAILED'}")
    print(f"  - Polymarket: {'✅ OK' if poly_ok else '❌ FAILED'}")
    
    print(f"\n✓ Orderbook Depth:")
    if kalshi_depth_ok == "pending":
        print(f"  - Kalshi: ⏳ PENDING (test before games start)")
    else:
        print(f"  - Kalshi: {'✅ WORKING' if kalshi_depth_ok else '❌ FAILED'}")
    
    if poly_depth_ok == "partial":
        print(f"  - Polymarket: ⚠️  PARTIAL (some data available)")
    else:
        print(f"  - Polymarket: {'✅ WORKING' if poly_depth_ok else '❌ FAILED'}")
    
    # Overall status
    print("\n" + "=" * 100)
    
    if kalshi_ok and poly_ok and (kalshi_depth_ok == "pending" or kalshi_depth_ok) and poly_depth_ok:
        print("🎉 INFRASTRUCTURE STATUS: ✅ READY!")
        print("=" * 100)
        print("\nAll systems operational. Ready for Sunday data collection.")
        if kalshi_depth_ok == "pending":
            print("\n⏰ Note: Run this test again 1 hour before games start to verify")
            print("   Kalshi orderbook depth when markets are active.")
        print("\n🚀 To start data collection:")
        print("   caffeinate -i python3 data_logger.py --hours 24")
    elif kalshi_ok and poly_ok:
        print("⚠️  INFRASTRUCTURE STATUS: PARTIALLY READY")
        print("=" * 100)
        print("\nClients working, but orderbook depth needs verification.")
        print("Run this test again when markets are more active (1 hour before games).")
    else:
        print("❌ INFRASTRUCTURE STATUS: NOT READY")
        print("=" * 100)
        print("\nSome components failed. Check errors above.")
    
    # Cleanup
    if kalshi:
        kalshi.close()
    if polymarket:
        polymarket.close()
    
    print()

if __name__ == "__main__":
    main()

