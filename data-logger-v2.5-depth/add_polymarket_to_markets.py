#!/usr/bin/env python3
"""
Add Polymarket markets to existing Kalshi markets
Uses the Polymarket Gamma API to find matching NBA games
"""

import json
import re
import sys

try:
    import requests
except ImportError:
    print("ERROR: requests module not found")
    print("Run outside sandbox: pip3 install requests && python3 add_polymarket_to_markets.py")
    sys.exit(1)

GAMMA_API = "https://gamma-api.polymarket.com"
NBA_TAG_ID = 745

def normalize_team(name):
    """
    Normalize team names for matching
    Polymarket uses team names (Thunder, Warriors), not city names
    """
    # Map city names to team names (what Polymarket uses)
    city_to_team = {
        # City name -> Team name
        'atlanta': 'hawks',
        'boston': 'celtics',
        'brooklyn': 'nets',
        'charlotte': 'hornets',
        'chicago': 'bulls',
        'cleveland': 'cavaliers',
        'dallas': 'mavericks',
        'denver': 'nuggets',
        'detroit': 'pistons',
        'golden state': 'warriors',
        'houston': 'rockets',
        'indiana': 'pacers',
        'los angeles': 'lakers',  # or clippers - need context
        'la': 'lakers',
        'memphis': 'grizzlies',
        'miami': 'heat',
        'milwaukee': 'bucks',
        'minnesota': 'timberwolves',
        'new orleans': 'pelicans',
        'new york': 'knicks',
        'oklahoma city': 'thunder',
        'oklahoma': 'thunder',
        'orlando': 'magic',
        'philadelphia': '76ers',
        'phoenix': 'suns',
        'portland': 'trail blazers',
        'sacramento': 'kings',
        'san antonio': 'spurs',
        'toronto': 'raptors',
        'utah': 'jazz',
        'washington': 'wizards',
    }
    
    name_lower = name.lower().strip()
    
    # First check if it's already a team name
    if name_lower in city_to_team.values():
        return name_lower
    
    # Convert city to team name
    return city_to_team.get(name_lower, name_lower)

def get_polymarket_nba_games():
    """
    Fetch NBA games from Polymarket
    Returns dict: {(team1_abbr, team2_abbr, date): {'condition_id': str, 'slug': str}}
    """
    print("Fetching NBA games from Polymarket...")
    
    try:
        # Step 1: Get NBA events
        url = f"{GAMMA_API}/events"
        params = {
            'tag_id': str(NBA_TAG_ID),
            'closed': 'false',
            'limit': 200
        }
        
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        events = response.json()
        
        print(f"  Found {len(events)} NBA events")
        
        # Step 2: Filter for game events (those with dates in slug)
        date_pattern = re.compile(r'\d{4}-\d{2}-\d{2}')
        game_events = [e for e in events if date_pattern.search(e.get('slug', ''))]
        
        print(f"  Found {len(game_events)} NBA game events")
        
        # Step 3: Process each game
        games = {}
        
        for event in game_events:
            slug = event.get('slug', '')
            title = event.get('title', '')  # e.g., "Thunder vs. Trail Blazers"
            
            # Extract date from slug (format: nba-team1-team2-YYYY-MM-DD)
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})$', slug)
            if not date_match:
                continue
            
            game_date = date_match.group(1)
            
            # Parse teams from title (more reliable than slug)
            # Format: "Team1 vs. Team2" or "Team1 vs Team2"
            if ' vs. ' in title:
                teams = title.split(' vs. ')
            elif ' vs ' in title:
                teams = title.split(' vs ')
            else:
                continue
            
            if len(teams) != 2:
                continue
            
            team1 = teams[0].strip().lower()
            team2 = teams[1].strip().lower()
            
            # Fetch event details to get condition ID
            event_url = f"{GAMMA_API}/events/slug/{slug}"
            event_response = requests.get(event_url, timeout=15)
            
            if event_response.status_code == 200:
                event_data = event_response.json()
                markets = event_data.get('markets', [])
                
                if markets:
                    # First market is usually the moneyline
                    condition_id = markets[0].get('conditionId')
                    
                    if condition_id:
                        # Store both team orders with slug and condition_id
                        game_data = {'condition_id': condition_id, 'slug': slug}
                        games[(team1, team2, game_date)] = game_data
                        games[(team2, team1, game_date)] = game_data
                        
                        print(f"  ✓ {team1.upper()} vs {team2.upper()} ({game_date}): {condition_id}")
        
        print(f"\n  Total: {len(games) // 2} games with condition IDs")
        return games
        
    except Exception as e:
        print(f"  ✗ Error fetching Polymarket games: {e}")
        return {}

