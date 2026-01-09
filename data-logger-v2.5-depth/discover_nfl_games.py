#!/usr/bin/env python3
"""
Discover NFL Games for Today (January 3, 2026)

Finds games on both Kalshi and Polymarket and creates markets.json config
"""

import json
import sys
sys.path.insert(0, '.')

from kalshi_client import KalshiClient
from polymarket_client import PolymarketClient
from datetime import datetime, timedelta
import re

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
    'Los Angeles Chargers': 'Chargers',
    'Los Angeles Rams': 'Rams',
    'Miami': 'Dolphins',
    'Minnesota': 'Vikings',
    'New England': 'Patriots',
    'New Orleans': 'Saints',
    'New York Giants': 'Giants',
    'New York Jets': 'Jets',
    'Philadelphia': 'Eagles',
    'Pittsburgh': 'Steelers',
    'San Francisco': '49ers',
    'Seattle': 'Seahawks',
    'Tampa Bay': 'Buccaneers',
    'Tennessee': 'Titans',
    'Washington': 'Commanders'
}

print("=" * 80)
print("🏈 NFL GAME DISCOVERY - January 3, 2026")
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

# Get NFL games from Kalshi
print("\n🔍 Searching Kalshi for NFL games...")
print("   Series ticker: KXNFLGAME")

try:
    result = kalshi._make_request('GET', '/markets', params={
        'series_ticker': 'KXNFLGAME',
        'status': 'open',
        'limit': 200
    })
    
    if result and 'markets' in result:
        kalshi_markets = result['markets']
        print(f"   ✓ Found {len(kalshi_markets)} open NFL markets")
        
        # Filter for today's games (Jan 3, 2026)
        today = datetime(2026, 1, 3)
        today_markets = []
        
        for market in kalshi_markets:
            # Extract date from ticker (format: KXNFLGAME-26JAN03XXXYYY-XXX)
            ticker = market['ticker']
            
            # Look for 26jan03 or 26JAN03 in ticker
            if '26jan03' in ticker.lower():
                today_markets.append(market)
        
        print(f"   ✓ {len(today_markets)} games today (Jan 3)")
        
        # Display today's games
        if today_markets:
            print("\n📋 Today's NFL Games on Kalshi:")
            print("-" * 80)
            
            for market in today_markets:
                ticker = market['ticker']
                title = market.get('title', '')
                yes_team = market.get('yes_sub_title', 'Unknown')
                
                print(f"\n   {title}")
                print(f"   Ticker: {ticker}")
                print(f"   YES refers to: {yes_team}")
                print(f"   Close time: {market.get('close_time', 'Unknown')}")
        
        kalshi_games = today_markets
    else:
        print("   ✗ No NFL markets found")
        kalshi_games = []
        
except Exception as e:
    print(f"   ✗ Error: {e}")
    kalshi_games = []

# Get NFL games from Polymarket
print("\n🔍 Searching Polymarket for NFL games...")
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
        
        # Filter for games today (look for 2026-01-03 in slug)
        today_events = [e for e in events if '2026-01-03' in e.get('slug', '')]
        
        print(f"   ✓ Found {len(today_events)} NFL games today")
        
        if today_events:
            print("\n📋 Today's NFL Games on Polymarket:")
            print("-" * 80)
            
            for event in today_events:
                slug = event.get('slug', '')
                title = event.get('title', '')
                
                print(f"\n   {title}")
                print(f"   Slug: {slug}")
        
        poly_games = today_events
    else:
        print(f"   ✗ API returned status {response.status_code}")
        poly_games = []
        
except Exception as e:
    print(f"   ✗ Error: {e}")
    poly_games = []

# Match games between platforms
print("\n" + "=" * 80)
print("🔗 MATCHING GAMES BETWEEN PLATFORMS")
print("=" * 80)

matched_games = []

for k_market in kalshi_games:
    ticker = k_market['ticker']
    title = k_market['title']
    yes_team = k_market.get('yes_sub_title', '')
    
    # Extract teams from ticker (format: KXNFLGAME-26JAN03XXXYYY-XXX)
    # Example: KXNFLGAME-26JAN03PHIWAS-PHI
    parts = ticker.split('-')
    if len(parts) >= 3:
        team_part = parts[1]  # 26JAN03PHIWAS
        team_codes = team_part[7:]  # PHIWAS
        
        # Try to match with Polymarket
        for p_event in poly_games:
            p_slug = p_event.get('slug', '')
            p_title = p_event.get('title', '')
            
            # Check if any team names match
            match_found = False
            
            # Look for team name in slug
            for city, team_name in NFL_TEAM_MAP.items():
                if city.lower() in title.lower() or team_name.lower() in p_title.lower():
                    # Potential match - verify both teams
                    match_found = True
            
            if match_found or any(word in p_slug.lower() for word in team_codes.lower()[:3]):
                # Get full event details
                try:
                    event_detail = polymarket.get_market_by_slug(p_slug)
                    if event_detail:
                        matched_games.append({
                            'kalshi': k_market,
                            'polymarket': p_event,
                            'poly_detail': event_detail
                        })
                        print(f"\n✓ Matched: {title}")
                        print(f"  Kalshi: {ticker}")
                        print(f"  Polymarket: {p_slug}")
                        break
                except:
                    pass

# Generate markets.json
print("\n" + "=" * 80)
print("📝 GENERATING MARKETS.JSON")
print("=" * 80)

if not matched_games:
    print("\n⚠️  No matched games found!")
    print("    Check if games are available on both platforms")
else:
    markets_config = {
        "_comment": "Auto-discovered NFL games for January 3, 2026",
        "_generated_at": datetime.now().isoformat(),
        "markets": []
    }
    
    for match in matched_games:
        k = match['kalshi']
        p = match['polymarket']
        
        # Extract team names
        title = k['title']
        yes_team = k.get('yes_sub_title', 'Team A')
        ticker = k['ticker']
        
        # Find Polymarket teams
        poly_markets = p.get('markets', [])
        condition_id = None
        if poly_markets:
            condition_id = poly_markets[0].get('conditionId')
        
        event_id = ticker.lower().replace('-', '_')
        
        market_entry = {
            "event_id": event_id,
            "description": title,
            "sport": "NFL",
            "event_date": k.get('close_time', ''),
            "teams": {
                "yes_team": yes_team,
                "note": "Kalshi YES = this team wins"
            },
            "kalshi": {
                "enabled": True,
                "markets": {
                    "main": ticker
                },
                "yes_refers_to": yes_team
            },
            "polymarket": {
                "enabled": True,
                "markets": {
                    "game": condition_id,
                    "slug": p.get('slug')
                },
                "_note": "Use slug for API calls"
            }
        }
        
        markets_config["markets"].append(market_entry)
    
    # Save to file
    with open('config/markets.json', 'w') as f:
        json.dump(markets_config, f, indent=2)
    
    print(f"\n✅ Created markets.json with {len(matched_games)} game(s)")
    print(f"   File: config/markets.json")
    
    # Display summary
    print("\n📊 CONFIGURED GAMES:")
    print("-" * 80)
    for market in markets_config["markets"]:
        print(f"\n✓ {market['description']}")
        print(f"  Kalshi: {market['kalshi']['markets']['main']}")
        print(f"  Polymarket: {market['polymarket']['markets']['slug']}")

kalshi.close()
polymarket.close()

print("\n" + "=" * 80)
print("✅ NFL Game Discovery Complete!")
print("=" * 80)

if matched_games:
    print("\n🚀 NEXT STEP: Start the data logger")
    print("   Command: python3 data_logger.py --hours 6")
else:
    print("\n⚠️  No games configured - check API responses above")

