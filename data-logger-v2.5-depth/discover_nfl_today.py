#!/usr/bin/env python3
"""
Discover the 2 NFL games happening today (Saturday, Jan 3/4, 2026)
Based on user-provided links:
- Kalshi: kxnflgame-26jan04cartb (Carolina vs Tampa Bay)
- Polymarket: nfl-car-tb-2026-01-04
"""

import json
import sys
sys.path.insert(0, '.')

from kalshi_client import KalshiClient
from polymarket_client import PolymarketClient
from datetime import datetime

# NFL Team name mapping (City -> Team Name for Polymarket)
NFL_TEAM_MAP = {
    'Carolina': 'Panthers',
    'Tampa Bay': 'Buccaneers',
    'Arizona': 'Cardinals',
    'Atlanta': 'Falcons',
    'Baltimore': 'Ravens',
    'Buffalo': 'Bills',
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
    'Los Angeles': 'Chargers',  # Can be Chargers or Rams
    'Miami': 'Dolphins',
    'Minnesota': 'Vikings',
    'New England': 'Patriots',
    'New Orleans': 'Saints',
    'New York': 'Giants',  # Can be Giants or Jets
    'Philadelphia': 'Eagles',
    'Pittsburgh': 'Steelers',
    'San Francisco': '49ers',
    'Seattle': 'Seahawks',
    'Tennessee': 'Titans',
    'Washington': 'Commanders'
}

print("=" * 80)
print("🏈 DISCOVERING TODAY'S NFL GAMES")
print("=" * 80)

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

# Get Kalshi games with 26JAN04 (today's date code)
print("\n🔍 Searching Kalshi for 26JAN04 games...")

try:
    result = kalshi._make_request('GET', '/markets', params={
        'series_ticker': 'KXNFLGAME',
        'status': 'open',
        'limit': 200
    })
    
    if result and 'markets' in result:
        # Filter for 26JAN04
        today_markets = [m for m in result['markets'] if '26JAN04' in m['ticker']]
        
        print(f"   ✓ Found {len(today_markets)} games with date code 26JAN04")
        
        # Group by game (each game has 2 markets, one per team)
        games = {}
        for market in today_markets:
            ticker = market['ticker']
            # Extract game code (e.g., CARTB from KXNFLGAME-26JAN04CARTB-CAR)
            parts = ticker.split('-')
            if len(parts) >= 2:
                game_code = parts[1][7:]  # Remove 26JAN04 prefix
                team_code = parts[2] if len(parts) >= 3 else ''
                
                if game_code not in games:
                    games[game_code] = []
                games[game_code].append(market)
        
        print(f"\n📋 Found {len(games)} unique games:")
        print("-" * 80)
        
        kalshi_games = []
        for game_code, markets in games.items():
            if len(markets) == 2:  # Should have 2 markets per game
                game_info = {
                    'game_code': game_code,
                    'markets': markets,
                    'title': markets[0]['title']
                }
                kalshi_games.append(game_info)
                
                print(f"\n{markets[0]['title']}")
                for m in markets:
                    yes_team = m.get('yes_sub_title', 'Unknown')
                    print(f"  {m['ticker']} (YES = {yes_team})")

except Exception as e:
    print(f"   ✗ Error: {e}")
    kalshi_games = []

# Get Polymarket games for today
print("\n" + "=" * 80)
print("🔍 Searching Polymarket for today's NFL games...")
print("-" * 80)

try:
    response = polymarket.session.get(
        f"{polymarket.gamma_api_base}/events",
        params={
            'tag_id': '450',  # NFL tag
            'closed': 'false',
            'limit': 100
        },
        timeout=10
    )
    
    if response.status_code == 200:
        events = response.json()
        
        # Filter for 2026-01-04 or 2026-01-03 in slug
        today_events = [e for e in events if '2026-01-04' in e.get('slug', '') or '2026-01-03' in e.get('slug', '')]
        
        print(f"\n✓ Found {len(today_events)} games for today:")
        
        poly_games = []
        for event in today_events:
            slug = event.get('slug', '')
            title = event.get('title', '')
            print(f"  {title}")
            print(f"    Slug: {slug}")
            poly_games.append(event)

