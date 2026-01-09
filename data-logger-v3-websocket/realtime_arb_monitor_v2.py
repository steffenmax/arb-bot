#!/usr/bin/env python3
"""
Real-Time Arbitrage Monitor v2
Properly implements the user's arbitrage strategy:
1. For each game, check BOTH cross-platform combinations
2. Monitor orderbook depth for liquidity/slippage
3. Time opportunities from detection to disappearance
4. Flag opportunities >= 1% profit
"""

import sqlite3
import time
import json
from datetime import datetime, timedelta
from collections import defaultdict

# Configuration
DB_PATH = "data/market_data.db"
CONFIG_PATH = "config/markets.json"
CHECK_INTERVAL = 1  # Check every 1 second
PROFIT_THRESHOLD = 0.01  # 1% minimum profit
OPPORTUNITY_TIMEOUT = 30  # Max seconds to track an opportunity

# Team name normalization for matching
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

def normalize_team_name(name):
    """Normalize team name for matching"""
    # Direct mapping
    if name in NFL_TEAM_MAP:
        return NFL_TEAM_MAP[name]
    
    # Try to match from team name to city
    for city, team in NFL_TEAM_MAP.items():
        if team.lower() == name.lower():
            return team
        if city.lower() in name.lower():
            return team
    
    return name

def load_markets_config():
    """Load markets configuration"""
    with open(CONFIG_PATH, 'r') as f:
        data = json.load(f)
        return {m['event_id']: m for m in data.get('markets', [])}

def get_latest_prices(conn, event_id, max_age_seconds=10):
    """
    Get latest prices for a game from both platforms
    Returns dict with structure:
    {
        'kalshi': {
            'team_a': {'name': 'Cowboys', 'ask': 0.30, 'timestamp': ...},
            'team_b': {'name': 'Giants', 'ask': 0.70, 'timestamp': ...}
        },
        'polymarket': {
            'team_a': {'name': 'Cowboys', 'ask': 0.29, 'timestamp': ...},
            'team_b': {'name': 'Giants', 'ask': 0.71, 'timestamp': ...}
        }
    }
    """
    cutoff = (datetime.now() - timedelta(seconds=max_age_seconds)).isoformat()
    
    cursor = conn.execute("""
        SELECT platform, market_side, yes_ask, timestamp
        FROM price_snapshots
        WHERE event_id = ?
        AND timestamp > ?
        AND yes_ask IS NOT NULL
        ORDER BY timestamp DESC
    """, (event_id, cutoff))
    
    rows = cursor.fetchall()
    
    prices = {
        'kalshi': {},
        'polymarket': {}
    }
    
    for row in rows:
        platform = row[0]
        team = row[1]
        ask = row[2]
        timestamp = row[3]
        
        norm_team = normalize_team_name(team)
        
        # Store if we don't have this team yet (newest first due to ORDER BY DESC)
        if norm_team not in prices[platform]:
            prices[platform][norm_team] = {
                'name': team,
                'ask': ask,
                'timestamp': timestamp
            }
    
    return prices

def calculate_vwap_from_db(conn, snapshot_id, side, order_type, target_dollars):
    """
    Calculate VWAP for a given dollar amount from orderbook data
    Returns (vwap_price, contracts_filled, slippage_pct)
    """
    cursor = conn.execute("""
        SELECT price, size
        FROM orderbook_snapshots
        WHERE snapshot_id = ?
        AND side = ?
        AND order_type = ?
        ORDER BY level
    """, (snapshot_id, side, order_type))
    
    levels = cursor.fetchall()
    
    if not levels:
        return None, 0, 0
    
    total_cost = 0
    contracts_filled = 0
    best_price = levels[0][0]
    
    for price, size in levels:
        # How many contracts can we afford at this level?
        max_contracts_at_level = min(size, (target_dollars - total_cost) / price)
        
        if max_contracts_at_level <= 0:
            break
        
        total_cost += max_contracts_at_level * price
        contracts_filled += max_contracts_at_level
        
        if total_cost >= target_dollars:
            break
    
    if contracts_filled == 0:
        return None, 0, 0
    
    vwap = total_cost / contracts_filled
    slippage_pct = ((vwap - best_price) / best_price) * 100 if best_price > 0 else 0
    
    return vwap, contracts_filled, slippage_pct

