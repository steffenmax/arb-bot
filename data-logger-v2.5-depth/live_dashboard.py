#!/usr/bin/env python3
"""
Live Trading Dashboard
Shows real-time market data in an Excel-style table format with:
- Latest ask prices from both platforms
- Top-of-book volumes
- Best arbitrage opportunities
- Green highlighting for profitable combinations (<1.0 total)
"""

import sqlite3
import json
import time
import sys
import csv
from datetime import datetime, timedelta
from pathlib import Path
from arb_calculator import ArbCalculator

# Configuration
DB_PATH = "data/market_data.db"
CONFIG_PATH = "config/markets.json"
CSV_OUTPUT = "data/live_dashboard.csv"
ARB_LOG_CSV = "data/arb_opportunities.csv"
REFRESH_INTERVAL = 1  # seconds
MAX_DATA_AGE = 10  # Only show data from last 10 seconds

# Global tracking for active arbitrage opportunities
ACTIVE_ARBS = {}  # Key: event_id, Value: {start_time, details}

# Initialize arbitrage calculator with accurate fee model
ARB_CALC = ArbCalculator(
    kalshi_taker_rate=0.07,
    kalshi_maker_rate=0.0175,
    polymarket_fee_rate=0.0,
    gas_cost_usd=0.0,
    min_roi_pct=1.0,  # Minimum 1% net ROI
    min_profit_usd=3.0  # Minimum $3 net profit
)

# ANSI color codes for terminal
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'
CLEAR_SCREEN = '\033[2J\033[H'

# NFL Team name mapping (Kalshi city names -> Polymarket nicknames)
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

# Reverse mapping (Polymarket -> Kalshi)
POLY_TO_KALSHI = {v: k for k, v in NFL_TEAM_MAP.items()}

# NBA Team name mapping (Kalshi city names -> Polymarket nicknames)
NBA_TEAM_MAP = {
    'Atlanta': 'Hawks',
    'Boston': 'Celtics',
    'Brooklyn': 'Nets',
    'Charlotte': 'Hornets',
    'Chicago': 'Bulls',
    'Cleveland': 'Cavaliers',
    'Dallas': 'Mavericks',
    'Denver': 'Nuggets',
    'Detroit': 'Pistons',
    'Golden State': 'Warriors',
    'Houston': 'Rockets',
    'Indiana': 'Pacers',
    'Los Angeles C': 'Clippers',
    'Los Angeles L': 'Lakers',
    'Memphis': 'Grizzlies',
    'Miami': 'Heat',
    'Milwaukee': 'Bucks',
    'Minnesota': 'Timberwolves',
    'New Orleans': 'Pelicans',
    'New York': 'Knicks',
    'Oklahoma City': 'Thunder',
    'Orlando': 'Magic',
    'Philadelphia': '76ers',
    'Phoenix': 'Suns',
    'Portland': 'Trail Blazers',
    'Sacramento': 'Kings',
    'San Antonio': 'Spurs',
    'Toronto': 'Raptors',
    'Utah': 'Jazz',
    'Washington': 'Wizards'
}

# Reverse mapping for NBA (Polymarket -> Kalshi)
NBA_POLY_TO_KALSHI = {v: k for k, v in NBA_TEAM_MAP.items()}

def load_markets_config():
    """Load markets configuration"""
    with open(CONFIG_PATH, 'r') as f:
        data = json.load(f)
        return {m['event_id']: m for m in data.get('markets', [])}

def get_terminal_width():
    """Get terminal width for formatting"""
    try:
        import os
        return os.get_terminal_size().columns
    except:
        return 200  # Default width

def format_price(price):
    """Format price with color"""
    if price is None:
        return "   -   "
    return f"{price:.3f}"

def format_volume(volume):
    """Format volume - handles large liquidity numbers"""
    if volume is None or volume == 0:
        return "   -   "
    
    # For very large numbers (millions), show as millions
    if volume >= 1000000:
        return f"{volume/1000000:.1f}M"
    # For thousands, show as k
    elif volume >= 1000:
        return f"{volume/1000:.1f}k"
    else:
        return f"{volume:.0f}"

