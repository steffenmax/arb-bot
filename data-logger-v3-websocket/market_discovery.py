#!/usr/bin/env python3
"""
Market Discovery CLI Tool

Automatically discovers and matches NBA games across Kalshi and Polymarket.

Usage:
    python market_discovery.py --sport nba --date 2026-01-09
    python market_discovery.py --sport nba --date today
    python market_discovery.py --sport nba --date tomorrow
    python market_discovery.py --sport nba --date today --dry-run
    python market_discovery.py --sport nba --date today --append
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
# TEAM ALIAS MAPPING - All 30 NBA Teams
# =============================================================================

NBA_TEAM_ALIASES = {
    # Eastern Conference - Atlantic
    "celtics": ["boston", "bos", "boston celtics", "celtics"],
    "nets": ["brooklyn", "bkn", "brk", "brooklyn nets", "nets"],
    "knicks": ["new york", "nyk", "new york knicks", "knicks"],
    "76ers": ["philadelphia", "phi", "sixers", "philadelphia 76ers", "76ers", "philly"],
    "raptors": ["toronto", "tor", "toronto raptors", "raptors"],
    
    # Eastern Conference - Central
    "bulls": ["chicago", "chi", "chicago bulls", "bulls"],
    "cavaliers": ["cleveland", "cle", "cavs", "cleveland cavaliers", "cavaliers"],
    "pistons": ["detroit", "det", "detroit pistons", "pistons"],
    "pacers": ["indiana", "ind", "indiana pacers", "pacers"],
    "bucks": ["milwaukee", "mil", "milwaukee bucks", "bucks"],
    
    # Eastern Conference - Southeast
    "hawks": ["atlanta", "atl", "atlanta hawks", "hawks"],
    "hornets": ["charlotte", "cha", "charlotte hornets", "hornets"],
    "heat": ["miami", "mia", "miami heat", "heat"],
    "magic": ["orlando", "orl", "orlando magic", "magic"],
    "wizards": ["washington", "was", "washington wizards", "wizards"],
    
    # Western Conference - Northwest
    "nuggets": ["denver", "den", "denver nuggets", "nuggets"],
    "timberwolves": ["minnesota", "min", "minnesota timberwolves", "timberwolves", "wolves"],
    "thunder": ["oklahoma city", "okc", "oklahoma city thunder", "thunder"],
    "trail blazers": ["portland", "por", "blazers", "portland trail blazers", "trail blazers", "trailblazers"],
    "jazz": ["utah", "uta", "utah jazz", "jazz"],
    
    # Western Conference - Pacific
    "warriors": ["golden state", "gsw", "golden state warriors", "warriors", "gs"],
    "clippers": ["los angeles c", "lac", "la clippers", "los angeles clippers", "clippers"],
    "lakers": ["los angeles l", "lal", "la lakers", "los angeles lakers", "lakers", "los angeles"],
    "suns": ["phoenix", "phx", "phoenix suns", "suns"],
    "kings": ["sacramento", "sac", "sacramento kings", "kings"],
    
    # Western Conference - Southwest
    "mavericks": ["dallas", "dal", "dallas mavericks", "mavericks", "mavs"],
    "rockets": ["houston", "hou", "houston rockets", "rockets"],
    "grizzlies": ["memphis", "mem", "memphis grizzlies", "grizzlies"],
    "pelicans": ["new orleans", "nop", "new orleans pelicans", "pelicans"],
    "spurs": ["san antonio", "sas", "san antonio spurs", "spurs"],
}

# Reverse mapping: alias -> canonical name
ALIAS_TO_CANONICAL = {}
for canonical, aliases in NBA_TEAM_ALIASES.items():
    for alias in aliases:
        ALIAS_TO_CANONICAL[alias.lower()] = canonical

# =============================================================================
# CFP TEAM ALIASES - College Football Playoff Teams
# =============================================================================

CFP_TEAM_ALIASES = {
    "oregon": ["oregon", "ore", "oregon ducks", "ducks"],
    "ohio state": ["ohio state", "osu", "ohio state buckeyes", "buckeyes"],
    "texas": ["texas", "tex", "texas longhorns", "longhorns"],
    "penn state": ["penn state", "psu", "penn state nittany lions", "nittany lions"],
    "notre dame": ["notre dame", "nd", "notre dame fighting irish", "fighting irish"],
    "georgia": ["georgia", "uga", "georgia bulldogs", "bulldogs"],
    "tennessee": ["tennessee", "tenn", "tennessee volunteers", "volunteers", "vols"],
    "indiana": ["indiana", "ind", "indiana hoosiers", "hoosiers"],
    "boise state": ["boise state", "bsu", "boise state broncos", "broncos"],
    "smu": ["smu", "southern methodist", "smu mustangs", "mustangs"],
    "clemson": ["clemson", "clem", "clemson tigers", "tigers"],
    "arizona state": ["arizona state", "asu", "arizona state sun devils", "sun devils"],
    "miami": ["miami", "mia", "miami hurricanes", "hurricanes"],
    "ole miss": ["ole miss", "miss", "ole miss rebels", "rebels", "mississippi"],
}

# CFP alias -> canonical
CFP_ALIAS_TO_CANONICAL = {}
for canonical, aliases in CFP_TEAM_ALIASES.items():
    for alias in aliases:
        CFP_ALIAS_TO_CANONICAL[alias.lower()] = canonical

# CFP canonical -> code
CFP_CANONICAL_TO_CODE = {
    "oregon": "ORE",
    "ohio state": "OSU",
    "texas": "TEX",
    "penn state": "PSU",
    "notre dame": "ND",
    "georgia": "UGA",
    "tennessee": "TENN",
    "indiana": "IND",
    "boise state": "BSU",
    "smu": "SMU",
    "clemson": "CLEM",
    "arizona state": "ASU",
    "miami": "MIA",
    "ole miss": "MISS",
}

# Canonical name -> 3-letter code
CANONICAL_TO_CODE = {
    "celtics": "BOS",
    "nets": "BKN",
    "knicks": "NYK",
    "76ers": "PHI",
    "raptors": "TOR",
    "bulls": "CHI",
    "cavaliers": "CLE",
    "pistons": "DET",
    "pacers": "IND",
    "bucks": "MIL",
    "hawks": "ATL",
    "hornets": "CHA",
    "heat": "MIA",
    "magic": "ORL",
    "wizards": "WAS",
    "nuggets": "DEN",
    "timberwolves": "MIN",
    "thunder": "OKC",
    "trail blazers": "POR",
    "jazz": "UTA",
    "warriors": "GSW",
    "clippers": "LAC",
    "lakers": "LAL",
    "suns": "PHX",
    "kings": "SAC",
    "mavericks": "DAL",
    "rockets": "HOU",
    "grizzlies": "MEM",
    "pelicans": "NOP",
    "spurs": "SAS",
}


# =============================================================================
# NFL TEAM ALIASES - All 32 Teams
# =============================================================================

NFL_TEAM_ALIASES = {
    # AFC East
    "bills": ["buffalo", "buf", "buffalo bills", "bills"],
    "dolphins": ["miami dolphins", "mia", "miami", "dolphins"],
    "patriots": ["new england", "ne", "new england patriots", "patriots", "pats"],
    "jets": ["new york jets", "nyj", "jets", "new york j"],
    
    # AFC North
    "ravens": ["baltimore", "bal", "baltimore ravens", "ravens"],
    "bengals": ["cincinnati", "cin", "cincinnati bengals", "bengals"],
    "browns": ["cleveland", "cle", "cleveland browns", "browns"],
    "steelers": ["pittsburgh", "pit", "pittsburgh steelers", "steelers"],
    
    # AFC South
    "texans": ["houston", "hou", "houston texans", "texans"],
    "colts": ["indianapolis", "ind", "indianapolis colts", "colts"],
    "jaguars": ["jacksonville", "jax", "jacksonville jaguars", "jaguars"],
    "titans": ["tennessee", "ten", "tennessee titans", "titans"],
    
    # AFC West
    "broncos": ["denver", "den", "denver broncos", "broncos"],
    "chiefs": ["kansas city", "kc", "kansas city chiefs", "chiefs"],
    "raiders": ["las vegas", "lv", "las vegas raiders", "raiders"],
    "chargers": ["los angeles chargers", "lac", "chargers", "la chargers"],
    
    # NFC East
    "cowboys": ["dallas", "dal", "dallas cowboys", "cowboys"],
    "giants": ["new york giants", "nyg", "giants", "new york g"],
    "eagles": ["philadelphia", "phi", "philadelphia eagles", "eagles"],
    "commanders": ["washington", "was", "washington commanders", "commanders"],
    
    # NFC North
    "bears": ["chicago", "chi", "chicago bears", "bears"],
    "lions": ["detroit", "det", "detroit lions", "lions"],
    "packers": ["green bay", "gb", "green bay packers", "packers"],
    "vikings": ["minnesota", "min", "minnesota vikings", "vikings"],
    
    # NFC South
    "falcons": ["atlanta", "atl", "atlanta falcons", "falcons"],
    "panthers": ["carolina", "car", "carolina panthers", "panthers"],
    "saints": ["new orleans", "no", "new orleans saints", "saints"],
    "buccaneers": ["tampa bay", "tb", "tampa bay buccaneers", "buccaneers", "bucs"],
    
    # NFC West
    "cardinals": ["arizona", "ari", "arizona cardinals", "cardinals"],
    "rams": ["los angeles rams", "lar", "rams", "la rams"],
    "49ers": ["san francisco", "sf", "san francisco 49ers", "49ers"],
    "seahawks": ["seattle", "sea", "seattle seahawks", "seahawks"],
}

# NFL alias -> canonical
NFL_ALIAS_TO_CANONICAL = {}
for canonical, aliases in NFL_TEAM_ALIASES.items():
    for alias in aliases:
        NFL_ALIAS_TO_CANONICAL[alias.lower()] = canonical

# NFL canonical -> code
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

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def parse_date_arg(date_str: str) -> str:
    """Parse date argument to YYYY-MM-DD format"""
    if date_str.lower() == "today":
        return datetime.now().strftime("%Y-%m-%d")
    elif date_str.lower() == "tomorrow":
        return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        # Validate format
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return date_str
        except ValueError:
            raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD, 'today', or 'tomorrow'")


def parse_kalshi_date(event_ticker: str) -> str:
    """Extract date from KXNBAGAME-26JAN09MILLAL -> 2026-01-09"""
    # Pattern: 26JAN09 = year 2026, month JAN, day 09
    match = re.search(r'-(\d{2})([A-Z]{3})(\d{2})', event_ticker)
    if not match:
        return None
    
    year_suffix = match.group(1)
    month_str = match.group(2).upper()
    day = match.group(3)
    
    month_map = {
        'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04',
        'MAY': '05', 'JUN': '06', 'JUL': '07', 'AUG': '08',
        'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'
    }
    
    month = month_map.get(month_str)
    if not month:
        return None
    
    return f"20{year_suffix}-{month}-{day}"


def parse_poly_date(start_date: str) -> str:
    """Extract date from ISO string 2026-01-09T15:03:00Z -> 2026-01-09"""
    if not start_date:
        return None
    return start_date[:10]


def normalize_team_name(name: str) -> str:
    """Convert any team name variant to canonical name (lowercase)"""
    if not name:
        return None
    
    name_lower = name.lower().strip()
    
    # Direct lookup
    if name_lower in ALIAS_TO_CANONICAL:
        return ALIAS_TO_CANONICAL[name_lower]
    
    # Try partial matching
    for alias, canonical in ALIAS_TO_CANONICAL.items():
        if alias in name_lower or name_lower in alias:
            return canonical
    
    return None


def get_team_code(canonical_name: str) -> str:
    """Get 3-letter code from canonical team name"""
    return CANONICAL_TO_CODE.get(canonical_name, canonical_name.upper()[:3])


def is_moneyline_market(market: dict) -> bool:
    """
    Return True if market is a moneyline (winner) market, not totals/props/spreads.
    
    Filters OUT:
    - Markets with Over/Under/Yes/No outcomes
    - Markets with O/U, Spread, 1H, player names in question
    """
    question = market.get('question', '').lower()
    outcomes_raw = market.get('outcomes', [])
    
    # Parse outcomes if JSON string
    if isinstance(outcomes_raw, str):
        try:
            outcomes = json.loads(outcomes_raw)
        except:
            return False
    else:
        outcomes = outcomes_raw
    
    # Must have exactly 2 outcomes
    if len(outcomes) != 2:
        return False
    
    # Filter out Over/Under/Yes/No markets
    outcome_str = ' '.join(outcomes).lower()
    if any(word in outcome_str for word in ['over', 'under', 'yes', 'no']):
        return False
    
    # Filter out by question content
    filter_phrases = ['o/u', 'spread', '1h', 'first half', 'points', 'rebounds', 
                      'assists', 'threes', '3-pointers', 'double', 'triple',
                      'total', 'alt ', 'alternative']
    if any(phrase in question for phrase in filter_phrases):
        return False
    
    # Both outcomes should be recognizable team names
    team_a = normalize_team_name(outcomes[0])
    team_b = normalize_team_name(outcomes[1])
    
    if not team_a or not team_b:
        return False
    
    return True


# =============================================================================
# API QUERY FUNCTIONS
# =============================================================================

def query_kalshi_nba(target_date: str, verbose: bool = False) -> List[Dict]:
    """
    Query Kalshi API for NBA games on target date.
    
    Returns list of:
    {
        'event_ticker': 'KXNBAGAME-26JAN09ATLDEN',
        'title': 'Atlanta at Denver',
        'date': '2026-01-09',
        'team_a': 'hawks',  # canonical
        'team_b': 'nuggets',  # canonical
        'team_a_code': 'ATL',
        'team_b_code': 'DEN',
        'market_a_ticker': 'KXNBAGAME-26JAN09ATLDEN-ATL',
        'market_b_ticker': 'KXNBAGAME-26JAN09ATLDEN-DEN',
    }
    """
    url = "https://api.elections.kalshi.com/trade-api/v2/events"
    params = {
        'series_ticker': 'KXNBAGAME',
        'status': 'open',
        'limit': 100
    }
    
    try:
        if verbose:
            print(f"  Querying Kalshi: {url}")
        
        response = requests.get(url, params=params, headers={'accept': 'application/json'}, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        events = data.get('events', [])
        if verbose:
            print(f"  Found {len(events)} total NBA events on Kalshi")
        
        results = []
        for event in events:
            event_ticker = event.get('event_ticker', '')
            title = event.get('title', '')
            
            # Parse date from ticker
            event_date = parse_kalshi_date(event_ticker)
            if not event_date:
                continue
            
            # Filter by target date
            if event_date != target_date:
                continue
            
            # Parse teams from title (e.g., "Atlanta at Denver")
            title_match = re.match(r'(.+?)\s+at\s+(.+)', title, re.IGNORECASE)
            if not title_match:
                title_match = re.match(r'(.+?)\s+vs\.?\s+(.+)', title, re.IGNORECASE)
            
            if not title_match:
                if verbose:
                    print(f"    Could not parse title: {title}")
                continue
            
            team_a_raw = title_match.group(1).strip()
            team_b_raw = title_match.group(2).strip()
            
            team_a = normalize_team_name(team_a_raw)
            team_b = normalize_team_name(team_b_raw)
            
            if not team_a or not team_b:
                if verbose:
                    print(f"    Could not normalize teams: {team_a_raw} vs {team_b_raw}")
                continue
            
            team_a_code = get_team_code(team_a)
            team_b_code = get_team_code(team_b)
            
            # Build market tickers
            market_a_ticker = f"{event_ticker}-{team_a_code}"
            market_b_ticker = f"{event_ticker}-{team_b_code}"
            
            results.append({
                'event_ticker': event_ticker,
                'title': title,
                'date': event_date,
                'team_a': team_a,
                'team_b': team_b,
                'team_a_raw': team_a_raw,
                'team_b_raw': team_b_raw,
                'team_a_code': team_a_code,
                'team_b_code': team_b_code,
                'market_a_ticker': market_a_ticker,
                'market_b_ticker': market_b_ticker,
            })
        
        if verbose:
            print(f"  {len(results)} games match date {target_date}")
        
        return results
    
    except requests.exceptions.Timeout:
        print("  ✗ Kalshi API timeout")
        return []
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Kalshi API error: {e}")
        return []


def query_polymarket_nba(target_date: str, verbose: bool = False) -> List[Dict]:
    """
    Query Polymarket API for NBA games on target date.
    
    Returns list of:
    {
        'title': 'Hawks vs. Nuggets',
        'date': '2026-01-09',
        'team_a': 'hawks',  # canonical
        'team_b': 'nuggets',  # canonical
        'team_a_code': 'ATL',
        'team_b_code': 'DEN',
        'condition_id': '0x...',
        'token_ids': {'ATL': '123...', 'DEN': '456...'},
        'start_date': '2026-01-09T15:03:00Z',
    }
    """
    url = "https://gamma-api.polymarket.com/events"
    params = {
        'series_id': '10345',  # NBA
        'closed': 'false',
        'limit': 200,
        'order': 'startTime',
        'ascending': 'true'
    }
    
    try:
        if verbose:
            print(f"  Querying Polymarket: {url}")
        
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        events = response.json()
        
        if verbose:
            print(f"  Found {len(events)} total NBA events on Polymarket")
        
        results = []
        for event in events:
            title = event.get('title', '')
            start_date = event.get('startDate', '')
            end_date = event.get('endDate', '')
            
            # For Polymarket NBA, use endDate - 1 day as the game date
            # (startDate is event creation, endDate is betting close time which is after the game)
            event_date = parse_poly_date(end_date)
            if event_date:
                end_dt = datetime.strptime(event_date, "%Y-%m-%d")
                game_dt = end_dt - timedelta(days=1)
                event_date = game_dt.strftime("%Y-%m-%d")
            
            if verbose:
                print(f"    Event: {title}, endDate={end_date[:10] if end_date else 'N/A'}, game_date={event_date}")
            
            if not event_date:
                continue
            
            # Filter by target date
            if event_date != target_date:
                continue
            
            # Find moneyline market
            markets = event.get('markets', [])
            moneyline_market = None
            
            for market in markets:
                # Check if market question matches event title (main winner market)
                question = market.get('question', '').strip()
                if question == title.strip() and is_moneyline_market(market):
                    moneyline_market = market
                    break
            
            # If no exact match, try finding any moneyline market
            if not moneyline_market:
                for market in markets:
                    if is_moneyline_market(market):
                        moneyline_market = market
                        break
            
            if not moneyline_market:
                if verbose:
                    print(f"    No moneyline market found for: {title}")
                continue
            
            # Extract outcomes and token IDs
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
            
            # Normalize team names
            team_a = normalize_team_name(outcomes[0])
            team_b = normalize_team_name(outcomes[1])
            
            if not team_a or not team_b:
                if verbose:
                    print(f"    Could not normalize teams: {outcomes}")
                continue
            
            team_a_code = get_team_code(team_a)
            team_b_code = get_team_code(team_b)
            
            results.append({
                'title': title,
                'date': event_date,
                'team_a': team_a,
                'team_b': team_b,
                'team_a_outcome': outcomes[0],
                'team_b_outcome': outcomes[1],
                'team_a_code': team_a_code,
                'team_b_code': team_b_code,
                'condition_id': condition_id,
                'token_ids': {team_a_code: tokens[0], team_b_code: tokens[1]},
                'start_date': start_date,
            })
        
        if verbose:
            print(f"  {len(results)} games match date {target_date}")
        
        return results
    
    except requests.exceptions.Timeout:
        print("  ✗ Polymarket API timeout")
        return []
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Polymarket API error: {e}")
        return []


# =============================================================================
# MATCHING FUNCTION
# =============================================================================

def match_games(kalshi_games: List[Dict], poly_games: List[Dict], verbose: bool = False) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Match games across platforms by team names.
    
    Returns:
        (matched_games, kalshi_only, poly_only)
    """
    matched = []
    kalshi_only = []
    poly_only = list(poly_games)  # Copy to track unmatched
    
    for k_game in kalshi_games:
        k_teams = frozenset([k_game['team_a'], k_game['team_b']])
        
        found_match = None
        for i, p_game in enumerate(poly_only):
            p_teams = frozenset([p_game['team_a'], p_game['team_b']])
            
            if k_teams == p_teams:
                found_match = (i, p_game)
                break
        
        if found_match:
            idx, p_game = found_match
            poly_only.pop(idx)
            
            # Create matched game entry
            matched.append({
                'kalshi': k_game,
                'polymarket': p_game,
            })
            
            if verbose:
                print(f"  ✓ Matched: {k_game['title']} <-> {p_game['title']}")
        else:
            kalshi_only.append(k_game)
            if verbose:
                print(f"  ✗ Kalshi only: {k_game['title']}")
    
    if verbose:
        for p_game in poly_only:
            print(f"  ✗ Polymarket only: {p_game['title']}")
    
    return matched, kalshi_only, poly_only


