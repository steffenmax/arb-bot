#!/usr/bin/env python3
"""Quick script to check what NBA games are available"""

import json
from kalshi_client import KalshiClient

# Load config
with open('config/settings.json', 'r') as f:
    config = json.load(f)

# Initialize Kalshi client
kalshi = KalshiClient(
    api_key=config['kalshi']['api_key'],
    private_key_path=config['kalshi']['private_key_path']
)

print("=" * 80)
print("Checking for NBA games on Kalshi...")
print("=" * 80)

# Get NBA markets
params = {
    'series_ticker': 'KXNBAGAME',
    'limit': 200,
    'status': 'open'
}

response = kalshi._make_request('GET', '/markets', params=params)
markets = response.get('markets', [])

print(f"\nFound {len(markets)} active NBA markets")
print("\nAll games available:")

# Group by game
games = {}
for market in markets:
    ticker = market['ticker']
    title = market['title']
    
    # Extract game from ticker
    parts = ticker.split('-')
    if len(parts) >= 2:
        game_id = parts[1]
        
        if game_id not in games:
            games[game_id] = []
        games[game_id].append(title)

for game_id, titles in sorted(games.items()):
    print(f"\n{game_id}:")
    for title in titles:
        print(f"  - {title}")