def match_kalshi_to_polymarket(kalshi_markets, polymarket_games):
    """Match Kalshi markets to Polymarket games"""
    print("\nMatching Kalshi markets to Polymarket...")
    print("-" * 70)
    
    matched = 0
    
    # Group Kalshi markets by game (description)
    games = {}
    for market in kalshi_markets:
        desc = market['description']
        if desc not in games:
            games[desc] = []
        games[desc].append(market)
    
    for game_desc, game_markets in games.items():
        # Extract teams from description
        teams_str = game_desc.replace(' Winner?', '')
        teams = teams_str.split(' vs ')
        
        if len(teams) != 2:
            print(f"  ✗ Could not parse teams from: {game_desc}")
            continue
        
        team1, team2 = teams
        team1_norm = normalize_team(team1)
        team2_norm = normalize_team(team2)
        
        # Get date from market (format: 2025-12-31T23:00:00Z)
        event_date = game_markets[0]['event_date']
        game_date = event_date[:10]  # Extract YYYY-MM-DD
        
        # Try to find match in Polymarket
        condition_id = None
        
        # Try both team orders
        key1 = (team1_norm, team2_norm, game_date)
        key2 = (team2_norm, team1_norm, game_date)
        
        game_data = None
        if key1 in polymarket_games:
            game_data = polymarket_games[key1]
        elif key2 in polymarket_games:
            game_data = polymarket_games[key2]
        
        if game_data:
            condition_id = game_data['condition_id']
            slug = game_data['slug']
            
            # Add to all markets for this game
            for market in game_markets:
                market['polymarket'] = {
                    "enabled": True,
                    "markets": {
                        "game": condition_id,
                        "slug": slug
                    },
                    "_note": "Use slug for API calls"
                }
            
            matched += 1
            print(f"  ✓ {team1} vs {team2} ({game_date})")
            print(f"      Condition ID: {condition_id}")
        else:
            print(f"  ✗ {team1} vs {team2} ({game_date}) - Not found on Polymarket")
    
    return matched

def main():
    print("=" * 70)
    print("ADDING POLYMARKET MARKETS TO KALSHI MARKETS")
    print("=" * 70)
    print()
    
    # Load Kalshi markets
    with open('config/markets.json', 'r') as f:
        data = json.load(f)
    
    print(f"Loaded {len(data['markets'])} Kalshi markets")
    print()
    
    # Fetch Polymarket games
    polymarket_games = get_polymarket_nba_games()
    
    if not polymarket_games:
        print("\n✗ No Polymarket games found!")
        print("  This might be temporary - Polymarket API could be down")
        print("  Or they might not have these specific games listed yet")
        return
    
    print()
    
    # Match and add
    matched = match_kalshi_to_polymarket(data['markets'], polymarket_games)
    
    print()
    print("=" * 70)
    print(f"✓ Matched {matched} out of {len(data['markets']) // 2} games")
    print("=" * 70)
    
    if matched > 0:
        # Save updated markets
        with open('config/markets.json', 'w') as f:
            json.dump(data, f, indent=2)
        
        print()
        print("✓ Saved to config/markets.json")
        print()
        print("=" * 70)
        print("✓ READY TO COLLECT DATA FROM BOTH PLATFORMS!")
        print("=" * 70)
        print()
        print("Run: python3 data_logger.py --hours 24")
        print()
    else:
        print()
        print("✗ No matches found")
        print("  Possible reasons:")
        print("  - Team name mismatches (check normalization)")
        print("  - Date mismatches")
        print("  - Polymarket doesn't have these games yet")
        print()

if __name__ == '__main__':
    main()