# =============================================================================
# OUTPUT FUNCTIONS
# =============================================================================

def print_results(matched: List[Dict], kalshi_only: List[Dict], poly_only: List[Dict], target_date: str):
    """Print results in a nice table format"""
    print()
    print("=" * 100)
    print(f"MARKET DISCOVERY RESULTS - {target_date}")
    print("=" * 100)
    
    # Matched games
    print()
    print(f"✓ MATCHED GAMES ({len(matched)}):")
    print("-" * 100)
    if matched:
        print(f"{'Game':<40} {'Kalshi Ticker':<35} {'Poly Tokens':<20}")
        print("-" * 100)
        for m in matched:
            k = m['kalshi']
            p = m['polymarket']
            game = f"{k['team_a_code']} @ {k['team_b_code']}"
            kalshi_ticker = k['event_ticker']
            poly_tokens = f"{p['team_a_code']}, {p['team_b_code']}"
            print(f"{game:<40} {kalshi_ticker:<35} {poly_tokens:<20}")
    else:
        print("  No matched games found.")
    
    # Kalshi only
    print()
    print(f"✗ KALSHI ONLY ({len(kalshi_only)}):")
    print("-" * 100)
    if kalshi_only:
        for game in kalshi_only:
            print(f"  {game['title']} ({game['event_ticker']})")
    else:
        print("  None")
    
    # Polymarket only
    print()
    print(f"✗ POLYMARKET ONLY ({len(poly_only)}):")
    print("-" * 100)
    if poly_only:
        for game in poly_only:
            print(f"  {game['title']} (tokens: {game['team_a_code']}, {game['team_b_code']})")
    else:
        print("  None")
    
    print()
    print("=" * 100)


