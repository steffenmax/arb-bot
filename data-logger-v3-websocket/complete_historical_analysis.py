#!/usr/bin/env python3
"""
Complete Historical Arbitrage Analysis

Analyzes EVERY price snapshot pair to find if arbitrage ever existed,
even for a brief moment.
"""

import sqlite3
from datetime import datetime

TEAM_MAP = {
    'Boston': 'Celtics', 'Utah': 'Jazz', 'Golden State': 'Warriors',
    'Charlotte': 'Hornets', 'Portland': 'Trail Blazers', 'Oklahoma City': 'Thunder',
    'Minnesota': 'Timberwolves', 'Atlanta': 'Hawks', 'Orlando': 'Magic',
    'Indiana': 'Pacers', 'Phoenix': 'Suns', 'Cleveland': 'Cavaliers',
    'Denver': 'Nuggets', 'Toronto': 'Raptors', 'Chicago': 'Bulls',
    'New Orleans': 'Pelicans', 'New York': 'Knicks', 'San Antonio': 'Spurs',
    'Milwaukee': 'Bucks', 'Washington': 'Wizards'
}

# Reverse mapping
POLY_TO_KALSHI = {v: k for k, v in TEAM_MAP.items()}

print("=" * 80)
print("🔍 COMPLETE HISTORICAL ARBITRAGE ANALYSIS")
print("=" * 80)
print("Analyzing ALL price snapshot combinations...")
print("This will take a moment...")
print("=" * 80)

conn = sqlite3.connect("data/market_data.db")
conn.row_factory = sqlite3.Row

# Get count first
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM price_snapshots WHERE timestamp > datetime('now', '-24 hours')")
total = cursor.fetchone()[0]
print(f"\n📊 Total snapshots to analyze: {total:,}")

# Strategy: For each game, get all Kalshi snapshots for both teams
# and all Polymarket snapshots for both teams, then check every combination
# where timestamps are within 60 seconds

query = """
SELECT DISTINCT event_id, description
FROM tracked_markets
WHERE description NOT LIKE '%Lakers%'
ORDER BY description;
"""

cursor.execute(query)
games = cursor.fetchall()

print(f"📊 Analyzing {len(games)} games...\n")

all_opportunities = []
games_checked = 0

for game in games:
    event_id = game['event_id']
    game_desc = game['description']
    games_checked += 1
    
    if games_checked % 5 == 0:
        print(f"  Progress: {games_checked}/{len(games)} games...")
    
    # Get ALL Kalshi prices for this game
    query_k = """
    SELECT 
        market_side,
        yes_price,
        yes_bid,
        yes_ask,
        volume,
        timestamp,
        strftime('%s', timestamp) as ts_unix
    FROM price_snapshots
    WHERE event_id = ?
        AND platform = 'kalshi'
        AND timestamp > datetime('now', '-24 hours')
        AND yes_ask IS NOT NULL
    ORDER BY timestamp;
    """
    
    cursor.execute(query_k, (event_id,))
    kalshi_snapshots = cursor.fetchall()
    
    # Get ALL Polymarket prices for this game
    query_p = """
    SELECT 
        market_side,
        yes_price,
        yes_bid,
        yes_ask,
        volume,
        timestamp,
        strftime('%s', timestamp) as ts_unix
    FROM price_snapshots
    WHERE event_id = ?
        AND platform = 'polymarket'
        AND timestamp > datetime('now', '-24 hours')
        AND yes_price IS NOT NULL
    ORDER BY timestamp;
    """
    
    cursor.execute(query_p, (event_id,))
    poly_snapshots = cursor.fetchall()
    
    # Organize by team
    kalshi_by_team = {}
    for snap in kalshi_snapshots:
        team = snap['market_side']
        if team not in kalshi_by_team:
            kalshi_by_team[team] = []
        kalshi_by_team[team].append(snap)
    
    poly_by_team = {}
    for snap in poly_snapshots:
        team = snap['market_side']
        if team not in poly_by_team:
            poly_by_team[team] = []
        poly_by_team[team].append(snap)
    
    # Need 2 teams on each platform
    if len(kalshi_by_team) < 2 or len(poly_by_team) < 2:
        continue
    
    kalshi_teams = list(kalshi_by_team.keys())
    if len(kalshi_teams) != 2:
        continue
    
    team_a_k, team_b_k = kalshi_teams[0], kalshi_teams[1]
    team_a_p = TEAM_MAP.get(team_a_k)
    team_b_p = TEAM_MAP.get(team_b_k)
    
    if not team_a_p or not team_b_p:
        continue
    
    if team_a_p not in poly_by_team or team_b_p not in poly_by_team:
        continue
    
    # Check every combination of Kalshi TeamA + Polymarket TeamB within time window
    for k_snap_a in kalshi_by_team[team_a_k]:
        k_time_a = int(k_snap_a['ts_unix'])
        k_price_a = k_snap_a['yes_ask']
        
        if not k_price_a:
            continue
        
        # Find Polymarket TeamB snapshots within 60 seconds
        for p_snap_b in poly_by_team[team_b_p]:
            p_time_b = int(p_snap_b['ts_unix'])
            p_price_b = p_snap_b['yes_price']
            
            if not p_price_b:
                continue
            
            time_diff = abs(k_time_a - p_time_b)
            if time_diff > 60:  # Only consider if within 60 seconds
                continue
            
            total = k_price_a + p_price_b
            
            if total < 1.0:
                profit_pct = ((1.0 - total) / total) * 100
                all_opportunities.append({
                    'game': game_desc,
                    'bet1': f"{team_a_k} (Kalshi)",
                    'price1': k_price_a,
                    'bet2': f"{team_b_p} (Poly)",
                    'price2': p_price_b,
                    'total': total,
                    'profit': 1.0 - total,
                    'profit_pct': profit_pct,
                    'time_diff': time_diff,
                    'k_time': k_snap_a['timestamp'],
                    'p_time': p_snap_b['timestamp']
                })
    
    # Also check Kalshi TeamB + Polymarket TeamA
    for k_snap_b in kalshi_by_team[team_b_k]:
        k_time_b = int(k_snap_b['ts_unix'])
        k_price_b = k_snap_b['yes_ask']
        
        if not k_price_b:
            continue
        
        for p_snap_a in poly_by_team[team_a_p]:
            p_time_a = int(p_snap_a['ts_unix'])
            p_price_a = p_snap_a['yes_price']
            
            if not p_price_a:
                continue
            
            time_diff = abs(k_time_b - p_time_a)
            if time_diff > 60:
                continue
            
            total = k_price_b + p_price_a
            
            if total < 1.0:
                profit_pct = ((1.0 - total) / total) * 100
                all_opportunities.append({
                    'game': game_desc,
                    'bet1': f"{team_b_k} (Kalshi)",
                    'price1': k_price_b,
                    'bet2': f"{team_a_p} (Poly)",
                    'price2': p_price_a,
                    'total': total,
                    'profit': 1.0 - total,
                    'profit_pct': profit_pct,
                    'time_diff': time_diff,
                    'k_time': k_snap_b['timestamp'],
                    'p_time': p_snap_a['timestamp']
                })

