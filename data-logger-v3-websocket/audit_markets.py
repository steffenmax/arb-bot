#!/usr/bin/env python3
"""
Instrument-Level Market Audit Tool

Comprehensive validation of market mappings and pricing accuracy:
1. Validates token/ticker mappings against live API data
2. Fetches real-time orderbooks from both venues
3. Detects pricing anomalies (crossed books, stale data, out-of-range)
4. Verifies market status (active, closed, restricted)

Usage:
    python3 audit_markets.py                      # Audit all markets
    python3 audit_markets.py --event_id <id>      # Audit specific market
    python3 audit_markets.py --verbose            # Show full orderbook depth
"""

import argparse
import asyncio
import json
import time
import sys
import ssl
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import aiohttp

from team_mappings import (
    LEAGUE_TEAMS, 
    match_outcome_to_team_id, 
    normalize_team_to_code,
    extract_kalshi_team_code
)

# ANSI colors
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
CYAN = '\033[96m'
MAGENTA = '\033[95m'
RESET = '\033[0m'
BOLD = '\033[1m'
DIM = '\033[2m'

# API endpoints
POLYMARKET_GAMMA_API = "https://gamma-api.polymarket.com"
POLYMARKET_CLOB_API = "https://clob.polymarket.com"
KALSHI_API = "https://api.elections.kalshi.com/trade-api/v2"

# Thresholds
STALE_THRESHOLD_SEC = 5.0
MAX_FETCH_AGE_SEC = 10.0


class MarketAuditResult:
    """Container for audit results for a single market"""
    def __init__(self, event_id: str):
        self.event_id = event_id
        self.description = ""
        self.sport = ""
        self.teams = {}  # {team_code: TeamAuditResult}
        self.market_status = {}  # From Polymarket gamma API
        self.errors = []
        self.warnings = []
        self.fetch_timestamp = None


class TeamAuditResult:
    """Container for audit results for a single team within a market"""
    def __init__(self, team_code: str):
        self.team_code = team_code
        self.display_name = ""
        
        # Identifiers
        self.kalshi_ticker = None
        self.poly_token_id = None
        self.poly_condition_id = None
        
        # Mapping validation
        self.mapping_valid = False
        self.mapping_error = None
        self.expected_outcome = None
        self.actual_outcome = None
        
        # Kalshi pricing
        self.kalshi_best_bid = None
        self.kalshi_best_ask = None
        self.kalshi_bid_size = None
        self.kalshi_ask_size = None
        self.kalshi_fetch_time = None
        self.kalshi_stale = True
        self.kalshi_error = None
        
        # Polymarket pricing
        self.poly_best_bid = None
        self.poly_best_ask = None
        self.poly_bid_size = None
        self.poly_ask_size = None
        self.poly_fetch_time = None
        self.poly_stale = True
        self.poly_error = None
        
        # Anomalies
        self.anomalies = []


async def fetch_polymarket_gamma(slug: str, session: aiohttp.ClientSession) -> Optional[Dict]:
    """
    Fetch market data from Polymarket Gamma API
    Returns market metadata including outcomes, clobTokenIds, status
    """
    try:
        url = f"{POLYMARKET_GAMMA_API}/markets?slug={slug}"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            # Gamma returns array of markets
            market = None
            if isinstance(data, list) and len(data) > 0:
                market = data[0]
            else:
                market = data
            
            # Parse outcomes and clobTokenIds if they're JSON strings
            if market:
                outcomes = market.get('outcomes')
                if isinstance(outcomes, str):
                    try:
                        market['outcomes'] = json.loads(outcomes)
                    except:
                        pass
                
                token_ids = market.get('clobTokenIds')
                if isinstance(token_ids, str):
                    try:
                        market['clobTokenIds'] = json.loads(token_ids)
                    except:
                        pass
            
            return market
    except Exception as e:
        print(f"{RED}Error fetching gamma API for {slug}: {e}{RESET}")
        return None


async def fetch_polymarket_book(token_id: str, session: aiohttp.ClientSession) -> Optional[Dict]:
    """
    Fetch orderbook from Polymarket CLOB API
    Returns: {bids: [...], asks: [...], timestamp: ...}
    """
    try:
        url = f"{POLYMARKET_CLOB_API}/book?token_id={token_id}"
        fetch_start = time.time()
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            fetch_time = time.time()
            if resp.status != 200:
                return {'error': f"HTTP {resp.status}", 'fetch_time': fetch_time}
            data = await resp.json()
            data['fetch_time'] = fetch_time
            data['fetch_latency_ms'] = (fetch_time - fetch_start) * 1000
            return data
    except asyncio.TimeoutError:
        return {'error': 'Timeout', 'fetch_time': time.time()}
    except Exception as e:
        return {'error': str(e), 'fetch_time': time.time()}