def build_markets_json(matched: List[Dict], target_date: str, sport: str = "NBA") -> Dict:
    """Build markets.json structure from matched games"""
    markets = []
    
    for m in matched:
        k = m['kalshi']
        p = m['polymarket']
        
        # Build event_id from Kalshi ticker (lowercase)
        event_id = k['event_ticker'].lower()
        
        # Description
        description = f"{k['team_a_raw']} at {k['team_b_raw']}"
        
        market_entry = {
            "event_id": event_id,
            "description": description,
            "sport": sport.upper(),
            "event_date": p['start_date'],
            "teams": {
                "team_a": k['team_a_raw'],
                "team_b": k['team_b_raw']
            },
            "kalshi": {
                "enabled": True,
                "markets": {
                    "main": k['market_a_ticker'],
                    "opponent": k['market_b_ticker']
                },
                "market_a_refers_to": k['team_a_raw'],
                "market_b_refers_to": k['team_b_raw']
            },
            "polymarket": {
                "enabled": True,
                "markets": {
                    "slug": f"nba-{k['team_a_code'].lower()}-{k['team_b_code'].lower()}-{target_date}"
                }
            },
            "poly_token_ids": p['token_ids'],
            "poly_condition_id": p['condition_id'],
            "poly_title": p['title'],
            "home_team": k['team_b_code'],
            "away_team": k['team_a_code']
        }
        
        markets.append(market_entry)
    
    return {
        "_comment": f"Active {sport.upper()} markets for {target_date}",
        "_generated_at": datetime.now(timezone.utc).isoformat(),
        "_note": f"Auto-discovered by market_discovery.py",
        "markets": markets
    }


