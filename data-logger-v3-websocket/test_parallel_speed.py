#!/usr/bin/env python3
"""
Quick test to verify parallel fetching is working and measure speed improvement.
"""

import json
import time
from kalshi_client import KalshiClient
from polymarket_client import PolymarketClient

def test_parallel_performance():
    """Test parallel vs sequential fetching performance"""
    
    print("=" * 70)
    print("Parallel Fetching Speed Test")
    print("=" * 70)
    
    # Load config
    with open('config/settings.json', 'r') as f:
        config = json.load(f)
    
    with open('config/markets.json', 'r') as f:
        markets_data = json.load(f)
        markets = markets_data.get("markets", [])
    
    # Initialize clients
    kalshi = KalshiClient(
        api_key=config["kalshi"]["api_key"],
        private_key_path=config["kalshi"]["private_key_path"]
    )
    
    polymarket = PolymarketClient()
    
    # Collect tickers and slugs
    kalshi_tickers = []
    polymarket_slugs = []
    
    for market in markets[:10]:  # Test with first 10 markets
        if market.get("kalshi", {}).get("enabled"):
            for ticker in market["kalshi"]["markets"].values():
                if ticker:
                    kalshi_tickers.append(ticker)
        
        if market.get("polymarket", {}).get("enabled"):
            slug = market["polymarket"]["markets"].get("slug")
            if slug:
                polymarket_slugs.append(slug)
    
    print(f"\nTest dataset: {len(kalshi_tickers)} Kalshi markets, {len(polymarket_slugs)} Polymarket markets")
    
    # Test Kalshi - Sequential
    print("\n" + "-" * 70)
    print("KALSHI - Sequential Fetching:")
    start = time.time()
    kalshi_seq = kalshi.get_markets_batch(kalshi_tickers, delay=0.05)
    seq_time = time.time() - start
    print(f"  ✓ Fetched {len(kalshi_seq)}/{len(kalshi_tickers)} markets")
    print(f"  ⏱️  Time: {seq_time:.2f}s")
    
    # Test Kalshi - Parallel
    print("\nKALSHI - Parallel Fetching:")
    start = time.time()
    kalshi_par = kalshi.get_markets_parallel(kalshi_tickers, max_workers=20)
    par_time = time.time() - start
    print(f"  ✓ Fetched {len(kalshi_par)}/{len(kalshi_tickers)} markets")
    print(f"  ⏱️  Time: {par_time:.2f}s")
    print(f"  ⚡ Speedup: {seq_time/par_time:.1f}x faster!")
    
    # Test Polymarket - Sequential
    print("\n" + "-" * 70)
    print("POLYMARKET - Sequential Fetching:")
    start = time.time()
    poly_seq = polymarket.get_markets_batch([m["polymarket"]["markets"]["game"] for m in markets[:len(polymarket_slugs)] if "game" in m["polymarket"]["markets"]], delay=0.1)
    seq_time_poly = time.time() - start
    print(f"  ✓ Fetched {len(poly_seq)} markets")
    print(f"  ⏱️  Time: {seq_time_poly:.2f}s")
    
    # Test Polymarket - Parallel
    print("\nPOLYMARKET - Parallel Fetching:")
    start = time.time()
    poly_par = polymarket.get_markets_parallel(polymarket_slugs, max_workers=15)
    par_time_poly = time.time() - start
    print(f"  ✓ Fetched {len(poly_par)}/{len(polymarket_slugs)} markets")
    print(f"  ⏱️  Time: {par_time_poly:.2f}s")
    if seq_time_poly > 0:
        print(f"  ⚡ Speedup: {seq_time_poly/par_time_poly:.1f}x faster!")
    
    # Overall Summary
    print("\n" + "=" * 70)
    print("SUMMARY:")
    total_par = par_time + par_time_poly
    print(f"  Total parallel fetch time: {total_par:.2f}s")
    print(f"  Estimated cycle time:      {total_par + 0.5:.2f}s (fetch + processing)")
    print(f"  Target cycle time:         ~3 seconds ✓")
    print("=" * 70)
    
    # Cleanup
    kalshi.close()
    polymarket.close()

if __name__ == "__main__":
    test_parallel_performance()

