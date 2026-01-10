#!/usr/bin/env python3
"""
Market Discovery CLI Tool - Interactive Version

Add or remove markets interactively with proper moneyline detection.

Usage:
    python market_discovery.py              # Interactive mode
    python market_discovery.py --list       # List current markets
    python market_discovery.py --clear      # Clear all markets
"""

import argparse
import json
import requests
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from pathlib import Path


# =============================================================================
# TEAM ALIAS MAPPINGS
# =============================================================================

NBA_TEAM_ALIASES = {
    "celtics": ["boston", "bos", "boston celtics", "celtics"],
    "nets": ["brooklyn", "bkn", "brk", "brooklyn nets", "nets"],
    "knicks": ["new york", "nyk", "new york knicks", "knicks"],
    "76ers": ["philadelphia", "phi", "sixers", "philadelphia 76ers", "76ers", "philly"],
    "raptors": ["toronto", "tor", "toronto raptors", "raptors"],
    "bulls": ["chicago", "chi", "chicago bulls", "bulls"],
    "cavaliers": ["cleveland", "cle", "cavs", "cleveland cavaliers", "cavaliers"],
    "pistons": ["detroit", "det", "detroit pistons", "pistons"],
    "pacers": ["indiana", "ind", "indiana pacers", "pacers"],
    "bucks": ["milwaukee", "mil", "milwaukee bucks", "bucks"],
    "hawks": ["atlanta", "atl", "atlanta hawks", "hawks"],
    "hornets": ["charlotte", "cha", "charlotte hornets", "hornets"],
    "heat": ["miami", "mia", "miami heat", "heat"],
    "magic": ["orlando", "orl", "orlando magic", "magic"],
    "wizards": ["washington", "was", "washington wizards", "wizards"],
    "nuggets": ["denver", "den", "denver nuggets", "nuggets"],
    "timberwolves": ["minnesota", "min", "minnesota timberwolves", "timberwolves", "wolves"],
    "thunder": ["oklahoma city", "okc", "oklahoma city thunder", "thunder"],
    "trail blazers": ["portland", "por", "blazers", "portland trail blazers", "trail blazers", "trailblazers"],
    "jazz": ["utah", "uta", "utah jazz", "jazz"],
    "warriors": ["golden state", "gsw", "golden state warriors", "warriors", "gs"],
    "clippers": ["los angeles c", "lac", "la clippers", "los angeles clippers", "clippers"],
    "lakers": ["los angeles l", "lal", "la lakers", "los angeles lakers", "lakers", "los angeles"],
    "suns": ["phoenix", "phx", "phoenix suns", "suns"],
    "kings": ["sacramento", "sac", "sacramento kings", "kings"],
    "mavericks": ["dallas", "dal", "dallas mavericks", "mavericks", "mavs"],
    "rockets": ["houston", "hou", "houston rockets", "rockets"],
    "grizzlies": ["memphis", "mem", "memphis grizzlies", "grizzlies"],
    "pelicans": ["new orleans", "nop", "new orleans pelicans", "pelicans"],
    "spurs": ["san antonio", "sas", "san antonio spurs", "spurs"],
}

