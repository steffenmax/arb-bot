#!/usr/bin/env python3
"""
Fresh Market Discovery - Finds Active Markets for Today and Next 7 Days
Automatically updates config/markets.json with current games
"""

import json
import sys
from datetime import datetime, timedelta
from kalshi_client import KalshiClient
from polymarket_client import PolymarketClient

# NFL Team name mapping
NFL_TEAM_MAP = {
    'Arizona': 'Cardinals', 'Atlanta': 'Falcons', 'Baltimore': 'Ravens',
    'Buffalo': 'Bills', 'Carolina': 'Panthers', 'Chicago': 'Bears',
    'Cincinnati': 'Bengals', 'Cleveland': 'Browns', 'Dallas': 'Cowboys',
    'Denver': 'Broncos', 'Detroit': 'Lions', 'Green Bay': 'Packers',
    'Houston': 'Texans', 'Indianapolis': 'Colts', 'Jacksonville': 'Jaguars',
    'Kansas City': 'Chiefs', 'Las Vegas': 'Raiders', 
    'Los Angeles C': 'Chargers', 'Los Angeles R': 'Rams',
    'Miami': 'Dolphins', 'Minnesota': 'Vikings', 'New England': 'Patriots',
    'New Orleans': 'Saints', 'New York G': 'Giants', 'New York J': 'Jets',
    'Philadelphia': 'Eagles', 'Pittsburgh': 'Steelers',
    'San Francisco': '49ers', 'Seattle': 'Seahawks',
    'Tampa Bay': 'Buccaneers', 'Tennessee': 'Titans', 'Washington': 'Commanders'
}

NBA_TEAM_MAP = {
    'Atlanta': 'Hawks', 'Boston': 'Celtics', 'Brooklyn': 'Nets',
    'Charlotte': 'Hornets', 'Chicago': 'Bulls', 'Cleveland': 'Cavaliers',
    'Dallas': 'Mavericks', 'Denver': 'Nuggets', 'Detroit': 'Pistons',
    'Golden State': 'Warriors', 'Houston': 'Rockets', 'Indiana': 'Pacers',
    'LA': 'Clippers', 'Lakers': 'Lakers', 'Memphis': 'Grizzlies',
    'Miami': 'Heat', 'Milwaukee': 'Bucks', 'Minnesota': 'Timberwolves',
    'New Orleans': 'Pelicans', 'New York': 'Knicks', 'Oklahoma City': 'Thunder',
    'Orlando': 'Magic', 'Philadelphia': '76ers', 'Phoenix': 'Suns',
    'Portland': 'Trail Blazers', 'Sacramento': 'Kings', 'San Antonio': 'Spurs',
    'Toronto': 'Raptors', 'Utah': 'Jazz', 'Washington': 'Wizards'
}

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
            
            # Group by game (2 markets per game)
            games = {}
            for market in markets:
                ticker = market['ticker']
                # Extract base game identifier (remove team code at end)
                parts = ticker.split('-')
                if len(parts) >= 2:
                    game_base = '-'.join(parts[:2])  # e.g., KXNFLGAME-26JAN04ARILA
                    
                    if game_base not in games:
                        games[game_base] = []
                    games[game_base].append(market)
            
            # Filter for complete games (should have 2 markets)
            complete_games = []
            for game_base, markets_list in games.items():
                if len(markets_list) == 2:
                    complete_games.append({
                        'game_base': game_base,
                        'markets': markets_list,
                        'title': markets_list[0]['title'],
                        'close_time': markets_list[0].get('close_time', '')
                    })
            
            print(f"   ✓ Found {len(complete_games)} complete games (2 markets each)")
            return complete_games
        
        return []
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return []

def discover_polymarket_nfl(polymarket):
    """Discover Polymarket NFL games"""
    print(f"\n🔍 Searching Polymarket for NFL games...")
    
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
            
            # Filter for upcoming games (next 7 days)
            today = datetime.now().date()
            week_from_now = today + timedelta(days=7)
            
            upcoming = []
            for event in events:
                slug = event.get('slug', '')
                # Extract date from slug (format: nfl-xxx-yyy-2026-01-05)
                if '2026-' in slug:
                    try:
                        date_str = slug.split('2026-')[1].split('-')[:2]
                        date_str = f"2026-{date_str[0]}-{date_str[1]}"
                        event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        
                        if today <= event_date <= week_from_now:
                            upcoming.append(event)
                    except:
                        pass
            
            print(f"   ✓ Found {len(upcoming)} upcoming games")
            return upcoming
        
        return []
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return []

def discover_polymarket_nba(polymarket):
    """Discover Polymarket NBA games"""
    print(f"\n🔍 Searching Polymarket for NBA games...")
    
    try:
        response = polymarket.session.get(
            f"{polymarket.gamma_api_base}/events",
            params={
                'tag_id': '370',  # NBA tag
                'closed': 'false',
                'limit': 100
            },
            timeout=10
        )
        
        if response.status_code == 200:
            events = response.json()
            
            # Filter for upcoming games
            today = datetime.now().date()
            week_from_now = today + timedelta(days=7)
            
            upcoming = []
            for event in events:
                slug = event.get('slug', '')
                if '2026-' in slug:
                    try:
                        date_str = slug.split('2026-')[1].split('-')[:2]
                        date_str = f"2026-{date_str[0]}-{date_str[1]}"
                        event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        
                        if today <= event_date <= week_from_now:
                            upcoming.append(event)
                    except:
                        pass
            
            print(f"   ✓ Found {len(upcoming)} upcoming games")
            return upcoming
        
        return []
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return []

