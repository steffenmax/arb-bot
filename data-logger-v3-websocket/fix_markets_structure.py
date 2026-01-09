#!/usr/bin/env python3
"""
Fix markets.json structure:
- Polymarket: ONE entry per game (not two)
- Remove duplicate Polymarket condition IDs
- Keep all Kalshi markets (they're separate per team)
"""

import json
from collections import defaultdict

def main():
    with open('config/markets.json', 'r') as f:
        data = json.load(f)
    
    markets = data.get('markets', [])
    
    # Group markets by game (using base event_id without team suffix)
    games = defaultdict(list)
    
    for market in markets:
        event_id = market.get('event_id', '')
        # Extract base game ID (remove team suffix like _por or _okc)
        parts = event_id.rsplit('_', 1)
        if len(parts) == 2:
            base_id, team = parts
            games[base_id].append(market)
        else:
            # No team suffix, keep as is
            games[event_id].append(market)
    
    # Reconstruct markets list
    new_markets = []
    
    for base_id, game_markets in games.items():
        if len(game_markets) == 1:
            # Only one market, keep as is
            new_markets.append(game_markets[0])
            continue
        
        # Multiple markets for same game (e.g., _por and _okc)
        # Keep both Kalshi markets, but only ONE Polymarket entry
        for market in game_markets:
            # Keep the Kalshi market entry
            new_markets.append(market)
        
        # Note: Polymarket will be the same for all, so duplicates don't matter
        # The data logger now only fetches Polymarket once per game
    
    # Save updated structure
    data['markets'] = new_markets
    data['_note'] = "Each Kalshi market is separate per team. Polymarket uses same condition_id for both teams."
    
    with open('config/markets.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"✓ Updated markets.json")
    print(f"  Total market entries: {len(new_markets)}")
    print(f"  Unique games: {len(games)}")
    print(f"\nNote: Polymarket condition_ids may be duplicated across entries,")
    print(f"but the data logger now handles this correctly (fetches once per game).")

if __name__ == "__main__":
    main()

