#!/usr/bin/env python3
"""
Improved Market Discovery with Better Team Matching
Finds active markets and automatically updates config/markets.json
"""

import json
import re
from datetime import datetime, timedelta
from kalshi_client import KalshiClient
from polymarket_client import PolymarketClient

def normalize_team_name(name):
    """Normalize team name for matching"""
    # Remove common words
    name = name.lower()
    name = re.sub(r'\b(at|vs|winner)\b', '', name)
    name = name.strip()
    
    # Extract team codes (first 3 letters often)
    words = name.split()
    if words:
        return words[0][:3]  # Return first 3 letters of first word
    return name[:3]

def extract_team_codes_from_ticker(ticker):
    """Extract team codes from Kalshi ticker
    Example: KXNFLGAME-26JAN11PITBUF-PIT -> ('PIT', 'BUF')
    """
    parts = ticker.split('-')
    if len(parts) < 2:
        return None, None
    
    # Get the game code part (e.g., 26JAN11PITBUF)
    game_part = parts[1]
    
    # Remove date code (first 7 chars: 26JAN11)
    if len(game_part) > 7:
        teams_part = game_part[7:]  # e.g., PITBUF
        
        # Split into two 3-letter codes
        if len(teams_part) >= 6:
            team1 = teams_part[:3]
            team2 = teams_part[3:6]
            return team1, team2
        # Handle 2+3 or 3+2 letter combos
        elif len(teams_part) == 5:
            # Try different splits
            return teams_part[:2], teams_part[2:5]
    
    return None, None

def discover_kalshi_markets(kalshi, series_prefix='KXNFLGAME'):
    """Discover open Kalshi markets"""
    print(f"\n🔍 Searching Kalshi for {series_prefix} markets...")
    
    try:
        result = kalshi._make_request('GET', '/markets', params={
            'series_ticker': series_prefix,
            'status': 'open',
            'limit': 200
        })
        
        if result and 'markets' in result:
            markets = result['markets']
            print(f"   ✓ Found {len(markets)} open markets")
            
            # Group by game base
            games = {}
            for market in markets:
                ticker = market['ticker']
                parts = ticker.split('-')
                if len(parts) >= 2:
                    game_base = '-'.join(parts[:2])
                    
                    if game_base not in games:
                        games[game_base] = []
                    games[game_base].append(market)
            
            # Get complete games
            complete_games = []
            for game_base, markets_list in games.items():
                if len(markets_list) == 2:
                    # Extract team codes
                    team1_code, team2_code = extract_team_codes_from_ticker(markets_list[0]['ticker'])
                    
                    complete_games.append({
                        'game_base': game_base,
                        'markets': sorted(markets_list, key=lambda x: x['ticker']),
                        'title': markets_list[0]['title'],
                        'close_time': markets_list[0].get('close_time', ''),
                        'team1_code': team1_code,
                        'team2_code': team2_code
                    })
            
            print(f"   ✓ Found {len(complete_games)} complete games")
            
            # Show details
            for game in complete_games[:5]:
                print(f"      {game['title']}")
                print(f"      Codes: {game['team1_code']} vs {game['team2_code']}")
            if len(complete_games) > 5:
                print(f"      ... and {len(complete_games) - 5} more")
            
            return complete_games
        
        return []
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return []

def discover_polymarket_events(polymarket, tag_id, sport_name):
    """Discover Polymarket events"""
    print(f"\n🔍 Searching Polymarket for {sport_name} games...")
    
    try:
        response = polymarket.session.get(
            f"{polymarket.gamma_api_base}/events",
            params={
                'tag_id': tag_id,
                'closed': 'false',
                'limit': 100
            },
            timeout=10
        )
        
        if response.status_code == 200:
            events = response.json()
            
            # Filter for 2026 events
            filtered = []
            for event in events:
                slug = event.get('slug', '')
                if '2026-' in slug:
                    # Extract team codes from slug
                    # Format: nfl-pit-buf-2026-01-11
                    parts = slug.split('-')
                    if len(parts) >= 4:
                        team1_code = parts[1].upper()
                        team2_code = parts[2].upper()
                        event['team1_code'] = team1_code
                        event['team2_code'] = team2_code
                        filtered.append(event)
            
            print(f"   ✓ Found {len(filtered)} upcoming games")
            
            # Show details
            for event in filtered[:5]:
                print(f"      {event.get('title')}")
                print(f"      Codes: {event['team1_code']} vs {event['team2_code']}")
                print(f"      Slug: {event.get('slug')}")
            if len(filtered) > 5:
                print(f"      ... and {len(filtered) - 5} more")
            
            return filtered
        
        return []
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return []

def match_games(kalshi_games, poly_events, sport='NFL'):
    """Match games using team codes"""
    print(f"\n🔗 Matching {sport} games between platforms...")
    
    matched = []
    
    for k_game in kalshi_games:
        k_team1 = k_game.get('team1_code', '').upper()
        k_team2 = k_game.get('team2_code', '').upper()
        
        if not k_team1 or not k_team2:
            continue
        
        for p_event in poly_events:
            p_team1 = p_event.get('team1_code', '').upper()
            p_team2 = p_event.get('team2_code', '').upper()
            
            if not p_team1 or not p_team2:
                continue
            
            # Check if team codes match (in either order)
            if (k_team1 == p_team1 and k_team2 == p_team2) or \
               (k_team1 == p_team2 and k_team2 == p_team1):
                
                print(f"   ✓ {k_game['title']}")
                print(f"      Kalshi: {k_team1} vs {k_team2}")
                print(f"      Polymarket: {p_event.get('title')} ({p_event.get('slug')})")
                
                matched.append({
                    'kalshi': k_game,
                    'polymarket': p_event
                })
                break
    
    print(f"\n   ✓ Matched {len(matched)} games total")
    return matched

