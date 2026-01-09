#!/usr/bin/env python3
"""
List ALL available NFL games to find today's games
"""

import json
import sys
sys.path.insert(0, '.')

from kalshi_client import KalshiClient
from polymarket_client import PolymarketClient
from datetime import datetime

print("=" * 80)
print("🏈 LISTING ALL AVAILABLE NFL GAMES")
print("=" * 80)

# Load credentials
with open('config/settings.json', 'r') as f:
    config = json.load(f)

# Initialize clients
kalshi = KalshiClient(
    api_key=config['kalshi']['api_key'],
    private_key_path=config['kalshi']['private_key_path']
)
polymarket = PolymarketClient()

# Get ALL NFL games from Kalshi
print("\n📋 KALSHI NFL MARKETS:")
print("-" * 80)

try:
    result = kalshi._make_request('GET', '/markets', params={
        'series_ticker': 'KXNFLGAME',
        'status': 'open',
        'limit': 200
    })
    
    if result and 'markets' in result:
        markets = result['markets']
        print(f"\nFound {len(markets)} open NFL markets\n")
        
        # Group by date
        from collections import defaultdict
        by_date = defaultdict(list)
        
        for market in markets[:20]:  # Show first 20
            ticker = market['ticker']
            title = market.get('title', '')
            close_time = market.get('close_time', '')
            
            # Extract date from ticker
            if '-' in ticker:
                parts = ticker.split('-')
                if len(parts) >= 2:
                    date_part = parts[1][:7]  # 26JAN03
                    by_date[date_part].append({
                        'ticker': ticker,
                        'title': title,
                        'close_time': close_time
                    })
        
        for date_str in sorted(by_date.keys())[:5]:  # Show next 5 dates
            print(f"\n{date_str}:")
            for game in by_date[date_str]:
                print(f"  {game['title']}")
                print(f"    {game['ticker']}")
                print(f"    Close: {game['close_time']}\n")

except Exception as e:
    print(f"Error: {e}")

# Get ALL NFL games from Polymarket
print("\n" + "=" * 80)
print("📋 POLYMARKET NFL EVENTS:")
print("-" * 80)

try:
    response = polymarket.session.get(
        f"{polymarket.gamma_api_base}/events",
        params={
            'tag_id': '450',  # NFL tag
            'closed': 'false',
            'limit': 50
        },
        timeout=10
    )
    
    if response.status_code == 200:
        events = response.json()
        print(f"\nFound {len(events)} open NFL events\n")
        
        for event in events[:15]:  # Show first 15
            slug = event.get('slug', '')
            title = event.get('title', '')
            start_date = event.get('startDate', '')
            
            print(f"{title}")
            print(f"  Slug: {slug}")
            print(f"  Date: {start_date}\n")

except Exception as e:
    print(f"Error: {e}")

kalshi.close()
polymarket.close()

print("=" * 80)
print("\n💡 Look for games with today's date (2026-01-03 or 26JAN03)")

