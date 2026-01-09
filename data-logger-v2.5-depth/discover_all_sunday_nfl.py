#!/usr/bin/env python3
"""
Discover ALL NFL Games for Sunday, January 4/5, 2026
Matches all games between Kalshi and Polymarket
"""

import json
import sys
sys.path.insert(0, '.')

from kalshi_client import KalshiClient
from polymarket_client import PolymarketClient
from datetime import datetime

# NFL Team name mapping (City -> Team Name for Polymarket)
NFL_TEAM_MAP = {
    'Arizona': 'Cardinals',
    'Atlanta': 'Falcons',
    'Baltimore': 'Ravens',
    'Buffalo': 'Bills',
    'Carolina': 'Panthers',
    'Chicago': 'Bears',
    'Cincinnati': 'Bengals',
    'Cleveland': 'Browns',
    'Dallas': 'Cowboys',
    'Denver': 'Broncos',
    'Detroit': 'Lions',
    'Green Bay': 'Packers',
    'Houston': 'Texans',
    'Indianapolis': 'Colts',
    'Jacksonville': 'Jaguars',
    'Kansas City': 'Chiefs',
    'Las Vegas': 'Raiders',
    'Los Angeles C': 'Chargers',
    'Los Angeles R': 'Rams',
    'Miami': 'Dolphins',
    'Minnesota': 'Vikings',
    'New England': 'Patriots',
    'New Orleans': 'Saints',
    'New York G': 'Giants',
    'New York J': 'Jets',
    'Philadelphia': 'Eagles',
    'Pittsburgh': 'Steelers',
    'San Francisco': '49ers',
    'Seattle': 'Seahawks',
    'Tampa Bay': 'Buccaneers',
    'Tennessee': 'Titans',
    'Washington': 'Commanders'
}

# Reverse mapping for matching
TEAM_TO_CITY = {v: k for k, v in NFL_TEAM_MAP.items()}

print("=" * 100)
print("🏈 DISCOVERING ALL NFL GAMES - Sunday, January 4/5, 2026")
print("=" * 100)

# Load credentials
with open('config/settings.json', 'r') as f:
    config = json.load(f)

# Initialize clients
print("\n📡 Connecting to APIs...")
kalshi = KalshiClient(
    api_key=config['kalshi']['api_key'],
    private_key_path=config['kalshi']['private_key_path']
)
polymarket = PolymarketClient()

# Get ALL NFL games from Kalshi with 26JAN04 or 26JAN05
print("\n🔍 Searching Kalshi for Sunday NFL games...")
print("   Series ticker: KXNFLGAME")

try:
    result = kalshi._make_request('GET', '/markets', params={
        'series_ticker': 'KXNFLGAME',
        'status': 'open',
        'limit': 200
    })
    
    if result and 'markets' in result:
        all_markets = result['markets']
        
        # Filter for Jan 4/5 games (could be dated either 26JAN04 or 26JAN05)
        sunday_markets = [m for m in all_markets if '26JAN04' in m['ticker'] or '26JAN05' in m['ticker']]
        
        print(f"   ✓ Found {len(sunday_markets)} markets for Sunday")
        
        # Group by game (each game has 2 markets, one per team)
        games = {}
        for market in sunday_markets:
            ticker = market['ticker']
            # Extract game code (e.g., SEASF from KXNFLGAME-26JAN04SEASF-SF)
            parts = ticker.split('-')
            if len(parts) >= 2:
                # Remove date prefix to get team codes
                date_and_teams = parts[1]
                if '26JAN04' in date_and_teams:
                    game_code = date_and_teams.replace('26JAN04', '')
                elif '26JAN05' in date_and_teams:
                    game_code = date_and_teams.replace('26JAN05', '')
                else:
                    continue
                
                if game_code not in games:
                    games[game_code] = []
                games[game_code].append(market)
        
        print(f"\n📋 Found {len(games)} unique games on Kalshi:")
        print("-" * 100)
        
        kalshi_games = []
        for game_code, markets in sorted(games.items()):
            if len(markets) == 2:  # Should have 2 markets per game
                game_info = {
                    'game_code': game_code,
                    'markets': markets,
                    'title': markets[0]['title'],
                    'teams': [markets[0].get('yes_sub_title', 'Team1'), 
                             markets[1].get('yes_sub_title', 'Team2')]
                }
                kalshi_games.append(game_info)
                
                print(f"{len(kalshi_games):2d}. {game_info['title']}")
                print(f"    Teams: {game_info['teams'][0]} vs {game_info['teams'][1]}")
                print(f"    Tickers: {markets[0]['ticker']}, {markets[1]['ticker']}")
        
        print(f"\n✓ Total: {len(kalshi_games)} games")
    else:
        print("   ✗ No NFL markets found")
        kalshi_games = []
        