async def fetch_kalshi_orderbook(ticker: str, session: aiohttp.ClientSession) -> Optional[Dict]:
    """
    Fetch orderbook from Kalshi REST API (public, no auth needed)
    Returns: {orderbook: {yes: [...], no: [...]}, market: {...}}
    """
    try:
        url = f"{KALSHI_API}/markets/{ticker}/orderbook"
        fetch_start = time.time()
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            fetch_time = time.time()
            if resp.status != 200:
                # Try alternate endpoint
                url2 = f"{KALSHI_API}/orderbook/{ticker}"
                async with session.get(url2, timeout=aiohttp.ClientTimeout(total=5)) as resp2:
                    if resp2.status != 200:
                        return {'error': f"HTTP {resp.status}/{resp2.status}", 'fetch_time': fetch_time}
                    data = await resp2.json()
                    data['fetch_time'] = fetch_time
                    return data
            data = await resp.json()
            data['fetch_time'] = fetch_time
            data['fetch_latency_ms'] = (fetch_time - fetch_start) * 1000
            return data
    except asyncio.TimeoutError:
        return {'error': 'Timeout', 'fetch_time': time.time()}
    except Exception as e:
        return {'error': str(e), 'fetch_time': time.time()}


async def fetch_kalshi_market(ticker: str, session: aiohttp.ClientSession) -> Optional[Dict]:
    """
    Fetch market metadata from Kalshi REST API
    """
    try:
        url = f"{KALSHI_API}/markets/{ticker}"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            return data.get('market', data)
    except Exception:
        return None


def parse_kalshi_orderbook(data: Dict) -> Tuple[Optional[float], Optional[float], float, float]:
    """
    Parse Kalshi orderbook response to extract best bid/ask
    
    Kalshi format:
    - 'orderbook': {
        'yes': [[price_cents, qty], ...],  - bids to BUY YES
        'no': [[price_cents, qty], ...],   - bids to BUY NO (converts to asks for YES)
      }
    
    For YES contracts:
    - Best bid = HIGHEST price in 'yes' array
    - Best ask = 1 - HIGHEST price in 'no' array (since NO bid @ X = YES ask @ 1-X)
    
    Returns: (best_bid, best_ask, bid_size, ask_size)
    """
    orderbook = data.get('orderbook', data)
    if not orderbook:
        return None, None, 0, 0
    
    yes_levels = orderbook.get('yes', []) or []
    no_levels = orderbook.get('no', []) or []
    
    # YES levels are bids (people wanting to buy YES)
    # Higher price = better bid for us to sell to
    bids = []
    for level in yes_levels:
        if isinstance(level, list) and len(level) >= 2:
            price = float(level[0])
            qty = float(level[1])
            # Kalshi uses cents (1-99), convert to decimal
            if price >= 1:
                price = price / 100.0
            bids.append((price, qty))
    
    # NO bids convert to YES asks
    # If someone bids $0.82 for NO, they're offering to sell YES at $0.18
    # So YES ask = 1 - NO bid
    # We want the LOWEST ask, which comes from the HIGHEST NO bid
    asks = []
    for level in no_levels:
        if isinstance(level, list) and len(level) >= 2:
            price = float(level[0])
            qty = float(level[1])
            # Convert cents to dollars
            if price >= 1:
                price = price / 100.0
            # YES ask = 1 - NO bid
            yes_ask_price = 1.0 - price
            asks.append((yes_ask_price, qty))
    
    # Sort: bids descending (best = highest), asks ascending (best = lowest)
    bids.sort(key=lambda x: -x[0])
    asks.sort(key=lambda x: x[0])
    
    # Best bid = highest in YES bids
    best_bid = bids[0][0] if bids else None
    bid_size = bids[0][1] if bids else 0
    
    # Best ask = lowest in converted NO bids = 1 - max(NO bids)
    best_ask = asks[0][0] if asks else None
    ask_size = asks[0][1] if asks else 0
    
    return best_bid, best_ask, bid_size, ask_size


