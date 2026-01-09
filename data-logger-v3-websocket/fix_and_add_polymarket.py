#!/usr/bin/env python3
"""
Fix markets.json and add Polymarket condition IDs
1. Fix event dates from event IDs
2. Search Polymarket API for matching games
3. Add condition IDs to markets.json
"""

import json
import re
from datetime import datetime, timedelta
import sys

# Check if requests is available
try:
    import requests
except ImportError:
    print("ERROR: requests module not installed")
    print("Please run: pip3 install requests")
    sys.exit(1)

POLYMARKET_API = "https://gamma-api.polymarket.com"

def parse_date_from_event_id(event_id):
    """Extract date from event ID like 'kxnbagame_25dec31porokc_por'"""
    match = re.search(r'_(\d{2})(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(\d{2})', event_id.lower())
    if match:
        year_suffix = match.group(1)
        month_name = match.group(2)
        day = match.group(3)
        
        year = f"20{year_suffix}"
        months = {
            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
            'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
            'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
        }
        month = months[month_name]
        
        return f"{year}-{month}-{day}T23:00:00Z"
    return None

def search_polymarket_nba(date_str, team1, team2):
    """
    Search Polymarket for NBA games on a specific date
    Returns condition ID if found
    """
    try:
        # Parse date
        date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        
        # Search for markets
        # Polymarket API endpoint for events
        url = f"{POLYMARKET_API}/events"
        params = {
            'active': 'true',
            'closed': 'false',
            'limit': 100
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        events = response.json()
        
        # Search for matching game
        team1_lower = team1.lower()
        team2_lower = team2.lower()
        
        for event in events:
            title = event.get('title', '').lower()
            description = event.get('description', '').lower()
            
            # Check if both teams are mentioned
            if team1_lower in title and team2_lower in title:
                # Check if it's basketball/NBA
                if 'nba' in title or 'basketball' in title:
                    # Get markets for this event
                    markets = event.get('markets', [])
                    if markets:
                        # Return the first market's condition ID
                        return markets[0].get('conditionId')
        
        return None
        
    except Exception as e:
        print(f"  ⚠️  Polymarket API error: {e}")
        return None

def normalize_team_name(name):
    """Normalize team names for better matching"""
    # Common team name mappings
    mappings = {
        'Oklahoma City': 'Thunder',
        'Portland': 'Trail Blazers',
        'New York': 'Knicks',
        'San Antonio': 'Spurs',
        'New Orleans': 'Pelicans',
        'Chicago': 'Bulls',
        'Memphis': 'Grizzlies',
        'Golden State': 'Warriors',
        'Charlotte': 'Hornets',
        'Atlanta': 'Hawks',
        'Orlando': 'Magic',
        'Detroit': 'Pistons',
        'Indiana': 'Pacers',
        'Milwaukee': 'Bucks',
        'Boston': 'Celtics',
        'Toronto': 'Raptors',
        'Cleveland': 'Cavaliers',
        'Miami': 'Heat',
        'Brooklyn': 'Nets',
        'Philadelphia': '76ers',
    }
    return mappings.get(name, name)

print("=" * 70)
print("FIXING MARKETS.JSON")
print("=" * 70)
print()

# Load current markets
with open('config/markets.json', 'r') as f:
    data = json.load(f)

print(f"Loaded {len(data['markets'])} markets")
print()

# Step 1: Fix dates
print("STEP 1: Fixing Event Dates")
print("-" * 70)

fixed_dates = 0
for market in data['markets']:
    event_id = market['event_id']
    new_date = parse_date_from_event_id(event_id)
    
    if new_date and market['event_date'] != new_date:
        old_date = market['event_date']
        market['event_date'] = new_date
        fixed_dates += 1
        print(f"✓ {event_id[:30]:30} {old_date[:10]} → {new_date[:10]}")

print()
print(f"✓ Fixed {fixed_dates} event dates")
print()

# Step 2: Add Polymarket markets
print("STEP 2: Adding Polymarket Markets")
print("-" * 70)
print("Searching Polymarket API for matching games...")
print()

# Group markets by game (2 markets per game - one for each team)
games = {}
for market in data['markets']:
    description = market['description']
    if description not in games:
        games[description] = []
    games[description].append(market)

print(f"Found {len(games)} unique games")
print()

added_polymarket = 0

for game_desc, game_markets in games.items():
    print(f"Searching: {game_desc}")
    
    # Extract team names from first market
    first_market = game_markets[0]
    teams = game_desc.replace(' Winner?', '').split(' vs ')
    
    if len(teams) == 2:
        team1, team2 = teams
        date_str = first_market['event_date']
        
        # Try to find on Polymarket
        condition_id = search_polymarket_nba(date_str, team1, team2)
        
        if condition_id:
            print(f"  ✓ Found condition ID: {condition_id}")
            
            # Add to both markets for this game
            for market in game_markets:
                market['polymarket'] = {
                    "enabled": True,
                    "markets": {
                        "game": condition_id
                    }
                }
            added_polymarket += 1
        else:
            print(f"  ✗ Not found on Polymarket")
    
    print()

print("=" * 70)
print(f"✓ Fixed {fixed_dates} event dates")
print(f"✓ Added {added_polymarket} Polymarket markets")
print()

# Save updated markets
with open('config/markets.json', 'w') as f:
    json.dump(data, f, indent=2)

print("✓ Saved to config/markets.json")
print()

if added_polymarket == 0:
    print("=" * 70)
    print("⚠️  NO POLYMARKET MARKETS FOUND")
    print("=" * 70)
    print()
    print("Polymarket API search didn't find matching games.")
    print("This could mean:")
    print("  1. Polymarket doesn't have these specific NBA games")
    print("  2. The games are named differently on Polymarket")
    print("  3. The API endpoint or format has changed")
    print()
    print("MANUAL OPTION:")
    print("  1. Visit https://polymarket.com")
    print("  2. Search for each NBA game")
    print("  3. Copy condition ID from URL")
    print("  4. Run: python3 add_polymarket_ids.py --interactive")
    print()
else:
    print("=" * 70)
    print("✓ READY TO COLLECT DATA FROM BOTH PLATFORMS!")
    print("=" * 70)
    print()
    print("Run: python3 data_logger.py --hours 24")
    print()

