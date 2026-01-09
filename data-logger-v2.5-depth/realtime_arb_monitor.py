#!/usr/bin/env python3
"""
Real-Time NFL Arbitrage Monitor

Continuously monitors for arbitrage opportunities >= 1%
Displays opportunities as they appear and tracks duration
"""

import sqlite3
import time
from datetime import datetime
from collections import defaultdict

DB_PATH = "data/market_data.db"
MIN_PROFIT_THRESHOLD = 0.01  # 1%
CHECK_INTERVAL = 0.5  # Check every 0.5 seconds

# NFL Team name mapping (City -> Team Name)
NFL_TEAM_MAP = {
    'Carolina': 'Panthers',
    'Tampa Bay': 'Buccaneers',
    'Seattle': 'Seahawks',
    'San Francisco': '49ers',
    'Arizona': 'Cardinals',
    'Atlanta': 'Falcons',
    'Baltimore': 'Ravens',
    'Buffalo': 'Bills',
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
    'Los Angeles': 'Chargers',
    'Miami': 'Dolphins',
    'Minnesota': 'Vikings',
    'New England': 'Patriots',
    'New Orleans': 'Saints',
    'New York': 'Giants',
    'Philadelphia': 'Eagles',
    'Pittsburgh': 'Steelers',
    'Tennessee': 'Titans',
    'Washington': 'Commanders'
}

# Track active opportunities
active_opportunities = {}
opportunity_counter = 0

def clear_screen():
    """Clear terminal screen"""
    print("\033[2J\033[H", end="")

def get_latest_prices(conn):
    """Get latest prices for all NFL games"""
    cursor = conn.cursor()
    
    # Get all NFL games
    cursor.execute("""
        SELECT DISTINCT event_id, description 
        FROM tracked_markets 
        WHERE sport = 'NFL'
    """)
    games = cursor.fetchall()
    
    game_data = {}
    
    for game in games:
        event_id = game['event_id']
        description = game['description']
        
        # Get latest Kalshi prices
        cursor.execute("""
            SELECT market_side, yes_ask, no_ask, timestamp
            FROM price_snapshots
            WHERE event_id = ? AND platform = 'kalshi'
            ORDER BY id DESC
            LIMIT 1
        """, (event_id,))
        
        kalshi = cursor.fetchone()
        
        # Get latest Polymarket prices (both teams)
        cursor.execute("""
            SELECT market_side, yes_price, timestamp
            FROM price_snapshots
            WHERE event_id = ? AND platform = 'polymarket'
            ORDER BY id DESC
            LIMIT 2
        """, (event_id,))
        
        poly_teams = cursor.fetchall()
        
        if kalshi and len(poly_teams) == 2:
            game_data[event_id] = {
                'description': description,
                'kalshi': kalshi,
                'polymarket': poly_teams
            }
    
    return game_data

def find_arbitrage_opportunities(game_data):
    """Find arbitrage opportunities in current prices"""
    opportunities = []
    
    for event_id, data in game_data.items():
        kalshi = data['kalshi']
        poly_teams = data['polymarket']
        description = data['description']
        
        kalshi_team = kalshi['market_side']
        kalshi_yes_ask = kalshi['yes_ask']
        kalshi_no_ask = kalshi['no_ask']
        
        # Convert Kalshi city name to team name
        kalshi_team_name = NFL_TEAM_MAP.get(kalshi_team, kalshi_team)
        
        # Match Polymarket teams to Kalshi using team name mapping
        poly_same_team = None
        poly_opposite_team = None
        
        for p in poly_teams:
            poly_team_name = p['market_side']
            
            # Check if this Polymarket team matches the Kalshi team
            if kalshi_team_name.lower() in poly_team_name.lower() or poly_team_name.lower() in kalshi_team_name.lower():
                poly_same_team = p
            else:
                poly_opposite_team = p
        
        if not poly_same_team or not poly_opposite_team:
            continue
        
        # Calculate both-outcome arbitrage opportunities
        
        # Combo 1: Kalshi YES + Polymarket opposite team
        combo1_total = kalshi_yes_ask + poly_opposite_team['yes_price']
        combo1_profit = 1.0 - combo1_total
        
        if combo1_profit >= MIN_PROFIT_THRESHOLD:
            opportunities.append({
                'event_id': event_id,
                'game': description,
                'strategy': f"Kalshi YES ({kalshi_team}) + Poly {poly_opposite_team['market_side']}",
                'kalshi_side': f"YES {kalshi_team}",
                'kalshi_price': kalshi_yes_ask,
                'poly_side': poly_opposite_team['market_side'],
                'poly_price': poly_opposite_team['yes_price'],
                'total_cost': combo1_total,
                'profit_pct': combo1_profit * 100,
                'timestamp': datetime.now()
            })
        
        # Combo 2: Kalshi NO + Polymarket same team
        combo2_total = kalshi_no_ask + poly_same_team['yes_price']
        combo2_profit = 1.0 - combo2_total
        
        if combo2_profit >= MIN_PROFIT_THRESHOLD:
            opportunities.append({
                'event_id': event_id,
                'game': description,
                'strategy': f"Kalshi NO ({kalshi_team}) + Poly {poly_same_team['market_side']}",
                'kalshi_side': f"NO {kalshi_team}",
                'kalshi_price': kalshi_no_ask,
                'poly_side': poly_same_team['market_side'],
                'poly_price': poly_same_team['yes_price'],
                'total_cost': combo2_total,
                'profit_pct': combo2_profit * 100,
                'timestamp': datetime.now()
            })
    
    return opportunities