def parse_polymarket_orderbook(data: Dict) -> Tuple[Optional[float], Optional[float], float, float]:
    """
    Parse Polymarket orderbook response
    
    Format: {bids: [{price, size}, ...], asks: [{price, size}, ...]}
    
    Returns: (best_bid, best_ask, bid_size, ask_size)
    """
    if 'error' in data:
        return None, None, 0, 0
    
    bids_raw = data.get('bids', [])
    asks_raw = data.get('asks', [])
    
    bids = []
    for b in bids_raw:
        if isinstance(b, dict):
            price = float(b.get('price', 0))
            size = float(b.get('size', 0))
            if price > 0:
                bids.append((price, size))
    
    asks = []
    for a in asks_raw:
        if isinstance(a, dict):
            price = float(a.get('price', 0))
            size = float(a.get('size', 0))
            if price > 0:
                asks.append((price, size))
    
    bids.sort(key=lambda x: -x[0])
    asks.sort(key=lambda x: x[0])
    
    best_bid = bids[0][0] if bids else None
    best_ask = asks[0][0] if asks else None
    bid_size = bids[0][1] if bids else 0
    ask_size = asks[0][1] if asks else 0
    
    return best_bid, best_ask, bid_size, ask_size


def detect_anomalies(team_result: TeamAuditResult) -> List[str]:
    """
    Detect pricing anomalies for a team's orderbook
    """
    anomalies = []
    
    # Check Kalshi anomalies
    if team_result.kalshi_best_bid is not None and team_result.kalshi_best_ask is not None:
        if team_result.kalshi_best_bid > team_result.kalshi_best_ask:
            anomalies.append(f"KALSHI CROSSED: bid {team_result.kalshi_best_bid:.3f} > ask {team_result.kalshi_best_ask:.3f}")
        
        if team_result.kalshi_best_bid < 0 or team_result.kalshi_best_bid > 1:
            anomalies.append(f"KALSHI BID OUT OF RANGE: {team_result.kalshi_best_bid:.3f}")
        
        if team_result.kalshi_best_ask < 0 or team_result.kalshi_best_ask > 1:
            anomalies.append(f"KALSHI ASK OUT OF RANGE: {team_result.kalshi_best_ask:.3f}")
    
    # Check Polymarket anomalies
    if team_result.poly_best_bid is not None and team_result.poly_best_ask is not None:
        if team_result.poly_best_bid > team_result.poly_best_ask:
            anomalies.append(f"POLY CROSSED: bid {team_result.poly_best_bid:.3f} > ask {team_result.poly_best_ask:.3f}")
        
        if team_result.poly_best_bid < 0 or team_result.poly_best_bid > 1:
            anomalies.append(f"POLY BID OUT OF RANGE: {team_result.poly_best_bid:.3f}")
        
        if team_result.poly_best_ask < 0 or team_result.poly_best_ask > 1:
            anomalies.append(f"POLY ASK OUT OF RANGE: {team_result.poly_best_ask:.3f}")
    
    return anomalies