def match_games(kalshi_games, poly_events, sport='NFL'):
    """Match Kalshi and Polymarket games"""
    print(f"\n🔗 Matching {sport} games between platforms...")
    
    matched = []
    
    for k_game in kalshi_games:
        k_title = k_game['title'].lower()
        k_markets = k_game['markets']
        
        # Extract team info
        team_a_ticker = k_markets[0]['ticker'].split('-')[-1].lower()
        team_b_ticker = k_markets[1]['ticker'].split('-')[-1].lower()
        
        # Try to match with Polymarket
        for p_event in poly_events:
            p_slug = p_event.get('slug', '').lower()
            
            # Check if both team codes appear in slug
            if team_a_ticker in p_slug or team_b_ticker in p_slug:
                # Additional verification: check if both teams match
                team_a_name = k_markets[0].get('yes_sub_title', '').lower()
                team_b_name = k_markets[1].get('yes_sub_title', '').lower()
                
                p_title = p_event.get('title', '').lower()
                
                # Simple matching: check if team names appear in Polymarket title
                if any(word in p_title for word in team_a_name.split()) and \
                   any(word in p_title for word in team_b_name.split()):
                    
                    print(f"   ✓ {k_game['title']} <-> {p_event.get('title')}")
                    
                    matched.append({
                        'kalshi': k_game,
                        'polymarket': p_event
                    })
                    break
    
    print(f"   ✓ Matched {len(matched)} games")
    return matched

def generate_markets_config(matched_games, sport='NFL'):
    """Generate markets.json format"""
    markets = []
    
    for match in matched_games:
        k_game = match['kalshi']
        k_markets = k_game['markets']
        p_event = match['polymarket']
        
        # Sort markets by ticker to ensure consistent ordering
        k_markets_sorted = sorted(k_markets, key=lambda x: x['ticker'])
        
        team_a = k_markets_sorted[0].get('yes_sub_title', 'Team A')
        team_b = k_markets_sorted[1].get('yes_sub_title', 'Team B')
        
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
                    "main": k_markets_sorted[0]['ticker'],
                    "opponent": k_markets_sorted[1]['ticker']
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
    print("🔄 REFRESHING MARKETS - DISCOVERING ACTIVE GAMES")
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
    poly_nfl = discover_polymarket_nfl(polymarket)
    matched_nfl = match_games(kalshi_nfl, poly_nfl, 'NFL')
    nfl_markets = generate_markets_config(matched_nfl, 'NFL')
    all_markets.extend(nfl_markets)
    
    # Discover NBA games
    print("\n" + "=" * 80)
    print("🏀 NBA MARKETS")
    print("=" * 80)
    
    kalshi_nba = discover_kalshi_markets(kalshi, 'KXNBAGAME')
    poly_nba = discover_polymarket_nba(polymarket)
    matched_nba = match_games(kalshi_nba, poly_nba, 'NBA')
    nba_markets = generate_markets_config(matched_nba, 'NBA')
    all_markets.extend(nba_markets)
    
    # Generate final config
    print("\n" + "=" * 80)
    print("📝 GENERATING MARKETS.JSON")
    print("=" * 80)
    
    if not all_markets:
        print("\n⚠️  No active markets found!")
        print("   This could mean:")
        print("   - No games scheduled in the next 7 days")
        print("   - API connection issues")
        print("   - Markets not yet opened on platforms")
    else:
        # Backup old config
        try:
            with open('config/markets.json', 'r') as f:
                old_config = f.read()
            with open('config/markets.json.backup', 'w') as f:
                f.write(old_config)
            print("   ✓ Backed up old config to markets.json.backup")
        except:
            pass
        
        # Write new config
        markets_config = {
            "_comment": f"Active markets discovered on {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "_generated_at": datetime.now().isoformat(),
            "_note": "Auto-generated by refresh_markets.py",
            "markets": all_markets
        }
        
        with open('config/markets.json', 'w') as f:
            json.dump(markets_config, f, indent=2)
        
        print(f"\n✅ Created markets.json with {len(all_markets)} games")
        print(f"   NFL: {len(nfl_markets)}")
        print(f"   NBA: {len(nba_markets)}")
        print(f"\n📄 File: config/markets.json")
        
        # Show summary
        print("\n" + "=" * 80)
        print("📋 CONFIGURED MARKETS")
        print("=" * 80)
        
        for market in all_markets[:10]:  # Show first 10
            print(f"\n{market['sport']}: {market['description']}")
            print(f"  {market['teams']['team_a']} vs {market['teams']['team_b']}")
        
        if len(all_markets) > 10:
            print(f"\n... and {len(all_markets) - 10} more")
    
    # Cleanup
    kalshi.close()
    polymarket.close()
    
    print("\n" + "=" * 80)
    print("✅ MARKET REFRESH COMPLETE!")
    print("=" * 80)
    
    if all_markets:
        print(f"\n🎯 {len(all_markets)} active games configured")
        print("\n🚀 NEXT STEPS:")
        print("   1. Review config/markets.json")
        print("   2. Start data logger: python data_logger_depth.py")
        print("   3. Start dashboard: ./START_DASHBOARD.sh")
    else:
        print("\n⚠️  No active markets found - check API responses above")
        print("   You may need to wait for new games to be listed")

if __name__ == "__main__":
    main()

