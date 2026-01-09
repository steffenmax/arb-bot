#!/usr/bin/env python3
"""
Improved Market Discovery - Uses proper API endpoints and filtering

This tool properly queries Kalshi and Polymarket APIs to find sports markets.

Usage:
    python3 discover_markets_improved.py --sport NBA
    python3 discover_markets_improved.py --sport NHL --save
    python3 discover_markets_improved.py --list-series
"""

import argparse
import json
import requests
from datetime import datetime
from pathlib import Path
from kalshi_client import KalshiClient
from polymarket_client import PolymarketClient


def load_config():
    """Load configuration"""
    with open('config/settings.json', 'r') as f:
        return json.load(f)


def get_kalshi_series(client):
    """Get all event series from Kalshi to see what's available"""
    try:
        # Try to get events/series
        response = client._make_request('GET', '/events', params={'limit': 200, 'status': 'open'})
        
        if response and 'events' in response:
            events = response['events']
            print(f"\n✓ Found {len(events)} active events/series on Kalshi")
            return events
        else:
            print("\n⚠️  Could not fetch events")
            return []
    except Exception as e:
        print(f"\n✗ Error fetching events: {e}")
        return []


def find_kalshi_sports_markets(client, sport='NBA'):
    """
    Find Kalshi sports markets using multiple strategies
    
    Strategy:
    1. Get all markets with status=open
    2. Filter by series ticker patterns (HIGHB for basketball, HIGHHOCKEY for hockey)
    3. Filter by title keywords (team names)
    """
    print(f"\n{'='*80}")
    print(f"Searching Kalshi for {sport} markets...")
    print(f"{'='*80}")
    
    # Define search patterns for each sport
    # These are the CORRECT series tickers from your old working bot!
    series_patterns = {
        'NBA': ['KXNBAGAME'],
        'NHL': ['KXNHLGAME'],
        'NFL': ['KXNFLGAME']
    }
    
    patterns = series_patterns.get(sport, [sport])
    all_markets = []
    
    # Try each series ticker
    for series_ticker in patterns:
        print(f"\nQuerying series: '{series_ticker}'...")
        
        # Get markets with this series ticker
        params = {
            'series_ticker': series_ticker,
            'limit': 200,
            'status': 'open'
        }
        
        markets = client._make_request('GET', '/markets', params=params)
        
        if markets and 'markets' in markets:
            found = markets['markets']
            print(f"  ✓ Found {len(found)} markets in {series_ticker}")
            all_markets.extend(found)
        else:
            print(f"  ⊘ No markets found in {series_ticker}")
    
    # Remove duplicates
    unique_markets = {}
    for market in all_markets:
        ticker = market.get('ticker')
        if ticker and ticker not in unique_markets:
            unique_markets[ticker] = market
    
    markets_list = list(unique_markets.values())
    
    # Filter by sport-specific keywords in title
    sport_keywords = {
        'NBA': ['lakers', 'celtics', 'warriors', 'nets', 'heat', 'bucks', 'mavs', 'nuggets', 
                'kings', 'suns', 'clippers', 'knicks', 'sixers', 'hawks', 'bulls', 'cavaliers',
                'pistons', 'pacers', 'hornets', 'raptors', 'wizards', 'magic', 'thunder', 
                'trail blazers', 'jazz', 'spurs', 'timberwolves', 'pelicans', 'grizzlies', 'rockets'],
        'NHL': ['maple leafs', 'canadiens', 'bruins', 'rangers', 'devils', 'islanders', 'flyers',
                'penguins', 'capitals', 'hurricanes', 'blue jackets', 'panthers', 'lightning',
                'red wings', 'predators', 'jets', 'blues', 'blackhawks', 'avalanche', 'wild',
                'stars', 'golden knights', 'flames', 'oilers', 'canucks', 'ducks', 'kings',
                'sharks', 'coyotes', 'kraken', 'senators', 'sabres'],
        'NFL': ['chiefs', 'bills', 'bengals', 'ravens', 'browns', 'steelers', 'texans', 'colts',
                'jaguars', 'titans', 'broncos', 'raiders', 'chargers', 'dolphins', 'patriots',
                'jets', 'cowboys', 'eagles', 'giants', 'commanders', 'packers', 'vikings',
                'lions', 'bears', 'buccaneers', 'saints', 'falcons', 'panthers', 'rams',
                '49ers', 'seahawks', 'cardinals']
    }
    
    keywords = sport_keywords.get(sport, [])
    
    if keywords:
        filtered = []
        for market in markets_list:
            title = market.get('title', '').lower()
            if any(keyword in title for keyword in keywords):
                filtered.append(market)
        
        if filtered:
            print(f"\n✓ Filtered to {len(filtered)} {sport}-specific markets")
            markets_list = filtered
        else:
            print(f"\n⚠️  No markets matched {sport} team names")
            print(f"   Showing all {len(markets_list)} markets found")
    
    return markets_list


