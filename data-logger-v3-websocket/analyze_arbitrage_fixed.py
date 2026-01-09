#!/usr/bin/env python3
"""
Fixed Arbitrage Analysis - Properly matches team names

The key insight: Tennessee = Titans, they're the same team!
For arbitrage, we need to bet on OPPOSITE outcomes.
"""

import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict

# Team name mapping
TEAM_NORMALIZATION = {
    # NFL
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
    'Washington': 'Commanders',
    # Add reverse mappings
    'Cardinals': 'Cardinals',
    'Falcons': 'Falcons',
    'Ravens': 'Ravens',
    'Bills': 'Bills',
    'Panthers': 'Panthers',
    'Bears': 'Bears',
    'Bengals': 'Bengals',
    'Browns': 'Browns',
    'Cowboys': 'Cowboys',
    'Broncos': 'Broncos',
    'Lions': 'Lions',
    'Packers': 'Packers',
    'Texans': 'Texans',
    'Colts': 'Colts',
    'Jaguars': 'Jaguars',
    'Chiefs': 'Chiefs',
    'Raiders': 'Raiders',
    'Chargers': 'Chargers',
    'Rams': 'Rams',
    'Dolphins': 'Dolphins',
    'Vikings': 'Vikings',
    'Patriots': 'Patriots',
    'Saints': 'Saints',
    'Giants': 'Giants',
    'Jets': 'Jets',
    'Eagles': 'Eagles',
    'Steelers': 'Steelers',
    '49ers': '49ers',
    'Seahawks': 'Seahawks',
    'Buccaneers': 'Buccaneers',
    'Titans': 'Titans',
    'Commanders': 'Commanders'
}

def normalize_team_name(name):
    """Convert any team name to standard format"""
    return TEAM_NORMALIZATION.get(name, name)

