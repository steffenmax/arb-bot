#!/usr/bin/env python3
"""
Add specific NBA games to markets.json
"""

import json
from kalshi_client import KalshiClient
from polymarket_client import PolymarketClient

# Target games to find
TARGET_GAMES = [
    ("Denver", "Philadelphia"),  # Nuggets vs 76ers
    ("Golden State", "Los Angeles C"),  # Warriors vs Clippers
    ("Utah", "Portland")  # Jazz vs Trail Blazers
]

def discover_kalshi_nba(client):
    """Discover NBA markets on Kalshi"""
    print("\n🏀 Searching Kalshi for NBA games...")
    params = {
        'series_ticker': 'KXNBAGAME',
        'limit': 200,
        'status': 'open'
    }
    
    response = client._make_request('GET', '/markets', params=params)
    markets = response.get('markets', [])
    print(f"   Found {len(markets)} active NBA markets")
    
    # Group by game
    games = {}
    for market in markets:
        ticker = market['ticker']
        title = market['title']
        
        # Parse event_ticker from full ticker (e.g., KXNBAGAME-26JAN06DENGSW-DEN)
        parts = ticker.split('-')
        if len(parts) >= 2:
            event_ticker = parts[1]  # e.g., 26JAN06DENGSW
            
            if event_ticker not in games:
                games[event_ticker] = {
                    'event_ticker': event_ticker,
                    'markets': []
                }
            
            games[event_ticker]['markets'].append({
                'ticker': ticker,
                'title': title,
                'team': parts[2] if len(parts) > 2 else None
            })
    
    return games

def discover_polymarket_nba(client):
    """Discover NBA markets on Polymarket"""
    print("\n🏀 Searching Polymarket for NBA games...")
    
    # Use Gamma API to get NBA events (tag_id 370 is NBA)
    response = client.session.get(
        f"{client.gamma_api_base}/events",
        params={
            'tag_id': '370',  # NBA tag
            'closed': 'false',
            'limit': 100
        },
        timeout=10
    )
    
    if response.status_code == 200:
        events = response.json()
        
        # Filter for 2026 events (current season)
        nba_events = []
        for event in events:
            slug = event.get('slug', '')
            if '2026-' in slug:  # Only current season
                nba_events.append(event)
        
        print(f"   Found {len(nba_events)} active NBA games on Polymarket")
        return nba_events
    else:
        print(f"   ✗ Failed to fetch NBA events: {response.status_code}")
        return []

def find_target_games(kalshi_games, poly_events):
    """Match target games across both platforms"""
    print("\n🔍 Matching target games...")
    
    matched = []
    
    # Team name mappings for matching
    TEAM_KEYWORDS = {
        'Denver': ['denver', 'nuggets', 'den'],
        'Philadelphia': ['philadelphia', 'sixers', '76ers', 'phi'],
        'Golden State': ['golden state', 'warriors', 'gsw'],
        'Los Angeles C': ['clippers', 'lac', 'la clippers'],
        'Utah': ['utah', 'jazz'],
        'Portland': ['portland', 'trail blazers', 'blazers', 'por']
    }
    
    for target_a, target_b in TARGET_GAMES:
        print(f"\n   Looking for: {target_a} vs {target_b}")
        
        # Find in Kalshi
        kalshi_match = None
        for event_ticker, game_data in kalshi_games.items():
            markets = game_data['markets']
            teams_in_event = [m['team'] for m in markets if m['team']]
            
            # Check if both target teams are in this event
            teams_upper = [t.upper() if t else '' for t in teams_in_event]
            if any(target_a.upper() in t for t in teams_upper) and any(target_b.upper() in t for t in teams_upper):
                kalshi_match = game_data
                print(f"      ✓ Found on Kalshi: {event_ticker}")
                break
        
        # Find in Polymarket
        poly_match = None
        target_a_keywords = TEAM_KEYWORDS.get(target_a, [target_a.lower()])
        target_b_keywords = TEAM_KEYWORDS.get(target_b, [target_b.lower()])
        
        for event in poly_events:
            title = event.get('title', '').lower()
            slug = event.get('slug', '').lower()
            search_text = f"{title} {slug}"
            
            # Check if both teams are mentioned
            has_team_a = any(keyword in search_text for keyword in target_a_keywords)
            has_team_b = any(keyword in search_text for keyword in target_b_keywords)
            
            if has_team_a and has_team_b:
                poly_match = event
                print(f"      ✓ Found on Polymarket: {event.get('title')}")
                break
        
        if kalshi_match and poly_match:
            # Determine team names
            team_a = None
            team_b = None
            
            # Extract teams from Kalshi market titles
            for m in kalshi_match['markets']:
                if m['team']:
                    if not team_a:
                        team_a = m['team']
                    elif m['team'] != team_a:
                        team_b = m['team']
            
            # Find main and opponent tickers
            main_ticker = None
            opponent_ticker = None
            for m in kalshi_match['markets']:
                if m['team'] == team_a:
                    main_ticker = m['ticker']
                elif m['team'] == team_b:
                    opponent_ticker = m['ticker']
            
            matched.append({
                'kalshi': kalshi_match,
                'polymarket': poly_match,
                'team_a': team_a,
                'team_b': team_b,
                'kalshi_main': main_ticker,
                'kalshi_opponent': opponent_ticker
            })
            print(f"      ✅ MATCHED!")
        else:
            print(f"      ❌ Could not match on both platforms")
    
    return matched