async def audit_single_market(market_config: Dict, session: aiohttp.ClientSession, 
                               verbose: bool = False) -> MarketAuditResult:
    """
    Perform comprehensive audit for a single market
    """
    event_id = market_config['event_id']
    result = MarketAuditResult(event_id)
    result.description = market_config.get('description', '')
    result.sport = market_config.get('sport', 'NFL')
    result.fetch_timestamp = datetime.now()
    
    # Get Polymarket slug
    poly_config = market_config.get('polymarket', {})
    poly_slug = poly_config.get('markets', {}).get('slug') if isinstance(poly_config, dict) else None
    
    # Fetch Polymarket gamma data for market status and outcome validation
    gamma_data = None
    if poly_slug:
        gamma_data = await fetch_polymarket_gamma(poly_slug, session)
        if gamma_data:
            result.market_status = {
                'active': gamma_data.get('active'),
                'closed': gamma_data.get('closed'),
                'accepting_orders': gamma_data.get('acceptingOrders'),
                'restricted': gamma_data.get('restricted'),
                'end_date': gamma_data.get('endDate'),
                'resolved': gamma_data.get('resolved'),
                'resolution': gamma_data.get('resolution'),
                'outcomes': gamma_data.get('outcomes', []),
                'clob_token_ids': gamma_data.get('clobTokenIds', [])
            }
    
    # Get Kalshi tickers
    kalshi_config = market_config.get('kalshi', {})
    kalshi_tickers = []
    if kalshi_config.get('enabled') and 'markets' in kalshi_config:
        if 'main' in kalshi_config['markets']:
            kalshi_tickers.append(('main', kalshi_config['markets']['main']))
        if 'opponent' in kalshi_config['markets']:
            kalshi_tickers.append(('opponent', kalshi_config['markets']['opponent']))
    
    # Get Polymarket token IDs
    poly_token_ids = market_config.get('poly_token_ids', {})
    
    # Build team audit results
    teams_info = market_config.get('teams', {})
    team_a = teams_info.get('team_a', '')
    team_b = teams_info.get('team_b', '')
    home_team = market_config.get('home_team', '')
    away_team = market_config.get('away_team', '')
    
    # Determine which teams we're auditing
    teams_to_audit = set()
    
    # From Kalshi tickers
    for label, ticker in kalshi_tickers:
        team_code = extract_kalshi_team_code(ticker, result.sport)
        if team_code:
            teams_to_audit.add(team_code)
    
    # From Polymarket token IDs
    for team_code in poly_token_ids.keys():
        teams_to_audit.add(team_code)
    
    # If no teams found, try to infer from team_a/team_b
    if not teams_to_audit:
        if home_team:
            teams_to_audit.add(home_team)
        if away_team:
            teams_to_audit.add(away_team)
        # Try to normalize team_a/team_b
        if team_a:
            code = normalize_team_to_code(team_a, result.sport)
            if code:
                teams_to_audit.add(code)
        if team_b:
            code = normalize_team_to_code(team_b, result.sport)
            if code:
                teams_to_audit.add(code)
    
    # Audit each team
    for team_code in teams_to_audit:
        team_result = TeamAuditResult(team_code)
        
        # Get display name
        league_teams = LEAGUE_TEAMS.get(result.sport, {})
        if team_code in league_teams:
            team_info = league_teams[team_code]
            team_result.display_name = f"{team_info['city']} {team_info['nickname']}"
        else:
            team_result.display_name = team_code
        
        # Find Kalshi ticker for this team
        for label, ticker in kalshi_tickers:
            ticker_team = extract_kalshi_team_code(ticker, result.sport)
            if ticker_team == team_code:
                team_result.kalshi_ticker = ticker
                break
        
        # Find Polymarket token for this team
        team_result.poly_token_id = poly_token_ids.get(team_code)
        team_result.poly_condition_id = market_config.get('poly_condition_id', '')
        
        # Validate Polymarket mapping against gamma data
        if gamma_data and team_result.poly_token_id:
            outcomes = gamma_data.get('outcomes', [])
            clob_token_ids = gamma_data.get('clobTokenIds', [])
            
            # Find which outcome corresponds to this token
            if len(outcomes) == len(clob_token_ids):
                for i, tid in enumerate(clob_token_ids):
                    if str(tid) == str(team_result.poly_token_id):
                        actual_outcome = outcomes[i]
                        team_result.actual_outcome = actual_outcome
                        
                        # Validate that outcome normalizes to the expected team_code
                        inferred_code = match_outcome_to_team_id(actual_outcome, result.sport)
                        
                        if inferred_code == team_code:
                            team_result.mapping_valid = True
                            team_result.expected_outcome = actual_outcome
                        else:
                            team_result.mapping_valid = False
                            team_result.mapping_error = f"Expected {team_code}, got {inferred_code} from outcome '{actual_outcome}'"
                        break
                else:
                    team_result.mapping_error = f"Token ID not found in gamma clobTokenIds"
        
        # Fetch Kalshi orderbook
        if team_result.kalshi_ticker:
            kalshi_data = await fetch_kalshi_orderbook(team_result.kalshi_ticker, session)
            if kalshi_data and 'error' not in kalshi_data:
                bid, ask, bid_sz, ask_sz = parse_kalshi_orderbook(kalshi_data)
                team_result.kalshi_best_bid = bid
                team_result.kalshi_best_ask = ask
                team_result.kalshi_bid_size = bid_sz
                team_result.kalshi_ask_size = ask_sz
                team_result.kalshi_fetch_time = kalshi_data.get('fetch_time', time.time())
                team_result.kalshi_stale = (time.time() - team_result.kalshi_fetch_time) > STALE_THRESHOLD_SEC
            else:
                team_result.kalshi_error = kalshi_data.get('error', 'Unknown error') if kalshi_data else 'No response'
        
        # Fetch Polymarket orderbook
        if team_result.poly_token_id:
            poly_data = await fetch_polymarket_book(team_result.poly_token_id, session)
            if poly_data and 'error' not in poly_data:
                bid, ask, bid_sz, ask_sz = parse_polymarket_orderbook(poly_data)
                team_result.poly_best_bid = bid
                team_result.poly_best_ask = ask
                team_result.poly_bid_size = bid_sz
                team_result.poly_ask_size = ask_sz
                team_result.poly_fetch_time = poly_data.get('fetch_time', time.time())
                team_result.poly_stale = (time.time() - team_result.poly_fetch_time) > STALE_THRESHOLD_SEC
            else:
                team_result.poly_error = poly_data.get('error', 'Unknown error') if poly_data else 'No response'
        
        # Detect anomalies
        team_result.anomalies = detect_anomalies(team_result)
        
        result.teams[team_code] = team_result
    
    return result