def check_arbitrage_opportunity(conn, event_id, market_config, prices):
    """
    Check for arbitrage opportunities using the correct strategy:
    - Combination A: Kalshi Team A YES + Polymarket Team B YES
    - Combination B: Kalshi Team B YES + Polymarket Team A YES
    
    Returns list of opportunities with details
    """
    opportunities = []
    
    kalshi_prices = prices.get('kalshi', {})
    poly_prices = prices.get('polymarket', {})
    
    # Need at least 2 teams from each platform
    if len(kalshi_prices) < 2 or len(poly_prices) < 2:
        return opportunities
    
    # Get team names from config
    team_a = market_config['teams']['team_a']
    team_b = market_config['teams']['team_b']
    
    norm_team_a = normalize_team_name(team_a)
    norm_team_b = normalize_team_name(team_b)
    
    # Find matching prices
    kalshi_a = kalshi_prices.get(norm_team_a)
    kalshi_b = kalshi_prices.get(norm_team_b)
    poly_a = poly_prices.get(norm_team_a)
    poly_b = poly_prices.get(norm_team_b)
    
    if not all([kalshi_a, kalshi_b, poly_a, poly_b]):
        return opportunities
    
    # Combination A: Buy Team A on Kalshi + Buy Team B on Polymarket
    combo_a_cost = kalshi_a['ask'] + poly_b['ask']
    combo_a_profit_pct = ((1.0 - combo_a_cost) / combo_a_cost) * 100 if combo_a_cost > 0 else 0
    
    if combo_a_cost < 1.0 and combo_a_profit_pct >= (PROFIT_THRESHOLD * 100):
        opportunities.append({
            'type': 'cross_platform',
            'combo': 'A',
            'kalshi_team': team_a,
            'kalshi_ask': kalshi_a['ask'],
            'poly_team': team_b,
            'poly_ask': poly_b['ask'],
            'total_cost': combo_a_cost,
            'profit_pct': combo_a_profit_pct,
            'timestamps': {
                'kalshi': kalshi_a['timestamp'],
                'poly': poly_b['timestamp']
            }
        })
    
    # Combination B: Buy Team B on Kalshi + Buy Team A on Polymarket
    combo_b_cost = kalshi_b['ask'] + poly_a['ask']
    combo_b_profit_pct = ((1.0 - combo_b_cost) / combo_b_cost) * 100 if combo_b_cost > 0 else 0
    
    if combo_b_cost < 1.0 and combo_b_profit_pct >= (PROFIT_THRESHOLD * 100):
        opportunities.append({
            'type': 'cross_platform',
            'combo': 'B',
            'kalshi_team': team_b,
            'kalshi_ask': kalshi_b['ask'],
            'poly_team': team_a,
            'poly_ask': poly_a['ask'],
            'total_cost': combo_b_cost,
            'profit_pct': combo_b_profit_pct,
            'timestamps': {
                'kalshi': kalshi_b['timestamp'],
                'poly': poly_a['timestamp']
            }
        })
    
    return opportunities