def generate_market_entries(matched_games):
    """Generate market entries for markets.json"""
    entries = []
    
    for game in matched_games:
        kalshi_data = game['kalshi']
        poly_event = game['polymarket']
        
        # Extract slug from Polymarket event
        slug = poly_event.get('slug', '')
        
        # Create event_id from Kalshi event ticker
        event_id = f"kxnbagame_{kalshi_data['event_ticker'].lower()}"
        
        # Get description from first Kalshi market
        description = kalshi_data['markets'][0]['title'] if kalshi_data['markets'] else "NBA Game"
        
        # Get event date from Polymarket
        event_date = poly_event.get('endDate', '2026-01-06T00:00:00Z')
        
        entry = {
            "event_id": event_id,
            "description": description,
            "sport": "NBA",
            "event_date": event_date,
            "teams": {
                "team_a": game['team_a'],
                "team_b": game['team_b'],
                "note": "Kalshi has two markets - one per team"
            },
            "kalshi": {
                "enabled": True,
                "markets": {
                    "main": game['kalshi_main'],
                    "opponent": game['kalshi_opponent']
                },
                "market_a_refers_to": game['team_a'],
                "market_b_refers_to": game['team_b']
            },
            "polymarket": {
                "enabled": True,
                "markets": {
                    "slug": slug
                },
                "_note": "Use slug for API calls"
            }
        }
        
        entries.append(entry)
    
    return entries

def main():
    print("=" * 80)
    print("🏀 ADDING NBA GAMES TO MARKETS.JSON")
    print("=" * 80)
    
    # Load config
    with open('config/settings.json', 'r') as f:
        config = json.load(f)
    
    # Initialize clients
    print("\n📡 Connecting to APIs...")
    kalshi = KalshiClient(
        api_key=config['kalshi']['api_key'],
        private_key_path=config['kalshi']['private_key_path']
    )
    polymarket = PolymarketClient()
    
    # Discover markets
    kalshi_games = discover_kalshi_nba(kalshi)
    poly_events = discover_polymarket_nba(polymarket)
    
    # Find target games
    matched = find_target_games(kalshi_games, poly_events)
    
    if not matched:
        print("\n❌ No games matched. Check if games are active.")
        return
    
    # Generate entries
    new_entries = generate_market_entries(matched)
    
    # Load existing markets.json
    with open('config/markets.json', 'r') as f:
        markets_config = json.load(f)
    
    # Add new entries
    existing_ids = {m['event_id'] for m in markets_config['markets']}
    added_count = 0
    
    for entry in new_entries:
        if entry['event_id'] not in existing_ids:
            markets_config['markets'].append(entry)
            added_count += 1
            print(f"\n✅ Added: {entry['description']}")
        else:
            print(f"\n⚠️  Already exists: {entry['description']}")
    
    # Save
    if added_count > 0:
        with open('config/markets.json', 'w') as f:
            json.dump(markets_config, f, indent=2)
        
        print(f"\n" + "=" * 80)
        print(f"✅ SUCCESS! Added {added_count} NBA game(s) to markets.json")
        print("=" * 80)
    else:
        print(f"\n" + "=" * 80)
        print("ℹ️  No new games added (all already exist)")
        print("=" * 80)

if __name__ == "__main__":
    main()