def get_latest_market_data(conn, event_id, max_age_seconds=MAX_DATA_AGE):
    """
    Get latest prices and volumes for a game
    Returns dict with both platforms' data
    """
    cutoff = (datetime.now() - timedelta(seconds=max_age_seconds)).isoformat()
    
    cursor = conn.execute("""
        SELECT platform, market_side, yes_ask, yes_bid, timestamp, id
        FROM price_snapshots
        WHERE event_id = ?
        AND timestamp > ?
        ORDER BY timestamp DESC
    """, (event_id, cutoff))
    
    rows = cursor.fetchall()
    
    data = {
        'kalshi': {},
        'polymarket': {},
        'timestamp': None
    }
    
    for row in rows:
        platform = row[0]
        team = row[1]
        ask = row[2]
        bid = row[3]
        timestamp = row[4]
        snapshot_id = row[5]
        
        # Update timestamp
        if data['timestamp'] is None or timestamp > data['timestamp']:
            data['timestamp'] = timestamp
        
        # Store price if we don't have this team yet
        if team not in data[platform]:
            # Get total market liquidity from price snapshot (consistent across platforms)
            # This shows total market depth rather than just top-of-book volume
            liquidity_cursor = conn.execute("""
                SELECT liquidity, volume
                FROM price_snapshots
                WHERE id = ?
            """, (snapshot_id,))
            liq_row = liquidity_cursor.fetchone()
            
            # Use total market liquidity if available (preferred metric)
            if liq_row and liq_row[0]:
                # Liquidity is stored in cents, convert to dollars for display
                volume = liq_row[0] / 100.0 if liq_row[0] else 0
            elif liq_row and liq_row[1]:
                # Fall back to volume field
                volume = liq_row[1]
            else:
                # No data available
                volume = 0
            
            data[platform][team] = {
                'ask': ask,
                'bid': bid,
                'volume': volume,  # Actually total market liquidity
                'timestamp': timestamp
            }
    
    return data

def normalize_team_name(name, to_polymarket=True, sport=None):
    """Convert between Kalshi city names and Polymarket nicknames
    
    Args:
        name: Team name to convert
        to_polymarket: If True, convert from Kalshi to Polymarket; if False, reverse
        sport: 'NFL' or 'NBA' (if None, tries both)
    """
    if to_polymarket:
        # Kalshi -> Polymarket
        if sport == 'NBA':
            return NBA_TEAM_MAP.get(name, name)
        elif sport == 'NFL':
            return NFL_TEAM_MAP.get(name, name)
        else:
            # Try both mappings
            return NBA_TEAM_MAP.get(name, NFL_TEAM_MAP.get(name, name))
    else:
        # Polymarket -> Kalshi
        if sport == 'NBA':
            return NBA_POLY_TO_KALSHI.get(name, name)
        elif sport == 'NFL':
            return POLY_TO_KALSHI.get(name, name)
        else:
            # Try both mappings
            return NBA_POLY_TO_KALSHI.get(name, POLY_TO_KALSHI.get(name, name))