except Exception as e:
    print(f"   ✗ Error: {e}")
    kalshi_games = []

# Get NFL games from Polymarket
print("\n" + "=" * 100)
print("🔍 Searching Polymarket for Sunday NFL games...")
print("   Tag ID: 450 (NFL)")

try:
    response = polymarket.session.get(
        f"{polymarket.gamma_api_base}/events",
        params={
            'tag_id': '450',  # NFL tag
            'closed': 'false',
            'limit': 200
        },
        timeout=10
    )
    
    if response.status_code == 200:
        events = response.json()
        
        # Filter for games on 2026-01-04 or 2026-01-05
        sunday_events = [e for e in events if '2026-01-04' in e.get('slug', '') or '2026-01-05' in e.get('slug', '')]
        
        print(f"   ✓ Found {len(sunday_events)} NFL games for Sunday")
        
        print("\n📋 Polymarket Games:")
        print("-" * 100)
        
        for i, event in enumerate(sunday_events, 1):
            slug = event.get('slug', '')
            title = event.get('title', '')
            print(f"{i:2d}. {title}")
            print(f"    Slug: {slug}")
        
        poly_games = sunday_events
    else:
        print(f"   ✗ API returned status {response.status_code}")
        poly_games = []
        
except Exception as e:
    print(f"   ✗ Error: {e}")
    poly_games = []

# Match games between platforms
print("\n" + "=" * 100)
print("🔗 MATCHING GAMES BETWEEN PLATFORMS")
print("=" * 100)

matched_games = []
unmatched_kalshi = []
unmatched_poly = []

for k_game in kalshi_games:
    game_code = k_game['game_code']
    k_markets = k_game['markets']
    title = k_game['title']
    k_teams = k_game['teams']
    
    # Convert Kalshi team names to Polymarket format
    k_team_names = set()
    for team in k_teams:
        team_name = NFL_TEAM_MAP.get(team, team)
        k_team_names.add(team_name.lower())
    
    # Try to match with Polymarket
    matched = False
    for p_event in poly_games:
        p_slug = p_event.get('slug', '').lower()
        p_title = p_event.get('title', '')
        
        # Check if both team names appear in the slug or title
        if len(k_team_names) >= 2:
            team_list = list(k_team_names)
            # Check various formats (abbreviations in slug, full names in title)
            if any(t[:3] in p_slug for t in team_list) or \
               all(t in p_title.lower() for t in team_list):
                
                print(f"\n✓ MATCHED: {title}")
                print(f"  Kalshi: {k_markets[0]['ticker']}")
                print(f"  Polymarket: {p_slug}")
                
                matched_games.append({
                    'kalshi': k_game,
                    'polymarket': p_event
                })
                matched = True
                break
    
    if not matched:
        unmatched_kalshi.append(k_game)

# Check for unmatched Polymarket games
matched_slugs = {m['polymarket']['slug'] for m in matched_games}
unmatched_poly = [p for p in poly_games if p['slug'] not in matched_slugs]

if unmatched_kalshi:
    print(f"\n⚠️  {len(unmatched_kalshi)} Kalshi game(s) not matched:")
    for game in unmatched_kalshi:
        print(f"  - {game['title']}")

if unmatched_poly:
    print(f"\n⚠️  {len(unmatched_poly)} Polymarket game(s) not matched:")
    for event in unmatched_poly:
        print(f"  - {event['title']} ({event['slug']})")