NFL_TEAM_ALIASES = {
    "bills": ["buffalo", "buf", "buffalo bills", "bills"],
    "dolphins": ["miami dolphins", "mia", "dolphins"],  # Note: "miami" alone could be NBA Heat
    "patriots": ["new england", "ne", "new england patriots", "patriots", "pats"],
    "jets": ["new york jets", "nyj", "jets", "new york j"],
    "ravens": ["baltimore", "bal", "baltimore ravens", "ravens"],
    "bengals": ["cincinnati", "cin", "cincinnati bengals", "bengals"],
    "browns": ["cleveland browns", "cle", "browns"],  # Note: "cleveland" alone could be NBA Cavs
    "steelers": ["pittsburgh", "pit", "pittsburgh steelers", "steelers"],
    "texans": ["houston texans", "hou", "texans"],
    "colts": ["indianapolis", "ind", "indianapolis colts", "colts"],
    "jaguars": ["jacksonville", "jax", "jacksonville jaguars", "jaguars"],
    "titans": ["tennessee titans", "ten", "titans"],
    "broncos": ["denver broncos", "den", "broncos"],
    "chiefs": ["kansas city", "kc", "kansas city chiefs", "chiefs"],
    "raiders": ["las vegas", "lv", "las vegas raiders", "raiders"],
    "chargers": ["los angeles chargers", "lac", "chargers", "la chargers"],
    "cowboys": ["dallas cowboys", "dal", "cowboys"],
    "giants": ["new york giants", "nyg", "giants", "new york g"],
    "eagles": ["philadelphia eagles", "phi", "eagles"],
    "commanders": ["washington commanders", "was", "commanders"],
    "bears": ["chicago bears", "chi", "bears"],
    "lions": ["detroit lions", "det", "lions"],
    "packers": ["green bay", "gb", "green bay packers", "packers"],
    "vikings": ["minnesota vikings", "min", "vikings"],
    "falcons": ["atlanta falcons", "atl", "falcons"],
    "panthers": ["carolina", "car", "carolina panthers", "panthers"],
    "saints": ["new orleans saints", "no", "saints"],
    "buccaneers": ["tampa bay", "tb", "tampa bay buccaneers", "buccaneers", "bucs"],
    "cardinals": ["arizona", "ari", "arizona cardinals", "cardinals"],
    "rams": ["los angeles rams", "lar", "rams", "la rams", "la"],
    "49ers": ["san francisco", "sf", "san francisco 49ers", "49ers", "niners"],
    "seahawks": ["seattle", "sea", "seattle seahawks", "seahawks"],
}

CFP_TEAM_ALIASES = {
    "oregon": ["oregon", "ore", "oregon ducks", "ducks"],
    "ohio state": ["ohio state", "osu", "ohio state buckeyes", "buckeyes"],
    "texas": ["texas", "tex", "texas longhorns", "longhorns"],
    "penn state": ["penn state", "psu", "penn state nittany lions", "nittany lions"],
    "notre dame": ["notre dame", "nd", "notre dame fighting irish", "fighting irish"],
    "georgia": ["georgia", "uga", "georgia bulldogs", "bulldogs"],
    "tennessee": ["tennessee vols", "tenn", "tennessee volunteers", "volunteers", "vols"],
    "indiana": ["indiana hoosiers", "ind", "hoosiers"],
    "boise state": ["boise state", "bsu", "boise state broncos"],
    "smu": ["smu", "southern methodist", "smu mustangs", "mustangs"],
    "clemson": ["clemson", "clem", "clemson tigers"],
    "arizona state": ["arizona state", "asu", "arizona state sun devils", "sun devils"],
    "miami": ["miami hurricanes", "mia", "hurricanes"],
    "ole miss": ["ole miss", "miss", "ole miss rebels", "rebels", "mississippi"],
}

# Build reverse lookups
def build_alias_lookup(aliases_dict):
    lookup = {}
    for canonical, aliases in aliases_dict.items():
        for alias in aliases:
            lookup[alias.lower()] = canonical
    return lookup

NBA_ALIAS_TO_CANONICAL = build_alias_lookup(NBA_TEAM_ALIASES)
NFL_ALIAS_TO_CANONICAL = build_alias_lookup(NFL_TEAM_ALIASES)
CFP_ALIAS_TO_CANONICAL = build_alias_lookup(CFP_TEAM_ALIASES)