def calculate_arbitrage(kalshi_data, poly_data, team_a, team_b, sport='NFL'):
    """
    Calculate best arbitrage opportunity with accurate fee model
    Returns: dict with gross and net profit calculations
    """
    opportunities = []
    
    # Try to match teams (Kalshi uses city names, Polymarket uses nicknames)
    kalshi_a = kalshi_data.get(team_a)
    kalshi_b = kalshi_data.get(team_b)
    
    # Convert team names to Polymarket format for matching
    poly_team_a = normalize_team_name(team_a, to_polymarket=True, sport=sport)
    poly_team_b = normalize_team_name(team_b, to_polymarket=True, sport=sport)
    
    poly_a = poly_data.get(poly_team_a)
    poly_b = poly_data.get(poly_team_b)
    
    # Combination 1: Kalshi A + Poly B
    if kalshi_a and poly_b and kalshi_a['ask'] and poly_b['ask']:
        kalshi_price = kalshi_a['ask']
        poly_price = poly_b['ask']
        total = kalshi_price + poly_price
        
        # Calculate net profit with accurate fees (try multiple quantities)
        best_net_result = None
        for quantity in [50, 100, 250, 500]:
            net_result = ARB_CALC.calculate_net_profit(quantity, kalshi_price, poly_price)
            if (net_result['net_profit'] >= ARB_CALC.min_profit_usd and 
                net_result['roi_pct'] >= ARB_CALC.min_roi_pct):
                if not best_net_result or net_result['net_profit'] > best_net_result['net_profit']:
                    best_net_result = net_result
        
        opportunities.append({
            'total': total,
            'kalshi_team': team_a,
            'kalshi_ask': kalshi_price,
            'poly_team': team_b,
            'poly_ask': poly_price,
            'combo': f"K:{team_a[:3]} + P:{team_b[:3]}",
            'net_result': best_net_result
        })
    
    # Combination 2: Kalshi B + Poly A
    if kalshi_b and poly_a and kalshi_b['ask'] and poly_a['ask']:
        kalshi_price = kalshi_b['ask']
        poly_price = poly_a['ask']
        total = kalshi_price + poly_price
        
        # Calculate net profit with accurate fees
        best_net_result = None
        for quantity in [50, 100, 250, 500]:
            net_result = ARB_CALC.calculate_net_profit(quantity, kalshi_price, poly_price)
            if (net_result['net_profit'] >= ARB_CALC.min_profit_usd and 
                net_result['roi_pct'] >= ARB_CALC.min_roi_pct):
                if not best_net_result or net_result['net_profit'] > best_net_result['net_profit']:
                    best_net_result = net_result
        
        opportunities.append({
            'total': total,
            'kalshi_team': team_b,
            'kalshi_ask': kalshi_price,
            'poly_team': team_a,
            'poly_ask': poly_a['ask'],
            'combo': f"K:{team_b[:3]} + P:{team_a[:3]}",
            'net_result': best_net_result
        })
    
    # Return best opportunity (by net profit, not just lowest total)
    if opportunities:
        # Filter to only profitable opportunities
        profitable = [opp for opp in opportunities if opp['net_result'] is not None]
        if profitable:
            return max(profitable, key=lambda x: x['net_result']['net_profit'])
        else:
            # No profitable opportunities, return best gross
            return min(opportunities, key=lambda x: x['total'])
    
    return None

def initialize_arb_log():
    """Initialize the arbitrage opportunity log CSV"""
    import os
    if not os.path.exists(ARB_LOG_CSV):
        with open(ARB_LOG_CSV, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Detected At', 'Closed At', 'Duration (sec)',
                'Game', 'Team A', 'Team B',
                'Kalshi Ask', 'Kalshi Team', 'Kalshi Vol',
                'Poly Ask', 'Poly Team', 'Poly Vol',
                'Combo Used', 'Total Cost', 'Gross %',
                'Opt Qty', 'Kalshi Fee', 'Net Profit', 'Net ROI %'
            ])

def cleanup_old_market_data(retention_days=7):
    """
    Clean up old market data from database (price_snapshots, orderbook_snapshots)
    Keeps arbitrage opportunity logs - those are valuable!
    """
    cutoff_date = (datetime.now() - timedelta(days=retention_days)).isoformat()
    
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()
    
    # Count before deletion
    cursor.execute("SELECT COUNT(*) FROM price_snapshots WHERE timestamp < ?", (cutoff_date,))
    old_prices = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM orderbook_snapshots WHERE timestamp < ?", (cutoff_date,))
    old_orderbooks = cursor.fetchone()[0]
    
    # Delete old data
    if old_prices > 0:
        cursor.execute("DELETE FROM price_snapshots WHERE timestamp < ?", (cutoff_date,))
    
    if old_orderbooks > 0:
        cursor.execute("DELETE FROM orderbook_snapshots WHERE timestamp < ?", (cutoff_date,))
    
    conn.commit()
    
    # Vacuum to reclaim disk space
    if old_prices > 0 or old_orderbooks > 0:
        cursor.execute("VACUUM")
    
    conn.close()
    
    return old_prices, old_orderbooks

def log_arb_opportunity(opportunity):
    """Append a completed arbitrage opportunity to the log with net profit calc"""
    with open(ARB_LOG_CSV, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            opportunity['start_time'],
            opportunity['end_time'],
            opportunity['duration_sec'],
            opportunity['game'],
            opportunity['team_a'],
            opportunity['team_b'],
            opportunity['kalshi_ask'],
            opportunity['kalshi_team'],
            opportunity['kalshi_vol'],
            opportunity['poly_ask'],
            opportunity['poly_team'],
            opportunity['poly_vol'],
            opportunity['combo'],
            opportunity['total_cost'],
            opportunity['gross_profit_pct'],
            opportunity.get('opt_qty', ''),
            opportunity.get('kalshi_fee', ''),
            opportunity.get('net_profit', ''),
            opportunity.get('net_roi', '')
        ])