def display_header():
    """Display monitor header"""
    print("=" * 100)
    print("🔥 REAL-TIME NFL ARBITRAGE MONITOR")
    print("=" * 100)
    print(f"Monitoring for opportunities >= {MIN_PROFIT_THRESHOLD*100:.1f}%")
    print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100)

def display_active_opportunities(active_opps):
    """Display currently active opportunities"""
    if active_opps:
        print("\n🚨 ACTIVE OPPORTUNITIES:")
        print("-" * 100)
        for key, opp in active_opps.items():
            duration = (datetime.now() - opp['start_time']).total_seconds()
            print(f"\n#{opp['id']} - {opp['game']}")
            print(f"   Strategy: {opp['strategy']}")
            print(f"   Kalshi:  {opp['kalshi_side']:20s} @ {opp['kalshi_price']:.3f}")
            print(f"   Poly:    {opp['poly_side']:20s} @ {opp['poly_price']:.3f}")
            print(f"   Total:   {opp['total_cost']:.4f} → Profit: {opp['profit_pct']:.2f}%")
            print(f"   Duration: {duration:.1f}s (started {opp['start_time'].strftime('%H:%M:%S')})")
    else:
        print("\n⏳ No opportunities currently available")

def display_closed_opportunities(closed_opps):
    """Display recently closed opportunities"""
    if closed_opps:
        print("\n📊 RECENTLY CLOSED OPPORTUNITIES (Last 10):")
        print("-" * 100)
        for opp in closed_opps[-10:]:
            print(f"\n#{opp['id']} - {opp['game']}")
            print(f"   Strategy: {opp['strategy']}")
            print(f"   Kalshi:  {opp['kalshi_side']:20s} @ {opp['kalshi_price']:.3f}")
            print(f"   Poly:    {opp['poly_side']:20s} @ {opp['poly_price']:.3f}")
            print(f"   Total:   {opp['total_cost']:.4f} → Profit: {opp['profit_pct']:.2f}%")
            print(f"   Duration: {opp['duration']:.1f}s ({opp['start_time'].strftime('%H:%M:%S')} - {opp['end_time'].strftime('%H:%M:%S')})")

def main():
    """Main monitoring loop"""
    global opportunity_counter
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    closed_opportunities = []
    
    print("\n🚀 Starting real-time arbitrage monitor...")
    print(f"   Minimum profit threshold: {MIN_PROFIT_THRESHOLD*100:.1f}%")
    print(f"   Check interval: {CHECK_INTERVAL}s")
    print("\n")
    time.sleep(2)
    
    try:
        while True:
            # Get latest prices
            game_data = get_latest_prices(conn)
            
            # Find current opportunities
            current_opps = find_arbitrage_opportunities(game_data)
            
            # Create keys for current opportunities
            current_keys = set()
            for opp in current_opps:
                key = f"{opp['event_id']}_{opp['strategy']}"
                current_keys.add(key)
                
                # If this is a new opportunity, add it to active
                if key not in active_opportunities:
                    opportunity_counter += 1
                    active_opportunities[key] = {
                        'id': opportunity_counter,
                        'start_time': opp['timestamp'],
                        **opp
                    }
            
            # Check for closed opportunities
            closed_keys = set(active_opportunities.keys()) - current_keys
            for key in closed_keys:
                opp = active_opportunities.pop(key)
                opp['end_time'] = datetime.now()
                opp['duration'] = (opp['end_time'] - opp['start_time']).total_seconds()
                closed_opportunities.append(opp)
            
            # Display current state
            clear_screen()
            display_header()
            display_active_opportunities(active_opportunities)
            display_closed_opportunities(closed_opportunities)
            
            print("\n" + "=" * 100)
            print(f"Total opportunities detected: {opportunity_counter}")
            print(f"Currently active: {len(active_opportunities)}")
            print(f"Closed: {len(closed_opportunities)}")
            print("\nPress Ctrl+C to stop monitoring")
            print("=" * 100)
            
            time.sleep(CHECK_INTERVAL)
    
    except KeyboardInterrupt:
        print("\n\n🛑 Monitoring stopped by user")
        
        # Display final summary
        print("\n" + "=" * 100)
        print("📊 FINAL SUMMARY")
        print("=" * 100)
        print(f"Total opportunities detected: {opportunity_counter}")
        print(f"Active at shutdown: {len(active_opportunities)}")
        print(f"Closed: {len(closed_opportunities)}")
        
        if closed_opportunities:
            total_duration = sum(opp['duration'] for opp in closed_opportunities)
            avg_duration = total_duration / len(closed_opportunities)
            max_profit = max(opp['profit_pct'] for opp in closed_opportunities)
            
            print(f"\nAverage opportunity duration: {avg_duration:.1f}s")
            print(f"Maximum profit seen: {max_profit:.2f}%")
        
        print("=" * 100)
    
    finally:
        conn.close()

if __name__ == "__main__":
    main()