# Canonical to code mappings
NBA_CANONICAL_TO_CODE = {
    "celtics": "BOS", "nets": "BKN", "knicks": "NYK", "76ers": "PHI", "raptors": "TOR",
    "bulls": "CHI", "cavaliers": "CLE", "pistons": "DET", "pacers": "IND", "bucks": "MIL",
    "hawks": "ATL", "hornets": "CHA", "heat": "MIA", "magic": "ORL", "wizards": "WAS",
    "nuggets": "DEN", "timberwolves": "MIN", "thunder": "OKC", "trail blazers": "POR", "jazz": "UTA",
    "warriors": "GSW", "clippers": "LAC", "lakers": "LAL", "suns": "PHX", "kings": "SAC",
    "mavericks": "DAL", "rockets": "HOU", "grizzlies": "MEM", "pelicans": "NOP", "spurs": "SAS",
}

NFL_CANONICAL_TO_CODE = {
    "bills": "BUF", "dolphins": "MIA", "patriots": "NE", "jets": "NYJ",
    "ravens": "BAL", "bengals": "CIN", "browns": "CLE", "steelers": "PIT",
    "texans": "HOU", "colts": "IND", "jaguars": "JAX", "titans": "TEN",
    "broncos": "DEN", "chiefs": "KC", "raiders": "LV", "chargers": "LAC",
    "cowboys": "DAL", "giants": "NYG", "eagles": "PHI", "commanders": "WAS",
    "bears": "CHI", "lions": "DET", "packers": "GB", "vikings": "MIN",
    "falcons": "ATL", "panthers": "CAR", "saints": "NO", "buccaneers": "TB",
    "cardinals": "ARI", "rams": "LAR", "49ers": "SF", "seahawks": "SEA",
}