except Exception as e:
    print(f"   ✗ Error: {e}")
    poly_games = []

# Match games
print("\n" + "=" * 80)
print("🔗 MATCHING GAMES BETWEEN PLATFORMS")
print("=" * 80)

matched_games = []

for k_game in kalshi_games:
    game_code = k_game['game_code']
    k_markets = k_game['markets']
    title = k_game['title']
    
    # Extract team codes from game_code
    # E.g., CARTB = CAR + TB
    if len(game_code) >= 6:
        team1_code = game_code[:3]  # CAR
        team2_code = game_code[3:6]  # TB (might be 2 chars like TB)
    else:
        team1_code = game_code[:2]
        team2_code = game_code[2:]
    
    # Try to match with Polymarket
    for p_event in poly_games:
        p_slug = p_event.get('slug', '').lower()
        p_title = p_event.get('title', '')
        
        # Check if team codes match slug
        if team1_code.lower() in p_slug and team2_code.lower() in p_slug:
            print(f"\n✓ MATCHED: {title}")
            print(f"  Kalshi: {k_markets[0]['ticker']}")
            print(f"  Polymarket: {p_slug}")
            
            matched_games.append({
                'kalshi': k_game,
                'polymarket': p_event
            })
            break

# Generate markets.json
print("\n" + "=" * 80)
print("📝 GENERATING MARKETS.JSON")
print("=" * 80)

if not matched_games:
    print("\n⚠️  No matched games found!")
else:
    markets_config = {
        "_comment": "NFL games for January 3/4, 2026",
        "_generated_at": datetime.now().isoformat(),
        "markets": []
    }
    
    for match in matched_games:
        k_game = match['kalshi']
        k_markets = k_game['markets']
        p_event = match['polymarket']
        
        # Get details
        title = k_game['title']
        game_code = k_game['game_code']
        
        # Find YES team for first market
        yes_team = k_markets[0].get('yes_sub_title', 'Team A')
        main_ticker = k_markets[0]['ticker']
        
        # Get Polymarket condition ID
        p_slug = p_event.get('slug')
        p_markets = p_event.get('markets', [])
        condition_id = p_markets[0].get('conditionId') if p_markets else None
        
        event_id = main_ticker.lower().replace('-', '_')
        
        market_entry = {
            "event_id": event_id,
            "description": title,
            "sport": "NFL",
            "event_date": k_markets[0].get('close_time', ''),
            "teams": {
                "yes_team": yes_team,
                "note": "Kalshi YES = this team wins"
            },
            "kalshi": {
                "enabled": True,
                "markets": {
                    "main": main_ticker
                },
                "yes_refers_to": yes_team
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
        
        print(f"\n✓ Configured: {title}")
        print(f"  Event ID: {event_id}")
        print(f"  Kalshi: {main_ticker}")
        print(f"  Polymarket: {p_slug}")
    
    # Save to file
    with open('config/markets.json', 'w') as f:
        json.dump(markets_config, f, indent=2)
    
    print(f"\n✅ Created markets.json with {len(matched_games)} game(s)")
    print(f"   File: config/markets.json")

kalshi.close()
polymarket.close()

print("\n" + "=" * 80)
print("✅ NFL GAME DISCOVERY COMPLETE!")
print("=" * 80)

if matched_games:
    print(f"\n🎯 {len(matched_games)} game(s) configured and ready to log")
    print("\n🚀 NEXT STEP: Start the data logger")
    print("   Command: caffeinate -i python3 data_logger.py --hours 6")
else:
    print("\n⚠️  No games configured - check API responses above")