def generate_markets_config(matched_games, sport='NFL'):
    """Generate markets.json entries"""
    markets = []
    
    for match in matched_games:
        k_game = match['kalshi']
        k_markets = k_game['markets']
        p_event = match['polymarket']
        
        # Get team names
        team_a = k_markets[0].get('yes_sub_title', 'Team A')
        team_b = k_markets[1].get('yes_sub_title', 'Team B')
        
        event_id = k_game['game_base'].lower().replace('-', '_')
        
        market_entry = {
            "event_id": event_id,
            "description": k_game['title'],
            "sport": sport,
            "event_date": k_game['close_time'],
            "teams": {
                "team_a": team_a,
                "team_b": team_b,
                "note": "Kalshi has two markets - one per team"
            },
            "kalshi": {
                "enabled": True,
                "markets": {
                    "main": k_markets[0]['ticker'],
                    "opponent": k_markets[1]['ticker']
                },
                "market_a_refers_to": team_a,
                "market_b_refers_to": team_b
            },
            "polymarket": {
                "enabled": True,
                "markets": {
                    "slug": p_event.get('slug')
                },
                "_note": "Use slug for API calls"
            }
        }
        
        markets.append(market_entry)
    
    return markets

def main():
    print("=" * 80)
    print("🔄 MARKET REFRESH - IMPROVED MATCHING")
    print("=" * 80)
    
    # Load credentials
    print("\n📡 Loading configuration...")
    with open('config/settings.json', 'r') as f:
        config = json.load(f)
    
    # Initialize clients
    print("📡 Connecting to APIs...")
    kalshi = KalshiClient(
        api_key=config['kalshi']['api_key'],
        private_key_path=config['kalshi']['private_key_path']
    )
    polymarket = PolymarketClient()
    
    all_markets = []
    
    # Discover NFL games
    print("\n" + "=" * 80)
    print("🏈 NFL MARKETS")
    print("=" * 80)
    
    kalshi_nfl = discover_kalshi_markets(kalshi, 'KXNFLGAME')
    poly_nfl = discover_polymarket_events(polymarket, '450', 'NFL')
    matched_nfl = match_games(kalshi_nfl, poly_nfl, 'NFL')
    nfl_markets = generate_markets_config(matched_nfl, 'NFL')
    all_markets.extend(nfl_markets)
    
    # Discover NBA games
    print("\n" + "=" * 80)
    print("🏀 NBA MARKETS")
    print("=" * 80)
    
    kalshi_nba = discover_kalshi_markets(kalshi, 'KXNBAGAME')
    poly_nba = discover_polymarket_events(polymarket, '370', 'NBA')
    matched_nba = match_games(kalshi_nba, poly_nba, 'NBA')
    nba_markets = generate_markets_config(matched_nba, 'NBA')
    all_markets.extend(nba_markets)
    
    # Generate final config
    print("\n" + "=" * 80)
    print("📝 UPDATING MARKETS.JSON")
    print("=" * 80)
    
    if not all_markets:
        print("\n⚠️  No matched markets found!")
        print("   Keeping existing config unchanged")
    else:
        # Backup old config
        try:
            with open('config/markets.json', 'r') as f:
                old_config = f.read()
            backup_name = f"config/markets.json.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            with open(backup_name, 'w') as f:
                f.write(old_config)
            print(f"   ✓ Backed up old config to {backup_name}")
        except Exception as e:
            print(f"   ⚠️  Could not backup: {e}")
        
        # Write new config
        markets_config = {
            "_comment": f"Active markets discovered on {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "_generated_at": datetime.now().isoformat(),
            "_note": "Auto-generated by refresh_markets_improved.py",
            "markets": all_markets
        }
        
        with open('config/markets.json', 'w') as f:
            json.dump(markets_config, f, indent=2)
        
        print(f"\n✅ Updated markets.json with {len(all_markets)} games")
        print(f"   NFL: {len(nfl_markets)}")
        print(f"   NBA: {len(nba_markets)}")
        
        # Show summary
        print("\n" + "=" * 80)
        print("📋 NEWLY CONFIGURED MARKETS")
        print("=" * 80)
        
        for market in all_markets:
            print(f"\n{market['sport']}: {market['description']}")
            print(f"  Teams: {market['teams']['team_a']} vs {market['teams']['team_b']}")
            print(f"  Event Date: {market['event_date']}")
    
    # Cleanup
    kalshi.close()
    polymarket.close()
    
    print("\n" + "=" * 80)
    print("✅ MARKET REFRESH COMPLETE!")
    print("=" * 80)
    
    if all_markets:
        print(f"\n🎯 {len(all_markets)} active games now configured")
        print("\n🚀 NEXT STEPS:")
        print("   1. Review: config/markets.json")
        print("   2. Start data logger: python data_logger_depth.py")
        print("   3. Start dashboard: ./START_DASHBOARD.sh")
    else:
        print("\n⚠️  No matches found - this could mean:")
        print("   - Team code extraction needs adjustment")
        print("   - Platforms use different game identifiers")
        print("   - Run: python refresh_markets_improved.py to retry")

if __name__ == "__main__":
    main()