def analyze_arbitrage_fixed(db_path="data/market_data.db", lookback_minutes=120):
    """Fixed arbitrage analysis with proper team matching"""
    
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    
    print("=" * 100)
    print("🔍 FIXED ARBITRAGE ANALYSIS (Proper Team Matching)")
    print("=" * 100)
    
    cutoff = (datetime.now() - timedelta(minutes=lookback_minutes)).isoformat()
    print(f"\nAnalyzing last {lookback_minutes} minutes (since {cutoff})")
    
    # Get all games
    cursor = conn.execute("""
        SELECT DISTINCT event_id 
        FROM price_snapshots 
        WHERE timestamp > ?
    """, (cutoff,))
    
    games = [row[0] for row in cursor]
    print(f"Analyzing {len(games)} games...")
    
    opportunities = []
    
    for game in games:
        # Get all snapshots for this game
        cursor = conn.execute("""
            SELECT 
                id, platform, market_side, yes_ask, timestamp
            FROM price_snapshots
            WHERE event_id = ? 
            AND timestamp > ?
            AND yes_ask IS NOT NULL
            AND yes_ask > 0
            ORDER BY timestamp DESC
        """, (game, cutoff))
        
        snapshots = cursor.fetchall()
        
        # Group by timestamp (within 5 seconds)
        time_groups = defaultdict(list)
        for snap in snapshots:
            # Round to 5-second buckets
            ts = datetime.fromisoformat(snap['timestamp'].replace('Z', ''))
            bucket = int(ts.timestamp() / 5) * 5
            time_groups[bucket].append(snap)
        
        # Check each time bucket for arbitrage
        for bucket, snaps in time_groups.items():
            kalshi_snaps = [s for s in snaps if s['platform'] == 'kalshi']
            poly_snaps = [s for s in snaps if s['platform'] == 'polymarket']
            
            if not kalshi_snaps or not poly_snaps:
                continue
            
            # Try all combinations
            for k_snap in kalshi_snaps:
                k_team = normalize_team_name(k_snap['market_side'])
                
                for p_snap in poly_snaps:
                    p_team = normalize_team_name(p_snap['market_side'])
                    
                    # CRITICAL: Only arbitrage if betting on DIFFERENT teams!
                    if k_team == p_team:
                        continue  # Same team = not arbitrage!
                    
                    total_cost = k_snap['yes_ask'] + p_snap['yes_ask']
                    
                    # Check for arbitrage (< 0.98 for 2% profit minimum)
                    if total_cost < 0.98:
                        gross_profit = 1.0 - total_cost
                        profit_pct = (gross_profit / total_cost) * 100
                        
                        opportunities.append({
                            'game': game,
                            'kalshi_team': k_snap['market_side'],
                            'kalshi_team_normalized': k_team,
                            'kalshi_ask': k_snap['yes_ask'],
                            'kalshi_snapshot': k_snap['id'],
                            'poly_team': p_snap['market_side'],
                            'poly_team_normalized': p_team,
                            'poly_ask': p_snap['yes_ask'],
                            'poly_snapshot': p_snap['id'],
                            'total_cost': total_cost,
                            'gross_profit_pct': profit_pct,
                            'timestamp': k_snap['timestamp']
                        })
    
    if not opportunities:
        print("\n❌ No arbitrage opportunities found.")
        print("\nThis means markets are efficient - no mispricing between platforms.")
        conn.close()
        return
    
    print(f"\n✅ Found {len(opportunities)} arbitrage opportunities!")
    
    # Display top opportunities
    opportunities.sort(key=lambda x: x['gross_profit_pct'], reverse=True)
    
    print("\n" + "=" * 100)
    print("📋 TOP 20 ARBITRAGE OPPORTUNITIES")
    print("=" * 100)
    
    for i, opp in enumerate(opportunities[:20], 1):
        print(f"\n{'─' * 100}")
        print(f"#{i} - {opp['timestamp']}")
        print(f"{'─' * 100}")
        print(f"Game: {opp['game']}")
        print(f"\n💰 Trade:")
        print(f"  Kalshi: Buy {opp['kalshi_team']} ({opp['kalshi_team_normalized']}) @ ${opp['kalshi_ask']:.3f}")
        print(f"  Polymarket: Buy {opp['poly_team']} ({opp['poly_team_normalized']}) @ ${opp['poly_ask']:.3f}")
        print(f"  Total Cost: ${opp['total_cost']:.3f}")
        print(f"  Gross Profit: {opp['gross_profit_pct']:.2f}%")
        
        # Get orderbook depth
        k_depth = get_orderbook_summary(conn, opp['kalshi_snapshot'])
        p_depth = get_orderbook_summary(conn, opp['poly_snapshot'])
        
        if k_depth and p_depth:
            print(f"\n📊 Liquidity:")
            print(f"  Kalshi: {k_depth['total_size']:,.0f} contracts available")
            print(f"  Polymarket: {p_depth['total_size']:,.0f} contracts available")
    
    # Summary
    print("\n\n" + "=" * 100)
    print("📈 SUMMARY")
    print("=" * 100)
    
    avg_profit = sum(o['gross_profit_pct'] for o in opportunities) / len(opportunities)
    max_profit = max(o['gross_profit_pct'] for o in opportunities)
    
    print(f"\nTotal opportunities: {len(opportunities)}")
    print(f"Average profit: {avg_profit:.2f}%")
    print(f"Maximum profit: {max_profit:.2f}%")
    
    # Group by game
    by_game = defaultdict(list)
    for opp in opportunities:
        by_game[opp['game']].append(opp)
    
    print(f"\n📊 By Game:")
    for game, game_opps in sorted(by_game.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
        print(f"  {game[:40]}: {len(game_opps)} opportunities")
    
    conn.close()

def get_orderbook_summary(conn, snapshot_id):
    """Get summary of orderbook liquidity"""
    cursor = conn.execute("""
        SELECT COUNT(*) as levels, SUM(size) as total_size
        FROM orderbook_snapshots
        WHERE snapshot_id = ?
        AND side = 'yes'
        AND order_type = 'ask'
    """, (snapshot_id,))
    
    row = cursor.fetchone()
    if row and row['levels'] > 0:
        return {
            'levels': row['levels'],
            'total_size': row['total_size']
        }
    return None

if __name__ == "__main__":
    import sys
    lookback = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    analyze_arbitrage_fixed(lookback_minutes=lookback)