def print_audit_result(result: MarketAuditResult, verbose: bool = False):
    """
    Print formatted audit result for a market
    """
    print(f"\n{'='*100}")
    print(f"{BOLD}{CYAN}AUDIT: {result.event_id}{RESET}")
    print(f"{DIM}Description: {result.description}{RESET}")
    print(f"{DIM}Sport: {result.sport} | Fetched: {result.fetch_timestamp.strftime('%H:%M:%S')}{RESET}")
    print(f"{'='*100}")
    
    # Market status
    status = result.market_status
    if status:
        active = status.get('active', False)
        closed = status.get('closed', False)
        resolved = status.get('resolved', False)
        restricted = status.get('restricted', False)
        accepting = status.get('accepting_orders', False)
        
        status_str = []
        if closed or resolved:
            status_str.append(f"{RED}CLOSED/RESOLVED{RESET}")
        elif restricted:
            status_str.append(f"{YELLOW}RESTRICTED{RESET}")
        elif not active:
            status_str.append(f"{YELLOW}INACTIVE{RESET}")
        elif accepting:
            status_str.append(f"{GREEN}ACCEPTING ORDERS{RESET}")
        else:
            status_str.append(f"{YELLOW}NOT ACCEPTING{RESET}")
        
        resolution = status.get('resolution')
        if resolution:
            status_str.append(f"Resolution: {resolution}")
        
        end_date = status.get('end_date')
        if end_date:
            status_str.append(f"End: {end_date}")
        
        print(f"\n{BOLD}MARKET STATUS:{RESET} {' | '.join(status_str)}")
        
        if status.get('outcomes') and status.get('clob_token_ids'):
            print(f"{DIM}Gamma Outcomes: {status['outcomes']}{RESET}")
            print(f"{DIM}Gamma Token IDs: {[str(t)[:20] + '...' for t in status['clob_token_ids']]}{RESET}")
    
    # Team-by-team audit
    print(f"\n{BOLD}TEAM-BY-TEAM AUDIT:{RESET}")
    print(f"{'-'*100}")
    
    for team_code, team in sorted(result.teams.items()):
        print(f"\n{BOLD}{team.display_name} ({team_code}){RESET}")
        
        # Identifiers
        print(f"  {DIM}Kalshi Ticker:{RESET} {team.kalshi_ticker or 'N/A'}")
        print(f"  {DIM}Poly Token ID:{RESET} {str(team.poly_token_id)[:40] + '...' if team.poly_token_id else 'N/A'}")
        print(f"  {DIM}Poly Condition:{RESET} {team.poly_condition_id or 'N/A'}")
        
        # Mapping validation
        if team.poly_token_id:
            if team.mapping_valid:
                print(f"  {GREEN}✓ MAPPING VALID{RESET} - Outcome: '{team.actual_outcome}'")
            elif team.mapping_error:
                print(f"  {RED}✗ MAPPING ERROR: {team.mapping_error}{RESET}")
            else:
                print(f"  {YELLOW}⚠ MAPPING NOT VERIFIED{RESET}")
        
        # Kalshi pricing
        print(f"\n  {BOLD}KALSHI:{RESET}")
        if team.kalshi_error:
            print(f"    {RED}ERROR: {team.kalshi_error}{RESET}")
        elif team.kalshi_best_bid is not None or team.kalshi_best_ask is not None:
            bid_str = f"{team.kalshi_best_bid:.3f}" if team.kalshi_best_bid else "---"
            ask_str = f"{team.kalshi_best_ask:.3f}" if team.kalshi_best_ask else "---"
            bid_sz = f"{team.kalshi_bid_size:.0f}" if team.kalshi_bid_size else "---"
            ask_sz = f"{team.kalshi_ask_size:.0f}" if team.kalshi_ask_size else "---"
            
            stale_str = f"{RED}STALE{RESET}" if team.kalshi_stale else f"{GREEN}FRESH{RESET}"
            age = time.time() - team.kalshi_fetch_time if team.kalshi_fetch_time else 0
            
            print(f"    Bid: {CYAN}{bid_str}{RESET} × {bid_sz} | Ask: {CYAN}{ask_str}{RESET} × {ask_sz} | {stale_str} ({age:.1f}s)")
        else:
            print(f"    {YELLOW}No orderbook data{RESET}")
        
        # Polymarket pricing
        print(f"\n  {BOLD}POLYMARKET:{RESET}")
        if team.poly_error:
            print(f"    {RED}ERROR: {team.poly_error}{RESET}")
        elif team.poly_best_bid is not None or team.poly_best_ask is not None:
            bid_str = f"{team.poly_best_bid:.3f}" if team.poly_best_bid else "---"
            ask_str = f"{team.poly_best_ask:.3f}" if team.poly_best_ask else "---"
            bid_sz = f"{team.poly_bid_size:.0f}" if team.poly_bid_size else "---"
            ask_sz = f"{team.poly_ask_size:.0f}" if team.poly_ask_size else "---"
            
            stale_str = f"{RED}STALE{RESET}" if team.poly_stale else f"{GREEN}FRESH{RESET}"
            age = time.time() - team.poly_fetch_time if team.poly_fetch_time else 0
            
            print(f"    Bid: {CYAN}{bid_str}{RESET} × {bid_sz} | Ask: {CYAN}{ask_str}{RESET} × {ask_sz} | {stale_str} ({age:.1f}s)")
        else:
            print(f"    {YELLOW}No orderbook data{RESET}")
        
        # Anomalies
        if team.anomalies:
            print(f"\n  {RED}ANOMALIES:{RESET}")
            for anomaly in team.anomalies:
                print(f"    {RED}⚠ {anomaly}{RESET}")
        
        # Cross-venue comparison
        if (team.kalshi_best_bid is not None and team.poly_best_bid is not None):
            k_mid = (team.kalshi_best_bid + team.kalshi_best_ask) / 2 if team.kalshi_best_ask else team.kalshi_best_bid
            p_mid = (team.poly_best_bid + team.poly_best_ask) / 2 if team.poly_best_ask else team.poly_best_bid
            diff = abs(k_mid - p_mid) * 100
            diff_color = RED if diff > 5 else YELLOW if diff > 2 else GREEN
            print(f"\n  {BOLD}CROSS-VENUE:{RESET} Kalshi mid={k_mid:.3f}, Poly mid={p_mid:.3f}, Diff={diff_color}{diff:.1f}%{RESET}")