def write_markets_json(config: Dict, append: bool = False) -> bool:
    """Write markets.json file"""
    config_path = Path(__file__).parent / "config" / "markets.json"
    
    try:
        if append and config_path.exists():
            # Load existing config
            with open(config_path, 'r') as f:
                existing = json.load(f)
            
            # Get existing event_ids
            existing_ids = {m['event_id'] for m in existing.get('markets', [])}
            
            # Add new markets that don't exist
            added = 0
            for market in config['markets']:
                if market['event_id'] not in existing_ids:
                    existing['markets'].append(market)
                    added += 1
            
            print(f"  Added {added} new markets (skipped {len(config['markets']) - added} duplicates)")
            config = existing
        
        # Write to file
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"  ✓ Written to {config_path}")
        return True
    
    except Exception as e:
        print(f"  ✗ Error writing file: {e}")
        return False


# =============================================================================
# MAIN CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Discover and match NBA games across Kalshi and Polymarket",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python market_discovery.py --sport nba --date 2026-01-09
    python market_discovery.py --sport nba --date today
    python market_discovery.py --sport nba --date tomorrow --dry-run
    python market_discovery.py --sport nba --date today --append
        """
    )
    
    parser.add_argument(
        "--sport", 
        type=str, 
        default="nba",
        choices=["nba", "nfl", "cfp", "all"],
        help="Sport to discover: nba, cfp, or 'all' for both (default: nba)"
    )
    
    parser.add_argument(
        "--date", 
        type=str, 
        required=True,
        help="Target date: YYYY-MM-DD, 'today', or 'tomorrow'"
    )
    
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Show what would be written without actually writing"
    )
    
    parser.add_argument(
        "--append", 
        action="store_true",
        help="Add to existing markets.json instead of overwriting"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output"
    )
    
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt and write immediately"
    )
    
    args = parser.parse_args()
    
    # Parse date
    try:
        target_date = parse_date_arg(args.date)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    print()
    print("=" * 60)
    print(f"MARKET DISCOVERY - {args.sport.upper()} - {target_date}")
    print("=" * 60)
    
    # Route based on sport
    if args.sport.lower() == "nba":
        discover_nba(target_date, args)
    elif args.sport.lower() == "nfl":
        discover_nfl(target_date, args)
    elif args.sport.lower() == "cfp":
        discover_cfp(target_date, args)
    elif args.sport.lower() == "all":
        discover_all(target_date, args)
    else:
        print(f"Error: Sport '{args.sport}' not yet supported")
        sys.exit(1)


def discover_nba(target_date: str, args):
    """Discover NBA games"""
    
    # Step 1: Query Kalshi
    print()
    print("Step 1: Querying Kalshi...")
    kalshi_games = query_kalshi_nba(target_date, verbose=args.verbose)
    print(f"  Found {len(kalshi_games)} Kalshi games for {target_date}")
    
    # Step 2: Query Polymarket
    print()
    print("Step 2: Querying Polymarket...")
    poly_games = query_polymarket_nba(target_date, verbose=args.verbose)
    print(f"  Found {len(poly_games)} Polymarket games for {target_date}")
    
    # Step 3: Match games
    print()
    print("Step 3: Matching games...")
    matched, kalshi_only, poly_only = match_games(kalshi_games, poly_games, verbose=args.verbose)
    print(f"  Matched: {len(matched)}")
    print(f"  Kalshi only: {len(kalshi_only)}")
    print(f"  Polymarket only: {len(poly_only)}")
    
    # Step 4: Print results
    print_results(matched, kalshi_only, poly_only, target_date)
    
    # Step 5: Write to markets.json
    if len(matched) == 0:
        print("No matched games to write.")
        sys.exit(0)
    
    config = build_markets_json(matched, target_date, args.sport)
    
    if args.dry_run:
        print()
        print("DRY RUN - Would write:")
        print("-" * 60)
        print(json.dumps(config, indent=2))
        print("-" * 60)
        print("(No changes made)")
    else:
        # Prompt for confirmation unless --yes flag
        if not args.yes:
            print()
            response = input(f"Write {len(matched)} markets to markets.json? [y/n]: ").strip().lower()
            if response != 'y':
                print("Aborted.")
                sys.exit(0)
        
        print()
        print("Step 5: Writing markets.json...")
        success = write_markets_json(config, append=args.append)
        
        if success:
            print()
            print("✓ Done! Restart the bot to use new markets.")
        else:
            sys.exit(1)


# =============================================================================
# CFP QUERY FUNCTIONS
# =============================================================================

def normalize_cfp_team_name(name: str) -> str:
    """Convert any CFP team name variant to canonical name"""
    if not name:
        return None
    
    name_lower = name.lower().strip()
    
    # Direct lookup
    if name_lower in CFP_ALIAS_TO_CANONICAL:
        return CFP_ALIAS_TO_CANONICAL[name_lower]
    
    # Try partial matching
    for alias, canonical in CFP_ALIAS_TO_CANONICAL.items():
        if alias in name_lower or name_lower in alias:
            return canonical
    
    return None


def get_cfp_team_code(canonical_name: str) -> str:
    """Get code from canonical CFP team name"""
    return CFP_CANONICAL_TO_CODE.get(canonical_name, canonical_name.upper()[:3])


def query_kalshi_cfp(target_date: str, verbose: bool = False) -> List[Dict]:
    """Query Kalshi API for CFP games on target date"""
    url = "https://api.elections.kalshi.com/trade-api/v2/events"
    params = {
        'series_ticker': 'KXNCAAFGAME',
        'status': 'open',
        'limit': 50
    }
    
    try:
        if verbose:
            print(f"  Querying Kalshi: {url}")
        
        response = requests.get(url, params=params, headers={'accept': 'application/json'}, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        events = data.get('events', [])
        if verbose:
            print(f"  Found {len(events)} total CFP events on Kalshi")
        
        results = []
        for event in events:
            event_ticker = event.get('event_ticker', '')
            title = event.get('title', '')
            
            # Parse date from ticker
            event_date = parse_kalshi_date(event_ticker)
            if not event_date:
                continue
            
            # Filter by target date
            if event_date != target_date:
                continue
            
            # Parse teams from title (e.g., "Oregon at Indiana")
            title_match = re.match(r'(.+?)\s+at\s+(.+)', title, re.IGNORECASE)
            if not title_match:
                title_match = re.match(r'(.+?)\s+vs\.?\s+(.+)', title, re.IGNORECASE)
            
            if not title_match:
                if verbose:
                    print(f"    Could not parse title: {title}")
                continue
            
            team_a_raw = title_match.group(1).strip()
            team_b_raw = title_match.group(2).strip()
            
            team_a = normalize_cfp_team_name(team_a_raw)
            team_b = normalize_cfp_team_name(team_b_raw)
            
            if not team_a or not team_b:
                if verbose:
                    print(f"    Could not normalize CFP teams: {team_a_raw} vs {team_b_raw}")
                continue
            
            team_a_code = get_cfp_team_code(team_a)
            team_b_code = get_cfp_team_code(team_b)
            
            # Build market tickers
            market_a_ticker = f"{event_ticker}-{team_a_code}"
            market_b_ticker = f"{event_ticker}-{team_b_code}"
            
            results.append({
                'event_ticker': event_ticker,
                'title': title,
                'date': event_date,
                'team_a': team_a,
                'team_b': team_b,
                'team_a_raw': team_a_raw,
                'team_b_raw': team_b_raw,
                'team_a_code': team_a_code,
                'team_b_code': team_b_code,
                'market_a_ticker': market_a_ticker,
                'market_b_ticker': market_b_ticker,
            })
        
        if verbose:
            print(f"  {len(results)} games match date {target_date}")
        
        return results
    
    except requests.exceptions.Timeout:
        print("  ✗ Kalshi API timeout")
        return []
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Kalshi API error: {e}")
        return []


def query_polymarket_cfp(target_date: str, verbose: bool = False) -> List[Dict]:
    """Query Polymarket API for CFP games on target date"""
    url = "https://gamma-api.polymarket.com/events"
    params = {
        'series_id': '10210',  # CFP
        'closed': 'false',
        'limit': 50
    }
    
    try:
        if verbose:
            print(f"  Querying Polymarket: {url}")
        
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        events = response.json()
        
        if verbose:
            print(f"  Found {len(events)} total CFP events on Polymarket")
        
        results = []
        for event in events:
            title = event.get('title', '')
            start_date = event.get('startDate', '')
            end_date = event.get('endDate', '')
            
            # For CFP, use endDate as the game date (startDate is creation date)
            # The game date is the day BEFORE endDate (game ends next day in UTC)
            event_date = parse_poly_date(end_date)
            if event_date:
                # Parse the date and subtract 1 day to get actual game date
                from datetime import datetime, timedelta
                end_dt = datetime.strptime(event_date, "%Y-%m-%d")
                game_dt = end_dt - timedelta(days=1)
                event_date = game_dt.strftime("%Y-%m-%d")
            
            if verbose:
                print(f"    CFP event: {title}, endDate={end_date[:10]}, computed_game_date={event_date}")
            
            if not event_date:
                continue
            
            # Filter by target date
            if event_date != target_date:
                continue
            
            # Find moneyline market
            markets = event.get('markets', [])
            moneyline_market = None
            
            for market in markets:
                # Check if it's a moneyline market (2 team outcomes)
                question = market.get('question', '').strip()
                outcomes_raw = market.get('outcomes', [])
                
                if isinstance(outcomes_raw, str):
                    outcomes = json.loads(outcomes_raw)
                else:
                    outcomes = outcomes_raw
                
                if len(outcomes) != 2:
                    continue
                
                # Filter out Over/Under/Yes/No
                outcome_str = ' '.join(outcomes).lower()
                if any(word in outcome_str for word in ['over', 'under', 'yes', 'no']):
                    continue
                
                # Both outcomes should be recognizable team names
                t_a = normalize_cfp_team_name(outcomes[0])
                t_b = normalize_cfp_team_name(outcomes[1])
                
                if t_a and t_b:
                    moneyline_market = market
                    break
            
            if not moneyline_market:
                if verbose:
                    print(f"    No moneyline market found for: {title}")
                continue
            
            # Extract outcomes and token IDs
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
            
            # Normalize team names
            team_a = normalize_cfp_team_name(outcomes[0])
            team_b = normalize_cfp_team_name(outcomes[1])
            
            if not team_a or not team_b:
                if verbose:
                    print(f"    Could not normalize CFP teams: {outcomes}")
                continue
            
            team_a_code = get_cfp_team_code(team_a)
            team_b_code = get_cfp_team_code(team_b)
            
            results.append({
                'title': title,
                'date': event_date,
                'team_a': team_a,
                'team_b': team_b,
                'team_a_outcome': outcomes[0],
                'team_b_outcome': outcomes[1],
                'team_a_code': team_a_code,
                'team_b_code': team_b_code,
                'condition_id': condition_id,
                'token_ids': {team_a_code: tokens[0], team_b_code: tokens[1]},
                'start_date': start_date,
            })
        
        if verbose:
            print(f"  {len(results)} games match date {target_date}")
        
        return results
    
    except requests.exceptions.Timeout:
        print("  ✗ Polymarket API timeout")
        return []
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Polymarket API error: {e}")
        return []


def build_cfp_markets_json(matched: List[Dict], target_date: str) -> Dict:
    """Build markets.json structure from matched CFP games"""
    markets = []
    
    for m in matched:
        k = m['kalshi']
        p = m['polymarket']
        
        # Build event_id from Kalshi ticker (lowercase)
        event_id = k['event_ticker'].lower()
        
        # Description
        description = f"CFP: {k['team_a_raw']} vs {k['team_b_raw']}"
        
        market_entry = {
            "event_id": event_id,
            "description": description,
            "sport": "CFP",
            "event_date": p['start_date'],
            "teams": {
                "team_a": k['team_a_raw'],
                "team_b": k['team_b_raw']
            },
            "kalshi": {
                "enabled": True,
                "markets": {
                    "main": k['market_a_ticker'],
                    "opponent": k['market_b_ticker']
                },
                "market_a_refers_to": k['team_a_raw'],
                "market_b_refers_to": k['team_b_raw']
            },
            "polymarket": {
                "enabled": True,
                "markets": {
                    "slug": f"cfp-{k['team_a_code'].lower()}-{k['team_b_code'].lower()}-{target_date}"
                }
            },
            "poly_token_ids": p['token_ids'],
            "poly_condition_id": p['condition_id'],
            "poly_title": p['title'],
            "home_team": k['team_b_code'],
            "away_team": k['team_a_code']
        }
        
        markets.append(market_entry)
    
    return {
        "_comment": f"Active CFP markets for {target_date}",
        "_generated_at": datetime.now(timezone.utc).isoformat(),
        "_note": f"Auto-discovered by market_discovery.py",
        "markets": markets
    }


# =============================================================================
# NFL QUERY FUNCTIONS
# =============================================================================

def normalize_nfl_team_name(name: str) -> str:
    """Convert any NFL team name variant to canonical name"""
    if not name:
        return None
    
    name_lower = name.lower().strip()
    
    # Direct lookup
    if name_lower in NFL_ALIAS_TO_CANONICAL:
        return NFL_ALIAS_TO_CANONICAL[name_lower]
    
    # Try partial matching
    for alias, canonical in NFL_ALIAS_TO_CANONICAL.items():
        if alias in name_lower or name_lower in alias:
            return canonical
    
    return None


def get_nfl_team_code(canonical_name: str) -> str:
    """Get code from canonical NFL team name"""
    return NFL_CANONICAL_TO_CODE.get(canonical_name, canonical_name.upper()[:3])


def query_kalshi_nfl(target_date: str, verbose: bool = False) -> List[Dict]:
    """Query Kalshi API for NFL games on target date"""
    url = "https://api.elections.kalshi.com/trade-api/v2/events"
    params = {
        'series_ticker': 'KXNFLGAME',
        'status': 'open',
        'limit': 50
    }
    
    try:
        if verbose:
            print(f"  Querying Kalshi: {url}")
        
        response = requests.get(url, params=params, headers={'accept': 'application/json'}, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        events = data.get('events', [])
        if verbose:
            print(f"  Found {len(events)} total NFL events on Kalshi")
        
        results = []
        for event in events:
            event_ticker = event.get('event_ticker', '')
            title = event.get('title', '')
            
            # Parse date from ticker
            event_date = parse_kalshi_date(event_ticker)
            if not event_date:
                continue
            
            # Filter by target date
            if event_date != target_date:
                continue
            
            # Parse teams from title (e.g., "Baltimore at Pittsburgh")
            title_match = re.match(r'(.+?)\s+at\s+(.+)', title, re.IGNORECASE)
            if not title_match:
                title_match = re.match(r'(.+?)\s+vs\.?\s+(.+)', title, re.IGNORECASE)
            
            if not title_match:
                if verbose:
                    print(f"    Could not parse title: {title}")
                continue
            
            team_a_raw = title_match.group(1).strip()
            team_b_raw = title_match.group(2).strip()
            
            team_a = normalize_nfl_team_name(team_a_raw)
            team_b = normalize_nfl_team_name(team_b_raw)
            
            if not team_a or not team_b:
                if verbose:
                    print(f"    Could not normalize NFL teams: {team_a_raw} vs {team_b_raw}")
                continue
            
            team_a_code = get_nfl_team_code(team_a)
            team_b_code = get_nfl_team_code(team_b)
            
            # Build market tickers
            market_a_ticker = f"{event_ticker}-{team_a_code}"
            market_b_ticker = f"{event_ticker}-{team_b_code}"
            
            results.append({
                'event_ticker': event_ticker,
                'title': title,
                'date': event_date,
                'team_a': team_a,
                'team_b': team_b,
                'team_a_raw': team_a_raw,
                'team_b_raw': team_b_raw,
                'team_a_code': team_a_code,
                'team_b_code': team_b_code,
                'market_a_ticker': market_a_ticker,
                'market_b_ticker': market_b_ticker,
            })
        
        if verbose:
            print(f"  {len(results)} games match date {target_date}")
        
        return results
    
    except requests.exceptions.Timeout:
        print("  ✗ Kalshi API timeout")
        return []
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Kalshi API error: {e}")
        return []


def query_polymarket_nfl(target_date: str, verbose: bool = False) -> List[Dict]:
    """Query Polymarket API for NFL games on target date"""
    
    # Try multiple potential NFL series IDs
    potential_series_ids = ['10280', '10201', '10200', None]  # None = search all
    
    all_nfl_events = []
    
    for series_id in potential_series_ids:
        try:
            url = "https://gamma-api.polymarket.com/events"
            params = {
                'closed': 'false',
                'limit': 200
            }
            if series_id:
                params['series_id'] = series_id
            
            if verbose and series_id:
                print(f"  Trying Polymarket series_id={series_id}...")
            elif verbose:
                print(f"  Querying all Polymarket events...")
            
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            events = response.json()
            
            # Filter for NFL events by title keywords
            for event in events:
                title = event.get('title', '').lower()
                # NFL games typically have team names or "nfl" in title
                if any(keyword in title for keyword in ['vs', 'vs.', '@']):
                    # Check if title contains NFL team names
                    words = title.split()
                    has_nfl_team = False
                    for word in words:
                        if normalize_nfl_team_name(word):
                            has_nfl_team = True
                            break
                    
                    if has_nfl_team:
                        all_nfl_events.append(event)
            
            if all_nfl_events and verbose:
                print(f"  Found {len(all_nfl_events)} potential NFL events")
                break
                
        except Exception as e:
            if verbose:
                print(f"  Error with series_id={series_id}: {e}")
            continue
    
    if verbose:
        print(f"  Found {len(all_nfl_events)} total NFL events on Polymarket")
    
    results = []
    for event in all_nfl_events:
        title = event.get('title', '')
        start_date = event.get('startDate', '')
        end_date = event.get('endDate', '')
        
        # For NFL, use endDate - 1 day as the game date
        event_date = parse_poly_date(end_date)
        if event_date:
            end_dt = datetime.strptime(event_date, "%Y-%m-%d")
            game_dt = end_dt - timedelta(days=1)
            event_date = game_dt.strftime("%Y-%m-%d")
        
        if verbose:
            print(f"    NFL event: {title}, endDate={end_date[:10] if end_date else 'N/A'}, game_date={event_date}")
        
        if not event_date:
            continue
        
        # Filter by target date
        if event_date != target_date:
            continue
        
        # Find moneyline market - be more lenient for NFL
        markets = event.get('markets', [])
        moneyline_market = None
        
        for market in markets:
            question = market.get('question', '').strip()
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
            
            # Filter out Over/Under/Yes/No
            outcome_str = ' '.join(outcomes).lower()
            if any(word in outcome_str for word in ['over', 'under', 'yes', 'no']):
                continue
            
            # Filter out obvious non-moneyline markets
            question_lower = question.lower()
            if any(phrase in question_lower for phrase in ['spread', 'total', 'o/u', 'points', 'score']):
                continue
            
            # Both outcomes should be recognizable team names
            t_a = normalize_nfl_team_name(outcomes[0])
            t_b = normalize_nfl_team_name(outcomes[1])
            
            if t_a and t_b:
                moneyline_market = market
                if verbose:
                    print(f"      Found moneyline: {question} - {outcomes}")
                break
        
        if not moneyline_market:
            if verbose:
                print(f"    No moneyline market found for: {title}")
                print(f"      Available markets: {[m.get('question', '') for m in markets[:3]]}")
            continue
        
        # Extract outcomes and token IDs
        outcomes_raw = moneyline_market.get('outcomes', [])
        tokens_raw = moneyline_market.get('clobTokenIds', [])
        condition_id = moneyline_market.get('conditionId', '')
        
        if isinstance(outcomes_raw, str):
            try:
                outcomes = json.loads(outcomes_raw)
            except:
                outcomes = outcomes_raw
        else:
            outcomes = outcomes_raw
        
        if isinstance(tokens_raw, str):
            try:
                tokens = json.loads(tokens_raw)
            except:
                tokens = tokens_raw
        else:
            tokens = tokens_raw
        
        if len(outcomes) != 2 or len(tokens) != 2:
            if verbose:
                print(f"    Invalid outcomes/tokens for: {title}")
            continue
        
        # Normalize team names
        team_a = normalize_nfl_team_name(outcomes[0])
        team_b = normalize_nfl_team_name(outcomes[1])
        
        if not team_a or not team_b:
            if verbose:
                print(f"    Could not normalize NFL teams: {outcomes}")
            continue
        
        team_a_code = get_nfl_team_code(team_a)
        team_b_code = get_nfl_team_code(team_b)
        
        results.append({
            'title': title,
            'date': event_date,
            'team_a': team_a,
            'team_b': team_b,
            'team_a_outcome': outcomes[0],
            'team_b_outcome': outcomes[1],
            'team_a_code': team_a_code,
            'team_b_code': team_b_code,
            'condition_id': condition_id,
            'token_ids': {team_a_code: tokens[0], team_b_code: tokens[1]},
            'start_date': start_date,
        })
    
    if verbose:
        print(f"  {len(results)} NFL games match date {target_date}")
    
    return results


def build_nfl_markets_json(matched: List[Dict], target_date: str) -> Dict:
    """Build markets.json structure from matched NFL games"""
    markets = []
    
    for m in matched:
        k = m['kalshi']
        p = m['polymarket']
        
        # Build event_id from Kalshi ticker (lowercase)
        event_id = k['event_ticker'].lower()
        
        # Description
        description = f"NFL: {k['team_a_raw']} at {k['team_b_raw']}"
        
        market_entry = {
            "event_id": event_id,
            "description": description,
            "sport": "NFL",
            "event_date": p['start_date'],
            "teams": {
                "team_a": k['team_a_raw'],
                "team_b": k['team_b_raw']
            },
            "kalshi": {
                "enabled": True,
                "markets": {
                    "main": k['market_a_ticker'],
                    "opponent": k['market_b_ticker']
                },
                "market_a_refers_to": k['team_a_raw'],
                "market_b_refers_to": k['team_b_raw']
            },
            "polymarket": {
                "enabled": True,
                "markets": {
                    "slug": f"nfl-{k['team_a_code'].lower()}-{k['team_b_code'].lower()}-{target_date}"
                }
            },
            "poly_token_ids": p['token_ids'],
            "poly_condition_id": p['condition_id'],
            "poly_title": p['title'],
            "home_team": k['team_b_code'],
            "away_team": k['team_a_code']
        }
        
        markets.append(market_entry)
    
    return {
        "_comment": f"Active NFL markets for {target_date}",
        "_generated_at": datetime.now(timezone.utc).isoformat(),
        "_note": f"Auto-discovered by market_discovery.py",
        "markets": markets
    }


def discover_nfl(target_date: str, args):
    """Discover NFL games"""
    
    # Step 1: Query Kalshi
    print()
    print("Step 1: Querying Kalshi NFL...")
    kalshi_games = query_kalshi_nfl(target_date, verbose=args.verbose)
    print(f"  Found {len(kalshi_games)} Kalshi NFL games for {target_date}")
    
    # Step 2: Query Polymarket
    print()
    print("Step 2: Querying Polymarket NFL...")
    poly_games = query_polymarket_nfl(target_date, verbose=args.verbose)
    print(f"  Found {len(poly_games)} Polymarket NFL games for {target_date}")
    
    # Step 3: Match games
    print()
    print("Step 3: Matching games...")
    matched, kalshi_only, poly_only = match_games(kalshi_games, poly_games, verbose=args.verbose)
    print(f"  Matched: {len(matched)}")
    print(f"  Kalshi only: {len(kalshi_only)}")
    print(f"  Polymarket only: {len(poly_only)}")
    
    # Step 4: Print results
    print_results(matched, kalshi_only, poly_only, target_date)
    
    # Step 5: Write to markets.json
    if len(matched) == 0:
        print("No matched games to write.")
        sys.exit(0)
    
    config = build_nfl_markets_json(matched, target_date)
    
    if args.dry_run:
        print()
        print("DRY RUN - Would write:")
        print("-" * 60)
        print(json.dumps(config, indent=2))
        print("-" * 60)
        print("(No changes made)")
    else:
        # Prompt for confirmation unless --yes flag
        if not args.yes:
            print()
            response = input(f"Write {len(matched)} markets to markets.json? [y/n]: ").strip().lower()
            if response != 'y':
                print("Aborted.")
                sys.exit(0)
        
        print()
        print("Step 5: Writing markets.json...")
        success = write_markets_json(config, append=args.append)
        
        if success:
            print()
            print("✓ Done! Restart the bot to use new markets.")
        else:
            sys.exit(1)


def discover_cfp(target_date: str, args):
    """Discover CFP games"""
    
    # Step 1: Query Kalshi
    print()
    print("Step 1: Querying Kalshi CFP...")
    kalshi_games = query_kalshi_cfp(target_date, verbose=args.verbose)
    print(f"  Found {len(kalshi_games)} Kalshi CFP games for {target_date}")
    
    # Step 2: Query Polymarket
    print()
    print("Step 2: Querying Polymarket CFP...")
    poly_games = query_polymarket_cfp(target_date, verbose=args.verbose)
    print(f"  Found {len(poly_games)} Polymarket CFP games for {target_date}")
    
    # Step 3: Match games
    print()
    print("Step 3: Matching games...")
    matched, kalshi_only, poly_only = match_games(kalshi_games, poly_games, verbose=args.verbose)
    print(f"  Matched: {len(matched)}")
    print(f"  Kalshi only: {len(kalshi_only)}")
    print(f"  Polymarket only: {len(poly_only)}")
    
    # Step 4: Print results
    print_results(matched, kalshi_only, poly_only, target_date)
    
    # Step 5: Write to markets.json
    if len(matched) == 0:
        print("No matched games to write.")
        sys.exit(0)
    
    config = build_cfp_markets_json(matched, target_date)
    
    if args.dry_run:
        print()
        print("DRY RUN - Would write:")
        print("-" * 60)
        print(json.dumps(config, indent=2))
        print("-" * 60)
        print("(No changes made)")
    else:
        # Prompt for confirmation unless --yes flag
        if not args.yes:
            print()
            response = input(f"Write {len(matched)} markets to markets.json? [y/n]: ").strip().lower()
            if response != 'y':
                print("Aborted.")
                sys.exit(0)
        
        print()
        print("Step 5: Writing markets.json...")
        success = write_markets_json(config, append=args.append)
        
        if success:
            print()
            print("✓ Done! Restart the bot to use new markets.")
        else:
            sys.exit(1)


def discover_all(target_date: str, args):
    """Discover NBA, NFL, and CFP games"""
    all_matched = []
    
    # Query NBA
    print()
    print("=" * 60)
    print("DISCOVERING NBA GAMES")
    print("=" * 60)
    
    print()
    print("Querying Kalshi NBA...")
    kalshi_nba = query_kalshi_nba(target_date, verbose=args.verbose)
    print(f"  Found {len(kalshi_nba)} Kalshi NBA games")
    
    print()
    print("Querying Polymarket NBA...")
    poly_nba = query_polymarket_nba(target_date, verbose=args.verbose)
    print(f"  Found {len(poly_nba)} Polymarket NBA games")
    
    print()
    print("Matching NBA games...")
    matched_nba, kalshi_only_nba, poly_only_nba = match_games(kalshi_nba, poly_nba, verbose=args.verbose)
    print(f"  Matched: {len(matched_nba)}")
    
    # Query NFL
    print()
    print("=" * 60)
    print("DISCOVERING NFL GAMES")
    print("=" * 60)
    
    print()
    print("Querying Kalshi NFL...")
    kalshi_nfl = query_kalshi_nfl(target_date, verbose=args.verbose)
    print(f"  Found {len(kalshi_nfl)} Kalshi NFL games")
    
    print()
    print("Querying Polymarket NFL...")
    poly_nfl = query_polymarket_nfl(target_date, verbose=args.verbose)
    print(f"  Found {len(poly_nfl)} Polymarket NFL games")
    
    print()
    print("Matching NFL games...")
    matched_nfl, kalshi_only_nfl, poly_only_nfl = match_games(kalshi_nfl, poly_nfl, verbose=args.verbose)
    print(f"  Matched: {len(matched_nfl)}")
    
    # Query CFP
    print()
    print("=" * 60)
    print("DISCOVERING CFP GAMES")
    print("=" * 60)
    
    print()
    print("Querying Kalshi CFP...")
    kalshi_cfp = query_kalshi_cfp(target_date, verbose=args.verbose)
    print(f"  Found {len(kalshi_cfp)} Kalshi CFP games")
    
    print()
    print("Querying Polymarket CFP...")
    poly_cfp = query_polymarket_cfp(target_date, verbose=args.verbose)
    print(f"  Found {len(poly_cfp)} Polymarket CFP games")
    
    print()
    print("Matching CFP games...")
    matched_cfp, kalshi_only_cfp, poly_only_cfp = match_games(kalshi_cfp, poly_cfp, verbose=args.verbose)
    print(f"  Matched: {len(matched_cfp)}")
    
    # Print combined results
    print()
    print("=" * 100)
    print(f"COMBINED RESULTS - {target_date}")
    print("=" * 100)
    
    print()
    print(f"✓ MATCHED GAMES ({len(matched_nba) + len(matched_nfl) + len(matched_cfp)} total):")
    print("-" * 100)
    
    if matched_nba:
        print(f"\n  NBA ({len(matched_nba)}):")
        for m in matched_nba:
            k = m['kalshi']
            print(f"    {k['team_a_code']} @ {k['team_b_code']} ({k['event_ticker']})")
    
    if matched_nfl:
        print(f"\n  NFL ({len(matched_nfl)}):")
        for m in matched_nfl:
            k = m['kalshi']
            print(f"    {k['team_a_code']} @ {k['team_b_code']} ({k['event_ticker']})")
    
    if matched_cfp:
        print(f"\n  CFP ({len(matched_cfp)}):")
        for m in matched_cfp:
            k = m['kalshi']
            print(f"    {k['team_a_code']} vs {k['team_b_code']} ({k['event_ticker']})")
    
    if not matched_nba and not matched_nfl and not matched_cfp:
        print("  No matched games found.")
    
    # Unmatched summary
    all_kalshi_only = kalshi_only_nba + kalshi_only_nfl + kalshi_only_cfp
    all_poly_only = poly_only_nba + poly_only_nfl + poly_only_cfp
    
    if all_kalshi_only:
        print(f"\n✗ KALSHI ONLY ({len(all_kalshi_only)}):")
        for game in all_kalshi_only[:5]:  # Show first 5
            print(f"    {game['title']}")
        if len(all_kalshi_only) > 5:
            print(f"    ... and {len(all_kalshi_only) - 5} more")
    
    if all_poly_only:
        print(f"\n✗ POLYMARKET ONLY ({len(all_poly_only)}):")
        for game in all_poly_only[:5]:  # Show first 5
            print(f"    {game['title']}")
        if len(all_poly_only) > 5:
            print(f"    ... and {len(all_poly_only) - 5} more")
    
    print()
    print("=" * 100)
    
    # Build combined markets.json
    total_matched = len(matched_nba) + len(matched_nfl) + len(matched_cfp)
    if total_matched == 0:
        print("No matched games to write.")
        sys.exit(0)
    
    # Build combined config
    markets = []
    
    # Add NBA markets
    if matched_nba:
        nba_config = build_markets_json(matched_nba, target_date, "NBA")
        markets.extend(nba_config['markets'])
    
    # Add NFL markets
    if matched_nfl:
        nfl_config = build_nfl_markets_json(matched_nfl, target_date)
        markets.extend(nfl_config['markets'])
    
    # Add CFP markets
    if matched_cfp:
        cfp_config = build_cfp_markets_json(matched_cfp, target_date)
        markets.extend(cfp_config['markets'])
    
    config = {
        "_comment": f"Active markets for {target_date}",
        "_generated_at": datetime.now(timezone.utc).isoformat(),
        "_note": f"Auto-discovered by market_discovery.py - {len(matched_nba)} NBA, {len(matched_nfl)} NFL, {len(matched_cfp)} CFP",
        "markets": markets
    }
    
    if args.dry_run:
        print()
        print("DRY RUN - Would write:")
        print("-" * 60)
        print(json.dumps(config, indent=2))
        print("-" * 60)
        print("(No changes made)")
    else:
        # Prompt for confirmation unless --yes flag
        if not args.yes:
            print()
            response = input(f"Write {total_matched} markets to markets.json? [y/n]: ").strip().lower()
            if response != 'y':
                print("Aborted.")
                sys.exit(0)
        
        print()
        print("Writing markets.json...")
        success = write_markets_json(config, append=args.append)
        
        if success:
            print()
            print("✓ Done! Restart the bot to use new markets.")
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()