CFP_CANONICAL_TO_CODE = {
    "oregon": "ORE", "ohio state": "OSU", "texas": "TEX", "penn state": "PSU",
    "notre dame": "ND", "georgia": "UGA", "tennessee": "TENN", "indiana": "IND",
    "boise state": "BSU", "smu": "SMU", "clemson": "CLEM", "arizona state": "ASU",
    "miami": "MIA", "ole miss": "MISS",
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_markets_path() -> Path:
    return Path(__file__).parent / "config" / "markets.json"


def load_markets() -> Dict:
    """Load current markets.json"""
    path = get_markets_path()
    if path.exists():
        with open(path, 'r') as f:
            return json.load(f)
    return {"markets": []}


def save_markets(config: Dict):
    """Save markets.json"""
    path = get_markets_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(config, f, indent=2)


def parse_date_input(date_str: str) -> str:
    """Parse date input to YYYY-MM-DD"""
    date_str = date_str.strip().lower()
    
    if date_str == "today":
        return datetime.now().strftime("%Y-%m-%d")
    elif date_str == "tomorrow":
        return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        # Try various formats
        for fmt in ["%Y-%m-%d", "%m/%d/%y", "%m/%d/%Y", "%m-%d-%y", "%m-%d-%Y"]:
            try:
                dt = datetime.strptime(date_str, fmt)
                # Handle 2-digit years
                if dt.year < 100:
                    dt = dt.replace(year=dt.year + 2000)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        
        raise ValueError(f"Could not parse date: {date_str}")


def normalize_team(name: str, sport: str) -> Optional[str]:
    """Normalize team name to canonical form"""
    if not name:
        return None
    
    name_lower = name.lower().strip()
    
    if sport.upper() == "NFL":
        if name_lower in NFL_ALIAS_TO_CANONICAL:
            return NFL_ALIAS_TO_CANONICAL[name_lower]
        for alias, canonical in NFL_ALIAS_TO_CANONICAL.items():
            if alias in name_lower or name_lower in alias:
                return canonical
    elif sport.upper() == "NBA":
        if name_lower in NBA_ALIAS_TO_CANONICAL:
            return NBA_ALIAS_TO_CANONICAL[name_lower]
        for alias, canonical in NBA_ALIAS_TO_CANONICAL.items():
            if alias in name_lower or name_lower in alias:
                return canonical
    elif sport.upper() == "CFP":
        if name_lower in CFP_ALIAS_TO_CANONICAL:
            return CFP_ALIAS_TO_CANONICAL[name_lower]
        for alias, canonical in CFP_ALIAS_TO_CANONICAL.items():
            if alias in name_lower or name_lower in alias:
                return canonical
    
    return None


def get_team_code(canonical: str, sport: str) -> str:
    """Get team code from canonical name"""
    if sport.upper() == "NFL":
        return NFL_CANONICAL_TO_CODE.get(canonical, canonical.upper()[:3])
    elif sport.upper() == "NBA":
        return NBA_CANONICAL_TO_CODE.get(canonical, canonical.upper()[:3])
    elif sport.upper() == "CFP":
        return CFP_CANONICAL_TO_CODE.get(canonical, canonical.upper()[:3])
    return canonical.upper()[:3]


def parse_kalshi_date(event_ticker: str) -> str:
    """Extract date from Kalshi ticker: KXNFLGAME-26JAN10LACAR -> 2026-01-10"""
    match = re.search(r'-(\d{2})([A-Z]{3})(\d{2})', event_ticker)
    if not match:
        return None
    
    year_suffix, month_str, day = match.groups()
    month_map = {
        'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04',
        'MAY': '05', 'JUN': '06', 'JUL': '07', 'AUG': '08',
        'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'
    }
    month = month_map.get(month_str.upper())
    if not month:
        return None
    
    return f"20{year_suffix}-{month}-{day}"


# =============================================================================
# API QUERY FUNCTIONS
# =============================================================================

def query_kalshi_game(sport: str, target_date: str, team_a: str, team_b: str) -> Optional[Dict]:
    """
    Query Kalshi for a specific game.
    Returns market info or None if not found.
    """
    series_tickers = {
        "NFL": "KXNFLGAME",
        "NBA": "KXNBAGAME", 
        "CFP": "KXNCAAFGAME"
    }
    
    series_ticker = series_tickers.get(sport.upper())
    if not series_ticker:
        print(f"  ✗ Unknown sport: {sport}")
        return None
    
    url = "https://api.elections.kalshi.com/trade-api/v2/events"
    params = {
        'series_ticker': series_ticker,
        'status': 'open',
        'limit': 100
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        events = data.get('events', [])
        print(f"  Kalshi: Found {len(events)} {sport} events")
        
        for event in events:
            event_ticker = event.get('event_ticker', '')
            title = event.get('title', '')
            
            # Check date
            event_date = parse_kalshi_date(event_ticker)
            if event_date != target_date:
                continue
            
            # Check if both teams are in this event
            title_lower = title.lower()
            team_a_canonical = normalize_team(team_a, sport)
            team_b_canonical = normalize_team(team_b, sport)
            
            if not team_a_canonical or not team_b_canonical:
                continue
            
            # Check if event title contains both teams
            event_team_a = normalize_team(title.split(' at ')[0] if ' at ' in title else title.split(' vs')[0], sport)
            event_team_b = normalize_team(title.split(' at ')[-1] if ' at ' in title else title.split(' vs')[-1], sport)
            
            if not event_team_a or not event_team_b:
                continue
            
            # Match teams (order doesn't matter)
            teams_match = (
                {event_team_a, event_team_b} == {team_a_canonical, team_b_canonical}
            )
            
            if teams_match:
                print(f"  ✓ Kalshi match: {title} ({event_ticker})")
                
                # IMPORTANT: Fetch actual market tickers from Kalshi API
                # Kalshi uses their own team codes (e.g., "LA" not "LAR")
                markets_url = f"https://api.elections.kalshi.com/trade-api/v2/markets?event_ticker={event_ticker}"
                markets_resp = requests.get(markets_url, timeout=15)
                markets_data = markets_resp.json()
                
                actual_markets = markets_data.get('markets', [])
                if len(actual_markets) != 2:
                    print(f"  ✗ Expected 2 markets, got {len(actual_markets)}")
                    continue
                
                # Extract actual tickers and codes
                market_tickers = {}
                for m in actual_markets:
                    ticker = m.get('ticker', '')
                    # Extract code from ticker (last part after final dash)
                    kalshi_code = ticker.split('-')[-1]
                    market_tickers[kalshi_code] = ticker
                    print(f"    Found market: {ticker} (code: {kalshi_code})")
                
                # Match Kalshi codes to our teams based on title order
                # Title format: "Team A at Team B" - team_a is away, team_b is home
                codes = list(market_tickers.keys())
                
                # Get team codes (for our internal use)
                code_a = get_team_code(team_a_canonical, sport)
                code_b = get_team_code(team_b_canonical, sport)
                
                # Find which Kalshi ticker corresponds to which team
                # Use the title to determine team order
                title_parts = title.split(' at ')
                if len(title_parts) == 2:
                    away_team = normalize_team(title_parts[0], sport)
                    home_team = normalize_team(title_parts[1], sport)
                else:
                    away_team = event_team_a
                    home_team = event_team_b
                
                # Assign tickers based on matching
                market_a_ticker = None
                market_b_ticker = None
                kalshi_code_a = None
                kalshi_code_b = None
                
                for kalshi_code, ticker in market_tickers.items():
                    # Try to match Kalshi code to our team
                    if team_a_canonical == away_team:
                        # team_a is away team
                        market_a_ticker = list(market_tickers.values())[0]
                        market_b_ticker = list(market_tickers.values())[1]
                        kalshi_code_a = list(market_tickers.keys())[0]
                        kalshi_code_b = list(market_tickers.keys())[1]
                    else:
                        market_a_ticker = list(market_tickers.values())[1]
                        market_b_ticker = list(market_tickers.values())[0]
                        kalshi_code_a = list(market_tickers.keys())[1]
                        kalshi_code_b = list(market_tickers.keys())[0]
                    break
                
                return {
                    'event_ticker': event_ticker,
                    'title': title,
                    'date': event_date,
                    'team_a': team_a_canonical,
                    'team_b': team_b_canonical,
                    'team_a_code': code_a,
                    'team_b_code': code_b,
                    'market_a_ticker': market_a_ticker,
                    'market_b_ticker': market_b_ticker,
                    'kalshi_code_a': kalshi_code_a,
                    'kalshi_code_b': kalshi_code_b,
                }
        
        print(f"  ✗ Kalshi: No match found for {team_a} vs {team_b} on {target_date}")
        return None
        
    except Exception as e:
        print(f"  ✗ Kalshi API error: {e}")
        return None


def query_polymarket_game(sport: str, target_date: str, team_a: str, team_b: str) -> Optional[Dict]:
    """
    Query Polymarket for a specific game.
    Uses sportsMarketType == "moneyline" to find correct market.
    Returns market info or None if not found.
    """
    
    # Polymarket slug patterns by sport
    team_a_canonical = normalize_team(team_a, sport)
    team_b_canonical = normalize_team(team_b, sport)
    
    if not team_a_canonical or not team_b_canonical:
        print(f"  ✗ Could not normalize teams: {team_a}, {team_b}")
        return None
    
    team_a_code = get_team_code(team_a_canonical, sport).lower()
    team_b_code = get_team_code(team_b_canonical, sport).lower()
    
    # Helper to expand LA team codes
    def expand_la_codes(code):
        """Returns list of possible code variations for LA teams"""
        if code == "lar":
            return ["lar", "la"]
        elif code == "lac":
            return ["lac", "la"]
        elif code == "lal":
            return ["lal", "la"]
        return [code]
    
    # Generate all slug variations
    slug_patterns = []
    for a_code in expand_la_codes(team_a_code):
        for b_code in expand_la_codes(team_b_code):
            slug_patterns.append(f"{sport.lower()}-{a_code}-{b_code}-{target_date}")
            slug_patterns.append(f"{sport.lower()}-{b_code}-{a_code}-{target_date}")
    
    for slug in slug_patterns:
        try:
            url = f"https://gamma-api.polymarket.com/events?slug={slug}"
            print(f"  Trying Polymarket slug: {slug}")
            
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            events = response.json()
            
            if not events:
                continue
            
            event = events[0]
            markets = event.get('markets', [])
            
            # Find the TRUE moneyline market using sportsMarketType
            moneyline_market = None
            for market in markets:
                market_type = market.get('sportsMarketType', '')
                if market_type == 'moneyline':
                    moneyline_market = market
                    break
            
            if not moneyline_market:
                # Fallback: look for market with team names as outcomes
                for market in markets:
                    outcomes_raw = market.get('outcomes', [])
                    if isinstance(outcomes_raw, str):
                        try:
                            outcomes = json.loads(outcomes_raw)
                        except:
                            continue
                    else:
                        outcomes = outcomes_raw
                    
                    if len(outcomes) != 2:
                        continue
                    
                    # Skip Over/Under
                    outcome_str = ' '.join(outcomes).lower()
                    if any(w in outcome_str for w in ['over', 'under', 'yes', 'no']):
                        continue
                    
                    # Check if outcomes are team names
                    o_a = normalize_team(outcomes[0], sport)
                    o_b = normalize_team(outcomes[1], sport)
                    if o_a and o_b:
                        moneyline_market = market
                        break
            
            if not moneyline_market:
                print(f"  ✗ No moneyline market in event: {event.get('title', '')}")
                continue
            
            # Extract data
            outcomes_raw = moneyline_market.get('outcomes', [])
            tokens_raw = moneyline_market.get('clobTokenIds', [])
            condition_id = moneyline_market.get('conditionId', '')
            
            if isinstance(outcomes_raw, str):
                outcomes = json.loads(outcomes_raw)
            else:
                outcomes = outcomes_raw
            
            if isinstance(tokens_raw, str):
                tokens = json.loads(tokens_raw)
            else:
                tokens = tokens_raw
            
            if len(outcomes) != 2 or len(tokens) != 2:
                continue
            
            # Map outcomes to team codes
            token_map = {}
            for outcome, token in zip(outcomes, tokens):
                canonical = normalize_team(outcome, sport)
                if canonical:
                    code = get_team_code(canonical, sport)
                    token_map[code] = token
            
            print(f"  ✓ Polymarket match: {event.get('title', '')} (sportsMarketType=moneyline)")
            
            return {
                'title': event.get('title', ''),
                'slug': slug,
                'condition_id': condition_id,
                'token_ids': token_map,
                'outcomes': outcomes,
                'start_date': event.get('startDate', ''),
                'end_date': event.get('endDate', ''),
            }
            
        except Exception as e:
            continue
    
    print(f"  ✗ Polymarket: No match found for {team_a} vs {team_b} on {target_date}")
    return None


# =============================================================================
# MARKET MANAGEMENT
# =============================================================================

def add_market(sport: str, date_str: str, team_a: str, team_b: str) -> bool:
    """Add a single market to markets.json"""
    
    print()
    print(f"Looking for: {sport.upper()} - {team_a} vs {team_b} on {date_str}")
    print("-" * 60)
    
    # Query both platforms
    kalshi = query_kalshi_game(sport, date_str, team_a, team_b)
    polymarket = query_polymarket_game(sport, date_str, team_a, team_b)
    
    if not kalshi:
        print()
        print("✗ Could not find game on Kalshi")
        return False
    
    if not polymarket:
        print()
        print("✗ Could not find game on Polymarket")
        return False
    
    # Build market entry
    event_id = kalshi['event_ticker'].lower()
    
    market_entry = {
        "event_id": event_id,
        "description": f"{sport.upper()}: {kalshi['title']}",
        "sport": sport.upper(),
        "event_date": polymarket.get('start_date', ''),
        "teams": {
            "team_a": kalshi['team_a'],
            "team_b": kalshi['team_b']
        },
        "kalshi": {
            "enabled": True,
            "markets": {
                "main": kalshi['market_a_ticker'],
                "opponent": kalshi['market_b_ticker']
            },
            "market_a_refers_to": kalshi['team_a'],
            "market_b_refers_to": kalshi['team_b']
        },
        "polymarket": {
            "enabled": True,
            "markets": {
                "slug": polymarket['slug']
            }
        },
        "poly_token_ids": polymarket['token_ids'],
        "poly_condition_id": polymarket['condition_id'],
        "poly_title": polymarket['title'],
        "home_team": kalshi['team_b_code'],
        "away_team": kalshi['team_a_code']
    }
    
    # Load current markets
    config = load_markets()
    
    # Check for duplicates
    existing_ids = {m['event_id'] for m in config.get('markets', [])}
    if event_id in existing_ids:
        print()
        print(f"⚠ Market already exists: {event_id}")
        return False
    
    # Add market
    config['markets'].append(market_entry)
    config['_updated_at'] = datetime.now(timezone.utc).isoformat()
    
    # Save
    save_markets(config)
    
    print()
    print("=" * 60)
    print("✓ MARKET ADDED SUCCESSFULLY")
    print("=" * 60)
    print(f"  Event ID:     {event_id}")
    print(f"  Kalshi:       {kalshi['market_a_ticker']}")
    print(f"                {kalshi['market_b_ticker']}")
    print(f"  Polymarket:   {polymarket['slug']}")
    print(f"  Tokens:       {polymarket['token_ids']}")
    print()
    
    return True


def list_markets():
    """List all current markets"""
    config = load_markets()
    markets = config.get('markets', [])
    
    print()
    print("=" * 80)
    print("CURRENT MARKETS")
    print("=" * 80)
    
    if not markets:
        print("  (No markets configured)")
        return
    
    # Group by sport
    by_sport = {}
    for m in markets:
        sport = m.get('sport', 'UNKNOWN')
        if sport not in by_sport:
            by_sport[sport] = []
        by_sport[sport].append(m)
    
    for sport, sport_markets in by_sport.items():
        print()
        print(f"  {sport} ({len(sport_markets)} markets):")
        print("  " + "-" * 76)
        for i, m in enumerate(sport_markets, 1):
            event_id = m.get('event_id', 'N/A')
            desc = m.get('description', 'N/A')
            print(f"    {i}. {desc}")
            print(f"       ID: {event_id}")
    
    print()
    print("=" * 80)
    print(f"Total: {len(markets)} markets")
    print()


def delete_market_interactive():
    """Interactive market deletion"""
    config = load_markets()
    markets = config.get('markets', [])
    
    if not markets:
        print("  No markets to delete.")
        return
    
    print()
    print("Delete options:")
    print("  1. Delete ALL markets")
    print("  2. Delete by SPORT (NFL, NBA, CFP)")
    print("  3. Delete ONE market")
    print("  4. Cancel")
    print()
    
    choice = input("Choose option [1-4]: ").strip()
    
    if choice == "1":
        confirm = input("Are you sure you want to delete ALL markets? [y/n]: ").strip().lower()
        if confirm == 'y':
            config['markets'] = []
            config['_updated_at'] = datetime.now(timezone.utc).isoformat()
            save_markets(config)
            print("✓ All markets deleted.")
        else:
            print("Cancelled.")
    
    elif choice == "2":
        sport = input("Enter sport to delete (NFL/NBA/CFP): ").strip().upper()
        original_count = len(markets)
        config['markets'] = [m for m in markets if m.get('sport', '').upper() != sport]
        deleted = original_count - len(config['markets'])
        if deleted > 0:
            config['_updated_at'] = datetime.now(timezone.utc).isoformat()
            save_markets(config)
            print(f"✓ Deleted {deleted} {sport} markets.")
        else:
            print(f"No {sport} markets found.")
    
    elif choice == "3":
        # Show numbered list
        print()
        for i, m in enumerate(markets, 1):
            print(f"  {i}. {m.get('description', m.get('event_id', 'N/A'))}")
        print()
        
        try:
            idx = int(input("Enter number to delete: ").strip()) - 1
            if 0 <= idx < len(markets):
                deleted = markets.pop(idx)
                config['_updated_at'] = datetime.now(timezone.utc).isoformat()
                save_markets(config)
                print(f"✓ Deleted: {deleted.get('description', deleted.get('event_id'))}")
            else:
                print("Invalid number.")
        except ValueError:
            print("Invalid input.")
    
    else:
        print("Cancelled.")


# =============================================================================
# INTERACTIVE MODE
# =============================================================================

def interactive_mode():
    """Main interactive mode"""
    print()
    print("=" * 60)
    print("  MARKET DISCOVERY TOOL - Interactive Mode")
    print("=" * 60)
    print()
    
    while True:
        print("Options:")
        print("  [A]dd market")
        print("  [D]elete market")
        print("  [L]ist markets")
        print("  [Q]uit")
        print()
        
        choice = input("Choose [A/D/L/Q]: ").strip().upper()
        
        if choice == 'Q':
            print("Goodbye!")
            break
        
        elif choice == 'L':
            list_markets()
        
        elif choice == 'D':
            delete_market_interactive()
        
        elif choice == 'A':
            # Get sport
            print()
            print("Sports: NFL, NBA, CFP")
            sport = input("Enter sport: ").strip().upper()
            
            if sport not in ['NFL', 'NBA', 'CFP']:
                print(f"Unknown sport: {sport}")
                continue
            
            # Get date
            print()
            print("Date formats: YYYY-MM-DD, MM/DD/YY, 'today', 'tomorrow'")
            date_input = input("Enter date: ").strip()
            
            try:
                target_date = parse_date_input(date_input)
                print(f"  → Parsed as: {target_date}")
            except ValueError as e:
                print(f"  ✗ {e}")
                continue
            
            # Get matchup
            print()
            print("Matchup format: 'Panthers vs Rams' or 'Carolina at LA'")
            matchup = input("Enter matchup: ").strip()
            
            # Parse matchup
            matchup_match = re.match(r'(.+?)\s+(vs\.?|at|@)\s+(.+)', matchup, re.IGNORECASE)
            if not matchup_match:
                print("  ✗ Could not parse matchup. Use 'Team A vs Team B' format.")
                continue
            
            team_a = matchup_match.group(1).strip()
            team_b = matchup_match.group(3).strip()
            
            # Validate teams
            team_a_canonical = normalize_team(team_a, sport)
            team_b_canonical = normalize_team(team_b, sport)
            
            if not team_a_canonical:
                print(f"  ✗ Unknown team: {team_a}")
                continue
            if not team_b_canonical:
                print(f"  ✗ Unknown team: {team_b}")
                continue
            
            print(f"  → Teams: {team_a_canonical} vs {team_b_canonical}")
            
            # Add market
            success = add_market(sport, target_date, team_a, team_b)
            
            if success:
                print("Restart the bot to use the new market.")
            
            print()
        
        else:
            print("Unknown option. Try again.")
            print()


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Market Discovery Tool - Add or remove markets interactively",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python market_discovery.py              # Interactive mode
    python market_discovery.py --list       # List current markets
    python market_discovery.py --clear      # Clear all markets
        """
    )
    
    parser.add_argument("--list", action="store_true", help="List current markets")
    parser.add_argument("--clear", action="store_true", help="Clear all markets")
    
    args = parser.parse_args()
    
    if args.list:
        list_markets()
    elif args.clear:
        confirm = input("Clear ALL markets? [y/n]: ").strip().lower()
        if confirm == 'y':
            save_markets({"markets": [], "_updated_at": datetime.now(timezone.utc).isoformat()})
            print("✓ All markets cleared.")
        else:
            print("Cancelled.")
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