async def load_markets_config() -> List[Dict]:
    """Load markets from config file"""
    config_path = Path("config/markets.json")
    if not config_path.exists():
        print(f"{RED}Config file not found: {config_path}{RESET}")
        return []
    
    with open(config_path) as f:
        data = json.load(f)
        return data.get('markets', [])


async def main():
    parser = argparse.ArgumentParser(description='Instrument-Level Market Audit Tool')
    parser.add_argument('--event_id', type=str, help='Audit only this specific event')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show verbose output')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    args = parser.parse_args()
    
    print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{CYAN}  INSTRUMENT-LEVEL MARKET AUDIT{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}\n")
    
    # Load markets
    markets = await load_markets_config()
    if not markets:
        print(f"{RED}No markets found in config{RESET}")
        return
    
    # Filter if event_id specified
    if args.event_id:
        markets = [m for m in markets if m['event_id'] == args.event_id]
        if not markets:
            print(f"{RED}No market found with event_id: {args.event_id}{RESET}")
            return
    
    print(f"Auditing {len(markets)} market(s)...\n")
    
    # Create SSL context that doesn't verify certs (for macOS compatibility)
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    
    connector = aiohttp.TCPConnector(ssl=ssl_ctx)
    
    # Run audits
    results = []
    async with aiohttp.ClientSession(connector=connector) as session:
        for market in markets:
            result = await audit_single_market(market, session, args.verbose)
            results.append(result)
            
            if not args.json:
                print_audit_result(result, args.verbose)
    
    # Save market status cache (always, for dashboard consumption)
    await save_market_status_cache(results)
    
    # Summary
    if not args.json and len(results) > 1:
        print(f"\n{'='*100}")
        print(f"{BOLD}SUMMARY{RESET}")
        print(f"{'='*100}")
        
        total_teams = sum(len(r.teams) for r in results)
        mapping_errors = sum(1 for r in results for t in r.teams.values() if t.mapping_error)
        pricing_errors = sum(1 for r in results for t in r.teams.values() if t.kalshi_error or t.poly_error)
        anomalies = sum(len(t.anomalies) for r in results for t in r.teams.values())
        closed_markets = sum(1 for r in results if r.market_status.get('closed') or r.market_status.get('resolved'))
        
        print(f"  Markets audited: {len(results)}")
        print(f"  Teams audited: {total_teams}")
        print(f"  Mapping errors: {RED if mapping_errors else GREEN}{mapping_errors}{RESET}")
        print(f"  Pricing errors: {RED if pricing_errors else GREEN}{pricing_errors}{RESET}")
        print(f"  Anomalies detected: {RED if anomalies else GREEN}{anomalies}{RESET}")
        print(f"  Closed/Resolved markets: {YELLOW if closed_markets else GREEN}{closed_markets}{RESET}")
        
        print(f"\n{DIM}Audit completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}\n")
    
    if args.json:
        # Output as JSON
        output = []
        for r in results:
            market_data = {
                'event_id': r.event_id,
                'description': r.description,
                'sport': r.sport,
                'fetch_timestamp': r.fetch_timestamp.isoformat(),
                'market_status': r.market_status,
                'teams': {}
            }
            for tc, t in r.teams.items():
                market_data['teams'][tc] = {
                    'display_name': t.display_name,
                    'kalshi_ticker': t.kalshi_ticker,
                    'poly_token_id': t.poly_token_id,
                    'mapping_valid': t.mapping_valid,
                    'mapping_error': t.mapping_error,
                    'kalshi': {
                        'best_bid': t.kalshi_best_bid,
                        'best_ask': t.kalshi_best_ask,
                        'bid_size': t.kalshi_bid_size,
                        'ask_size': t.kalshi_ask_size,
                        'stale': t.kalshi_stale,
                        'error': t.kalshi_error
                    },
                    'polymarket': {
                        'best_bid': t.poly_best_bid,
                        'best_ask': t.poly_best_ask,
                        'bid_size': t.poly_bid_size,
                        'ask_size': t.poly_ask_size,
                        'stale': t.poly_stale,
                        'error': t.poly_error
                    },
                    'anomalies': t.anomalies
                }
            output.append(market_data)
        
        print(json.dumps(output, indent=2, default=str))