def find_polymarket_sports_markets(sport='NBA'):
    """
    Find Polymarket sports markets
    
    Polymarket API endpoints:
    - https://gamma-api.polymarket.com/markets (all markets)
    - Can filter by tags, archived status, etc.
    """
    print(f"\n{'='*80}")
    print(f"Searching Polymarket for {sport} markets...")
    print(f"{'='*80}")
    
    try:
        # Try Polymarket's gamma API
        url = "https://gamma-api.polymarket.com/markets"
        params = {
            'limit': 200,
            'archived': 'false',
            'active': 'true'
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            all_markets = response.json()
            print(f"  Found {len(all_markets)} active markets on Polymarket")
            
            # Filter by sport keywords
            sport_keywords = {
                'NBA': ['nba', 'lakers', 'celtics', 'warriors', 'nets', 'heat', 'bucks', 'basketball'],
                'NHL': ['nhl', 'hockey', 'maple leafs', 'canadiens', 'bruins', 'rangers'],
                'NFL': ['nfl', 'football', 'chiefs', 'bills', 'bengals', 'ravens']
            }
            
            keywords = sport_keywords.get(sport, [sport.lower()])
            
            filtered_markets = []
            for market in all_markets:
                question = market.get('question', '').lower()
                description = market.get('description', '').lower()
                
                if any(keyword in question or keyword in description for keyword in keywords):
                    filtered_markets.append(market)
            
            if filtered_markets:
                print(f"✓ Filtered to {len(filtered_markets)} {sport}-specific markets")
                return filtered_markets
            else:
                print(f"⚠️  No markets matched {sport} keywords")
                return []
        else:
            print(f"✗ Polymarket API returned status {response.status_code}")
            return []
            
    except Exception as e:
        print(f"✗ Error querying Polymarket: {e}")
        return []


def display_markets(kalshi_markets, polymarket_markets):
    """Display found markets in organized format"""
    print(f"\n{'='*80}")
    print("DISCOVERED MARKETS")
    print(f"{'='*80}")
    
    if kalshi_markets:
        print(f"\n📊 KALSHI MARKETS ({len(kalshi_markets)} found)")
        print(f"{'─'*80}")
        
        for i, market in enumerate(kalshi_markets[:20], 1):  # Show first 20
            ticker = market.get('ticker', 'N/A')
            title = market.get('title', 'N/A')
            status = market.get('status', 'N/A')
            volume = market.get('volume', 0)
            
            print(f"\n[{i}] {ticker}")
            print(f"    {title}")
            print(f"    Status: {status} | Volume: {volume:,}")
        
        if len(kalshi_markets) > 20:
            print(f"\n    ... and {len(kalshi_markets) - 20} more markets")
    else:
        print("\n⚠️  No Kalshi markets found")
    
    if polymarket_markets:
        print(f"\n\n📊 POLYMARKET MARKETS ({len(polymarket_markets)} found)")
        print(f"{'─'*80}")
        
        for i, market in enumerate(polymarket_markets[:20], 1):
            question = market.get('question', 'N/A')
            condition_id = market.get('condition_id', market.get('id', 'N/A'))
            volume = market.get('volume', market.get('volume_num', 0))
            
            print(f"\n[{i}] {condition_id}")
            print(f"    {question}")
            print(f"    Volume: ${volume:,.0f}" if isinstance(volume, (int, float)) else f"    Volume: {volume}")
    else:
        print("\n⚠️  No Polymarket markets found")


def generate_markets_config(kalshi_markets, polymarket_markets, sport):
    """Generate markets.json configuration"""
    
    markets_config = []
    
    # Create entries from Kalshi markets
    # Kalshi markets use yes_sub_title to indicate which team YES refers to
    for k_market in kalshi_markets[:20]:  # Get up to 20 games
        ticker = k_market.get('ticker', '')
        title = k_market.get('title', '')
        subtitle = k_market.get('subtitle', '')
        yes_sub_title = k_market.get('yes_sub_title', '')  # This is the team name!
        
        # Extract team name from yes_sub_title (this is the YES team)
        team_yes = yes_sub_title if yes_sub_title else "Team"
        
        # For sports games, the title usually contains both teams or the matchup
        # Generate a clean event ID
        event_id = ticker.lower().replace('-', '_')
        
        # Create description - use subtitle if available
        description = subtitle if subtitle else title
        
        market_entry = {
            "event_id": event_id,
            "description": description,
            "sport": sport,
            "event_date": k_market.get('close_time', ''),
            "teams": {
                "yes_team": team_yes,  # Team that YES refers to
                "note": "Kalshi YES = this team wins"
            },
            "kalshi": {
                "enabled": True,
                "markets": {
                    "main": ticker
                },
                "yes_refers_to": team_yes  # Important: YES means this team wins!
            },
            "polymarket": {
                "enabled": False,
                "markets": {},
                "_note": "Add Polymarket condition ID if you want Polymarket data"
            }
        }
        
        markets_config.append(market_entry)
    
    return {
        "_comment": f"Auto-discovered {sport} markets",
        "_generated_at": datetime.now().isoformat(),
        "_note": "REVIEW AND EDIT: Team names may need correction. Add Polymarket IDs manually.",
        "markets": markets_config
    }


def main():
    parser = argparse.ArgumentParser(
        description="Improved market discovery using proper API endpoints"
    )
    
    parser.add_argument('--sport', type=str, choices=['NBA', 'NHL', 'NFL'], 
                       help='Sport to search for')
    parser.add_argument('--list-series', action='store_true',
                       help='List all available Kalshi series')
    parser.add_argument('--save', action='store_true',
                       help='Save discovered markets to JSON')
    parser.add_argument('--output', type=str, default='markets_discovered_improved.json',
                       help='Output filename')
    
    args = parser.parse_args()
    
    print("="*80)
    print("Improved Market Discovery")
    print("="*80)
    
    # Load config and initialize Kalshi client
    config = load_config()
    kalshi_config = config['kalshi']
    
    kalshi_client = KalshiClient(
        api_key=kalshi_config['api_key'],
        private_key_path=kalshi_config['private_key_path']
    )
    
    if args.list_series:
        events = get_kalshi_series(kalshi_client)
        if events:
            print(f"\nAvailable Kalshi Events/Series:")
            for event in events[:50]:
                ticker = event.get('event_ticker', event.get('series_ticker', 'N/A'))
                title = event.get('title', 'N/A')
                category = event.get('category', 'N/A')
                print(f"  {ticker}: {title} ({category})")
        return
    
    if not args.sport:
        print("\n❌ Please specify --sport NBA, NHL, or NFL")
        print("   Or use --list-series to see all available series")
        return
    
    # Find markets
    kalshi_markets = find_kalshi_sports_markets(kalshi_client, args.sport)
    polymarket_markets = find_polymarket_sports_markets(args.sport)
    
    # Display results
    display_markets(kalshi_markets, polymarket_markets)
    
    print(f"\n{'='*80}")
    print(f"SUMMARY: {len(kalshi_markets)} Kalshi + {len(polymarket_markets)} Polymarket markets")
    print(f"{'='*80}")
    
    if args.save:
        if kalshi_markets or polymarket_markets:
            config_data = generate_markets_config(kalshi_markets, polymarket_markets, args.sport)
            
            with open(args.output, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            print(f"\n✅ Saved to {args.output}")
            print(f"\n⚠️  IMPORTANT: Review and edit the file:")
            print(f"   - Verify team names are correct")
            print(f"   - Add Polymarket condition IDs if you want Polymarket data")
            print(f"   - Remove any unwanted markets")
            print(f"\nThen copy to config/markets.json and run:")
            print(f"   python3 data_logger.py --hours 24")
        else:
            print(f"\n⚠️  No markets found to save")


if __name__ == "__main__":
    main()