def track_arbitrage_opportunities(event_id, arb_data, game_info):
    """
    Track arbitrage opportunities - detect starts and ends
    arb_data: dict with arbitrage details or None
    game_info: dict with game description and teams
    """
    global ACTIVE_ARBS
    
    # Check if opportunity is net profitable (not just gross < 1.0)
    is_profitable = arb_data and arb_data.get('net_result') is not None
    
    if is_profitable:
        # Arbitrage opportunity exists (net profitable)
        if event_id not in ACTIVE_ARBS:
            # New opportunity detected
            net_result = arb_data['net_result']
            ACTIVE_ARBS[event_id] = {
                'start_time': datetime.now().isoformat(),
                'game': game_info['description'],
                'team_a': game_info['team_a'],
                'team_b': game_info['team_b'],
                'kalshi_ask': arb_data['kalshi_ask'],
                'kalshi_team': arb_data['kalshi_team'],
                'kalshi_vol': game_info.get('kalshi_vol', 0),
                'poly_ask': arb_data['poly_ask'],
                'poly_team': arb_data['poly_team'],
                'poly_vol': game_info.get('poly_vol', 0),
                'combo': arb_data['combo'],
                'total_cost': arb_data['total'],
                'gross_profit_pct': ((1.0 - arb_data['total']) / arb_data['total']) * 100,
                'opt_qty': net_result['quantity'],
                'kalshi_fee': net_result['kalshi_fee'],
                'net_profit': net_result['net_profit'],
                'net_roi': net_result['roi_pct']
            }
    else:
        # No arbitrage (or arb >= 1.0)
        if event_id in ACTIVE_ARBS:
            # Opportunity closed - log it
            opp = ACTIVE_ARBS[event_id]
            start = datetime.fromisoformat(opp['start_time'])
            end = datetime.now()
            duration = (end - start).total_seconds()
            
            completed_opp = {
                'start_time': opp['start_time'],
                'end_time': end.isoformat(),
                'duration_sec': f"{duration:.1f}",
                'game': opp['game'],
                'team_a': opp['team_a'],
                'team_b': opp['team_b'],
                'kalshi_ask': f"{opp['kalshi_ask']:.3f}",
                'kalshi_team': opp['kalshi_team'],
                'kalshi_vol': format_volume(opp['kalshi_vol']),
                'poly_ask': f"{opp['poly_ask']:.3f}",
                'poly_team': opp['poly_team'],
                'poly_vol': format_volume(opp['poly_vol']),
                'combo': opp['combo'],
                'total_cost': f"{opp['total_cost']:.4f}",
                'gross_profit_pct': f"{opp['gross_profit_pct']:.2f}%",
                'opt_qty': f"{opp['opt_qty']:.0f}",
                'kalshi_fee': f"${opp['kalshi_fee']:.2f}",
                'net_profit': f"${opp['net_profit']:.2f}",
                'net_roi': f"{opp['net_roi']:.2f}%"
            }
            
            log_arb_opportunity(completed_opp)
            del ACTIVE_ARBS[event_id]