conn.close()

print("\n" + "=" * 80)
print("📊 RESULTS")
print("=" * 80)

if not all_opportunities:
    print("\n❌ CONFIRMED: NO ARBITRAGE OPPORTUNITIES FOUND")
    print("\nAnalyzed EVERY price snapshot combination where:")
    print("  • Both teams priced on both platforms")
    print("  • Timestamps within 60 seconds")
    print("  • ALL showed (Price_A + Price_B) >= 1.0")
    print("\n💡 This confirms the markets are highly efficient!")
else:
    print(f"\n🎯 FOUND {len(all_opportunities)} ARBITRAGE OPPORTUNITIES!")
    print("=" * 80)
    
    # Sort by profit
    all_opportunities.sort(key=lambda x: x['profit_pct'], reverse=True)
    
    # Show top 20
    for i, opp in enumerate(all_opportunities[:20], 1):
        print(f"\n💰 Opportunity #{i}")
        print(f"   Game: {opp['game']}")
        print(f"   ")
        print(f"   Bet 1: {opp['bet1']} @ ${opp['price1']:.4f}")
        print(f"   Bet 2: {opp['bet2']} @ ${opp['price2']:.4f}")
        print(f"   ")
        print(f"   Total Cost: ${opp['total']:.4f}")
        print(f"   Profit:     ${opp['profit']:.4f} ({opp['profit_pct']:.2f}%)")
        print(f"   ")
        print(f"   Kalshi Time: {opp['k_time']}")
        print(f"   Poly Time:   {opp['p_time']}")
        print(f"   Time Diff:   {opp['time_diff']} seconds")
        
        if i < len(all_opportunities) and i < 20:
            print(f"   {'-' * 76}")
    
    if len(all_opportunities) > 20:
        print(f"\n   ... and {len(all_opportunities) - 20} more opportunities!")
    
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"Total Opportunities:  {len(all_opportunities)}")
    print(f"Average Profit:       {sum(o['profit_pct'] for o in all_opportunities)/len(all_opportunities):.2f}%")
    print(f"Best Profit:          {max(o['profit_pct'] for o in all_opportunities):.2f}%")
    print(f"Smallest Profit:      {min(o['profit_pct'] for o in all_opportunities):.2f}%")
    
    # Group by game
    by_game = {}
    for opp in all_opportunities:
        game = opp['game']
        by_game[game] = by_game.get(game, 0) + 1
    
    print(f"\nOpportunities by game:")
    for game, count in sorted(by_game.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {game}: {count} instances")

print("\n" + "=" * 80)
print("✅ Complete analysis finished!")
print("=" * 80)