async def save_market_status_cache(results: List[MarketAuditResult]):
    """Save market status cache for dashboard consumption"""
    cache_path = Path("data/market_status_cache.json")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    
    cache_data = {
        'updated_at': datetime.now().isoformat(),
        'markets': {}
    }
    
    for r in results:
        market_data = {
            'description': r.description,
            'sport': r.sport,
            'status': r.market_status,
            'teams': {}
        }
        
        for tc, t in r.teams.items():
            market_data['teams'][tc] = {
                'display_name': t.display_name,
                'mapping_valid': t.mapping_valid,
                'mapping_error': t.mapping_error,
                'has_kalshi': t.kalshi_ticker is not None,
                'has_poly': t.poly_token_id is not None,
                'anomalies': t.anomalies
            }
        
        # Determine if market is tradeable
        status = r.market_status
        is_closed = status.get('closed', False) or status.get('resolved', False)
        is_restricted = status.get('restricted', False)
        is_active = status.get('active', True) and not is_closed
        
        market_data['is_tradeable'] = is_active and not is_restricted and not is_closed
        market_data['status_label'] = 'CLOSED' if is_closed else 'RESTRICTED' if is_restricted else 'ACTIVE'
        
        cache_data['markets'][r.event_id] = market_data
    
    with open(cache_path, 'w') as f:
        json.dump(cache_data, f, indent=2, default=str)
    
    print(f"\n{GREEN}✓ Saved market status cache to {cache_path}{RESET}")


if __name__ == "__main__":
    asyncio.run(main())