# Generate markets.json
print("\n" + "=" * 100)
print("📝 GENERATING MARKETS.JSON")
print("=" * 100)

if not matched_games:
    print("\n⚠️  No matched games found!")
else:
    markets_config = {
        "_comment": f"ALL NFL games for Sunday, January 4/5, 2026 - {len(matched_games)} games",
        "_generated_at": datetime.now().isoformat(),
        "markets": []
    }
    
    for match in matched_games:
        k_game = match['kalshi']
        k_markets = k_game['markets']
        p_event = match['polymarket']
        
        # Get details
        title = k_game['title']
        yes_team = k_markets[0].get('yes_sub_title', 'Team A')
        opponent_team = k_markets[1].get('yes_sub_title', 'Team B') if len(k_markets) > 1 else 'Team B'
        main_ticker = k_markets[0]['ticker']
        opponent_ticker = k_markets[1]['ticker'] if len(k_markets) > 1 else None
        
        # Get Polymarket details
        p_slug = p_event.get('slug')
        p_markets = p_event.get('markets', [])
        condition_id = p_markets[0].get('conditionId') if p_markets else None
        
        event_id = main_ticker.lower().replace('-', '_')
        
        # Build Kalshi markets dict
        kalshi_markets = {"main": main_ticker}
        if opponent_ticker:
            kalshi_markets["opponent"] = opponent_ticker
        
        market_entry = {
            "event_id": event_id,
            "description": title,
            "sport": "NFL",
            "event_date": k_markets[0].get('close_time', ''),
            "teams": {
                "team_a": yes_team,
                "team_b": opponent_team,
                "note": "Kalshi has two markets - one per team"
            },
            "kalshi": {
                "enabled": True,
                "markets": kalshi_markets,
                "market_a_refers_to": yes_team,
                "market_b_refers_to": opponent_team
            },
            "polymarket": {
                "enabled": True,
                "markets": {
                    "game": condition_id,
                    "slug": p_slug
                },
                "_note": "Use slug for API calls"
            }
        }
        
        markets_config["markets"].append(market_entry)
    
    # Display summary for user confirmation
    print("\n📊 MATCHED GAMES - PLEASE REVIEW:")
    print("=" * 100)
    for i, market in enumerate(markets_config["markets"], 1):
        print(f"\n{i:2d}. {market['description']}")
        print(f"    Team A: {market['teams']['team_a']}")
        print(f"    Team B: {market['teams']['team_b']}")
        print(f"    Kalshi Market A: {market['kalshi']['markets']['main']}")
        if 'opponent' in market['kalshi']['markets']:
            print(f"    Kalshi Market B: {market['kalshi']['markets']['opponent']}")
        else:
            print(f"    ⚠️  Kalshi Market B: MISSING!")
        print(f"    Polymarket: {market['polymarket']['markets']['slug']}")
    
    # Ask for user confirmation
    print("\n" + "=" * 100)
    print("❓ Review the matchups above. Do they look correct?")
    print("   - Check that BOTH Kalshi markets are present for each game")
    print("   - Check that team names match correctly")
    print("   - Check that Polymarket slugs are correct")
    print("=" * 100)
    
    user_input = input("\n✅ Type 'yes' to save this config, or 'no' to cancel: ").strip().lower()
    
    if user_input == 'yes':
        # Save to file
        output_file = 'config/markets.json'
        with open(output_file, 'w') as f:
            json.dump(markets_config, f, indent=2)
        
        print(f"\n✅ Saved {output_file} with {len(matched_games)} game(s)")
    else:
        print("\n❌ Config NOT saved. Please review the API responses and try again.")
        sys.exit(0)

kalshi.close()
polymarket.close()

print("\n" + "=" * 100)
print("✅ NFL GAME DISCOVERY COMPLETE!")
print("=" * 100)

if matched_games:
    print(f"\n🎯 {len(matched_games)} game(s) configured and ready for data collection")
    print("\n🚀 NEXT STEP: Start the data logger")
    print("   Command: caffeinate -i python3 data_logger.py --hours 24")
else:
    print("\n⚠️  No games configured - check API responses above")