def display_dashboard(markets_config, conn):
    """Display the live dashboard"""
    
    # Prepare data rows
    rows = []
    csv_rows = []
    
    # CSV Header
    csv_rows.append([
        'Game', 'Team A', 'Team B',
        'Kalshi A Ask', 'Kalshi A Liq', 
        'Kalshi B Ask', 'Kalshi B Liq',
        'Poly A Ask', 'Poly A Liq',
        'Poly B Ask', 'Poly B Liq',
        'Best Combo', 'Total Cost', 'Gross %', 'Net ROI %', 'Net $', 'Status'
    ])
    
    for event_id, market_config in markets_config.items():
        team_a = market_config['teams']['team_a']
        team_b = market_config['teams']['team_b']
        description = market_config['description']
        sport = market_config.get('sport', 'NFL')  # Default to NFL if not specified
        
        # Get latest data
        data = get_latest_market_data(conn, event_id)
        
        # Get Kalshi data (uses city names)
        kalshi_a_data = data['kalshi'].get(team_a, {})
        kalshi_b_data = data['kalshi'].get(team_b, {})
        
        # Get Polymarket data (uses team nicknames)
        poly_team_a = normalize_team_name(team_a, to_polymarket=True, sport=sport)
        poly_team_b = normalize_team_name(team_b, to_polymarket=True, sport=sport)
        poly_a_data = data['polymarket'].get(poly_team_a, {})
        poly_b_data = data['polymarket'].get(poly_team_b, {})
        
        # Calculate arbitrage
        arb = calculate_arbitrage(data['kalshi'], data['polymarket'], team_a, team_b, sport)
        
        # Format for display
        kalshi_a_ask = kalshi_a_data.get('ask')
        kalshi_a_vol = kalshi_a_data.get('volume', 0)
        kalshi_b_ask = kalshi_b_data.get('ask')
        kalshi_b_vol = kalshi_b_data.get('volume', 0)
        poly_a_ask = poly_a_data.get('ask')
        poly_a_vol = poly_a_data.get('volume', 0)
        poly_b_ask = poly_b_data.get('ask')
        poly_b_vol = poly_b_data.get('volume', 0)
        
        # Track arbitrage opportunities (logs when they close)
        game_info = {
            'description': description,
            'team_a': team_a,
            'team_b': team_b,
            'kalshi_vol': kalshi_a_vol if arb and arb['kalshi_team'] == team_a else kalshi_b_vol,
            'poly_vol': poly_a_vol if arb and normalize_team_name(arb['poly_team'], to_polymarket=False, sport=sport) == team_a else poly_b_vol
        }
        track_arbitrage_opportunities(event_id, arb, game_info)
        
        # Determine status (based on NET profitability, not just gross < 1.0)
        if arb and arb.get('net_result') is not None:
            status = 'ARB'
            gross_profit_pct = ((1.0 - arb['total']) / arb['total']) * 100
            net_result = arb['net_result']
            net_roi = net_result['roi_pct']
            net_profit = net_result['net_profit']
            status_color = GREEN
        else:
            status = '-'
            gross_profit_pct = ((1.0 - arb['total']) / arb['total']) * 100 if arb and arb['total'] < 1.0 else 0
            net_roi = 0
            net_profit = 0
            status_color = RESET
        
        # Build row
        row = {
            'game': description[:30],
            'team_a': team_a[:15],
            'team_b': team_b[:15],
            'kalshi_a_ask': kalshi_a_ask,
            'kalshi_a_vol': kalshi_a_vol,
            'kalshi_b_ask': kalshi_b_ask,
            'kalshi_b_vol': kalshi_b_vol,
            'poly_a_ask': poly_a_ask,
            'poly_a_vol': poly_a_vol,
            'poly_b_ask': poly_b_ask,
            'poly_b_vol': poly_b_vol,
            'arb': arb,
            'status': status,
            'status_color': status_color,
            'gross_profit_pct': gross_profit_pct,
            'net_roi': net_roi,
            'net_profit': net_profit
        }
        
        rows.append(row)
        
        # CSV row - scale volumes to thousands for proper display
        csv_rows.append([
            description,
            team_a, team_b,
            kalshi_a_ask if kalshi_a_ask else '',
            kalshi_a_vol / 1000 if kalshi_a_vol else '',  # Scale to thousands
            kalshi_b_ask if kalshi_b_ask else '',
            kalshi_b_vol / 1000 if kalshi_b_vol else '',  # Scale to thousands
            poly_a_ask if poly_a_ask else '',
            poly_a_vol / 1000 if poly_a_vol else '',  # Scale to thousands
            poly_b_ask if poly_b_ask else '',
            poly_b_vol / 1000 if poly_b_vol else '',  # Scale to thousands
            arb['combo'] if arb else '',
            arb['total'] if arb else '',
            f"{gross_profit_pct:.2f}%" if gross_profit_pct > 0 else '',
            f"{net_roi:.2f}%" if net_roi > 0 else '',
            f"${net_profit:.2f}" if net_profit > 0 else '',
            status
        ])
    
    # Write CSV
    with open(CSV_OUTPUT, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(csv_rows)
    
    # Clear screen and display
    print(CLEAR_SCREEN, end='')
    
    # Header
    now = datetime.now().strftime('%H:%M:%S')
    print(f"{BOLD}{'='*180}{RESET}")
    print(f"{BOLD}LIVE ARBITRAGE DASHBOARD - {now}{RESET}".center(190))
    print(f"{BOLD}{'='*180}{RESET}")
    print()
    
    # Column headers
    print(f"{BOLD}{'GAME':<32} {'TEAM A':<15} {'TEAM B':<15} "
          f"{'K-A ASK':<9} {'K-A LIQ':<9} {'K-B ASK':<9} {'K-B LIQ':<9} "
          f"{'P-A ASK':<9} {'P-A LIQ':<9} {'P-B ASK':<9} {'P-B LIQ':<9} "
          f"{'BEST COMBO':<20} {'TOTAL':<8} {'NET ROI':<9} {'NET $':<9} {'STATUS':<6}{RESET}")
    print(f"{'─'*200}")
    
    # Data rows
    for row in rows:
        arb = row['arb']
        combo_str = arb['combo'] if arb else '-'
        total_str = f"{arb['total']:.4f}" if arb else '-'
        net_roi_str = f"{row['net_roi']:.2f}%" if row['net_roi'] > 0 else '-'
        net_profit_str = f"${row['net_profit']:.2f}" if row['net_profit'] > 0 else '-'
        
        # Apply color to entire row if arbitrage
        color = row['status_color']
        
        line = (f"{row['game']:<32} {row['team_a']:<15} {row['team_b']:<15} "
                f"{format_price(row['kalshi_a_ask']):<9} {format_volume(row['kalshi_a_vol']):<9} "
                f"{format_price(row['kalshi_b_ask']):<9} {format_volume(row['kalshi_b_vol']):<9} "
                f"{format_price(row['poly_a_ask']):<9} {format_volume(row['poly_a_vol']):<9} "
                f"{format_price(row['poly_b_ask']):<9} {format_volume(row['poly_b_vol']):<9} "
                f"{combo_str:<20} {total_str:<8} {net_roi_str:<9} {net_profit_str:<9} {row['status']:<6}")
        
        if color == GREEN:
            print(f"{GREEN}{line}{RESET}")
        else:
            print(line)
    
    print(f"{'─'*180}")
    
    # Show active arbitrage tracking
    active_arb_count = len(ACTIVE_ARBS)
    total_logged = 0
    try:
        with open(ARB_LOG_CSV, 'r') as f:
            total_logged = len(f.readlines()) - 1  # Exclude header
    except:
        pass
    
    print(f"\n{BLUE}CSV Export: {CSV_OUTPUT} | Refresh: {REFRESH_INTERVAL}s | Data Age: <{MAX_DATA_AGE}s{RESET}")
    print(f"{BLUE}Arb Opportunities: {active_arb_count} active, {total_logged} total logged (kept forever){RESET}")
    print(f"{YELLOW}Press Ctrl+C to stop{RESET}")

def main():
    """Main loop"""
    print(CLEAR_SCREEN, end='')
    print(f"{BOLD}Starting Live Dashboard...{RESET}")
    print(f"Loading configuration...")
    
    markets_config = load_markets_config()
    print(f"✓ Loaded {len(markets_config)} markets")
    
    # Initialize arbitrage opportunity log
    initialize_arb_log()
    print(f"✓ Arbitrage log: {ARB_LOG_CSV} (kept forever)")
    
    # Clean up old market data (not arbitrage opportunities!)
    print(f"Cleaning up old market data (>7 days)...")
    old_prices, old_orderbooks = cleanup_old_market_data(retention_days=7)
    if old_prices > 0 or old_orderbooks > 0:
        print(f"✓ Removed {old_prices:,} old price snapshots, {old_orderbooks:,} old orderbook snapshots")
    else:
        print(f"✓ No old market data to clean (all recent)")
    
    print(f"✓ Database: {DB_PATH}")
    print(f"✓ CSV output: {CSV_OUTPUT}")
    print(f"\nStarting live updates...\n")
    
    time.sleep(2)
    
    try:
        while True:
            conn = sqlite3.connect(DB_PATH, timeout=30.0)
            display_dashboard(markets_config, conn)
            conn.close()
            time.sleep(REFRESH_INTERVAL)
            
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Dashboard stopped.{RESET}")
        print(f"Final CSV saved to: {CSV_OUTPUT}")

if __name__ == "__main__":
    main()