class OpportunityTracker:
    """Track arbitrage opportunities over time"""
    
    def __init__(self):
        self.active_opportunities = {}  # key: (event_id, combo) -> {start_time, last_seen, peak_profit, ...}
        self.completed_opportunities = []
    
    def update(self, event_id, opportunities, market_config):
        """Update tracking with new opportunities"""
        current_time = datetime.now()
        
        # Create a set of active opportunity keys
        current_opps = {(event_id, opp['combo']): opp for opp in opportunities}
        
        # Check existing opportunities
        for key in list(self.active_opportunities.keys()):
            if key[0] == event_id:
                if key in current_opps:
                    # Still active - update
                    self.active_opportunities[key]['last_seen'] = current_time
                    self.active_opportunities[key]['peak_profit'] = max(
                        self.active_opportunities[key]['peak_profit'],
                        current_opps[key]['profit_pct']
                    )
                else:
                    # Disappeared - mark as completed
                    opp = self.active_opportunities[key]
                    duration = (current_time - opp['start_time']).total_seconds()
                    opp['duration'] = duration
                    opp['end_time'] = current_time
                    self.completed_opportunities.append(opp)
                    del self.active_opportunities[key]
                    
                    # Print completion
                    print(f"\n⏱️  OPPORTUNITY ENDED")
                    print(f"   Game: {opp['description']}")
                    print(f"   Combo: {opp['kalshi_team']} (Kalshi) + {opp['poly_team']} (Poly)")
                    print(f"   Duration: {duration:.1f}s")
                    print(f"   Peak profit: {opp['peak_profit']:.2f}%")
        
        # Add new opportunities
        for key, opp_data in current_opps.items():
            if key not in self.active_opportunities:
                # New opportunity!
                self.active_opportunities[key] = {
                    'event_id': event_id,
                    'combo': opp_data['combo'],
                    'description': market_config['description'],
                    'kalshi_team': opp_data['kalshi_team'],
                    'poly_team': opp_data['poly_team'],
                    'start_time': current_time,
                    'last_seen': current_time,
                    'initial_profit': opp_data['profit_pct'],
                    'peak_profit': opp_data['profit_pct'],
                    'kalshi_ask': opp_data['kalshi_ask'],
                    'poly_ask': opp_data['poly_ask']
                }
                
                # Print alert
                print(f"\n🚨 ARBITRAGE OPPORTUNITY DETECTED!")
                print(f"   Game: {market_config['description']}")
                print(f"   Strategy: Buy {opp_data['kalshi_team']} on Kalshi @ ${opp_data['kalshi_ask']:.3f}")
                print(f"             Buy {opp_data['poly_team']} on Polymarket @ ${opp_data['poly_ask']:.3f}")
                print(f"   Total Cost: ${opp_data['total_cost']:.4f}")
                print(f"   Profit: {opp_data['profit_pct']:.2f}%")
                print(f"   Time: {current_time.strftime('%H:%M:%S')}")

def main():
    """Main monitoring loop"""
    print("=" * 80)
    print("🔍 REAL-TIME ARBITRAGE MONITOR v2")
    print("=" * 80)
    print(f"✓ Profit threshold: {PROFIT_THRESHOLD * 100:.1f}%")
    print(f"✓ Check interval: {CHECK_INTERVAL}s")
    print(f"✓ Database: {DB_PATH}")
    print("\nMonitoring for opportunities...\n")
    
    markets_config = load_markets_config()
    tracker = OpportunityTracker()
    
    try:
        while True:
            conn = sqlite3.connect(DB_PATH, timeout=30.0)
            
            # Check each market
            for event_id, market_config in markets_config.items():
                prices = get_latest_prices(conn, event_id)
                opportunities = check_arbitrage_opportunity(conn, event_id, market_config, prices)
                tracker.update(event_id, opportunities, market_config)
            
            conn.close()
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Stopping monitor...")
        print(f"\n📊 SUMMARY:")
        print(f"   Total opportunities detected: {len(tracker.completed_opportunities)}")
        if tracker.completed_opportunities:
            avg_duration = sum(o['duration'] for o in tracker.completed_opportunities) / len(tracker.completed_opportunities)
            print(f"   Average duration: {avg_duration:.1f}s")
            max_profit = max(o['peak_profit'] for o in tracker.completed_opportunities)
            print(f"   Best profit: {max_profit:.2f}%")

if __name__ == "__main__":
    main()

