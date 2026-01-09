#!/usr/bin/env python3
"""
Opportunity Duration Analysis

Analyzes how long arbitrage opportunities lasted by looking at
all historical snapshots, not just the latest prices.
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

ONCHAIN_COST = 0.002

print("=" * 80)
print("⏱️  ARBITRAGE OPPORTUNITY DURATION ANALYSIS")
print("=" * 80)
print("\nAnalyzing how long opportunities lasted throughout the data...\n")

conn = sqlite3.connect("data/market_data.db")
conn.row_factory = sqlite3.Row

# Focus on the two opportunities we found
target_games = [
    ('Golden State', 'Warriors', 'Golden State vs Charlotte Winner?'),
    ('San Antonio', 'Spurs', 'New York vs San Antonio Winner?')
]

for k_team, p_team, game_desc in target_games:
    print("=" * 80)
    print(f"🎯 Analyzing: {game_desc}")
    print(f"   Team: {k_team} (Kalshi) = {p_team} (Polymarket)")
    print("=" * 80)
    
    # Get ALL Kalshi snapshots for this team
    query_k = """
    SELECT 
        ps.yes_bid,
        ps.yes_ask,
        ps.yes_price,
        ps.volume,
        ps.timestamp,
        strftime('%s', ps.timestamp) as ts_unix
    FROM price_snapshots ps
    JOIN tracked_markets tm ON ps.event_id = tm.event_id
    WHERE tm.description = ?
        AND ps.platform = 'kalshi'
        AND ps.market_side = ?
        AND ps.timestamp > datetime('now', '-24 hours')
    ORDER BY ps.timestamp;
    """
    
    cursor = conn.cursor()
    cursor.execute(query_k, (game_desc, k_team))
    kalshi_snaps = cursor.fetchall()
    
    # Get ALL Polymarket snapshots for this team
    query_p = """
    SELECT 
        ps.yes_price,
        ps.yes_bid,
        ps.yes_ask,
        ps.volume,
        ps.timestamp,
        strftime('%s', ps.timestamp) as ts_unix
    FROM price_snapshots ps
    JOIN tracked_markets tm ON ps.event_id = tm.event_id
    WHERE tm.description = ?
        AND ps.platform = 'polymarket'
        AND ps.market_side = ?
        AND ps.timestamp > datetime('now', '-24 hours')
    ORDER BY ps.timestamp;
    """
    
    cursor.execute(query_p, (game_desc, p_team))
    poly_snaps = cursor.fetchall()
    
    print(f"\n📊 Data points collected:")
    print(f"   Kalshi: {len(kalshi_snaps)} snapshots")
    print(f"   Polymarket: {len(poly_snaps)} snapshots")
    
    if not kalshi_snaps or not poly_snaps:
        print("   ⚠️  Insufficient data")
        continue
    
    print(f"\n⏰ Time range:")
    print(f"   Kalshi: {kalshi_snaps[0]['timestamp']} to {kalshi_snaps[-1]['timestamp']}")
    print(f"   Polymarket: {poly_snaps[0]['timestamp']} to {poly_snaps[-1]['timestamp']}")
    
    # Find all instances where arbitrage existed
    # For each Kalshi snapshot, find the closest Polymarket snapshot in time
    
    opportunities = []
    
    for k_snap in kalshi_snaps:
        k_bid = k_snap['yes_bid']
        k_time = int(k_snap['ts_unix'])
        k_timestamp = k_snap['timestamp']
        
        if not k_bid:
            continue
        
        # Find closest Polymarket snapshot (within 60 seconds)
        closest_p = None
        min_time_diff = 61  # Start at 61 to ensure we only get within 60 sec
        
        for p_snap in poly_snaps:
            p_time = int(p_snap['ts_unix'])
            time_diff = abs(k_time - p_time)
            
            if time_diff < min_time_diff:
                min_time_diff = time_diff
                closest_p = p_snap
        
        if not closest_p or min_time_diff > 60:
            continue
        
        p_price = closest_p['yes_price']
        p_timestamp = closest_p['timestamp']
        
        if not p_price:
            continue
        
        # Check if arbitrage exists: k_bid > p_price
        if k_bid > p_price:
            gross = k_bid - p_price
            fees = ONCHAIN_COST * p_price
            net = gross - fees
            
            if net > 0:
                profit_pct = (net / p_price) * 100
                
                opportunities.append({
                    'k_time': k_timestamp,
                    'p_time': p_timestamp,
                    'time_diff': min_time_diff,
                    'k_bid': k_bid,
                    'p_price': p_price,
                    'gross': gross,
                    'net': net,
                    'profit_pct': profit_pct
                })
    
    if not opportunities:
        print(f"\n❌ No arbitrage opportunities found in historical data")
        print(f"   (Kalshi bid never exceeded Polymarket price)")
        continue
    
    print(f"\n🔥 FOUND {len(opportunities)} ARBITRAGE INSTANCES!")
    print("\n" + "-" * 80)
    
    # Analyze duration
    if len(opportunities) == 1:
        print(f"\n📍 Single Opportunity:")
        opp = opportunities[0]
        print(f"   Time: {opp['k_time']}")
        print(f"   Kalshi bid: ${opp['k_bid']:.4f}")
        print(f"   Poly price: ${opp['p_price']:.4f}")
        print(f"   Profit: ${opp['net']:.4f} ({opp['profit_pct']:.2f}%)")
        print(f"   Duration: Single snapshot only (~3 seconds)")
    else:
        # Group consecutive opportunities
        print(f"\n📊 Opportunity Timeline:")
        print(f"   First seen: {opportunities[0]['k_time']}")
        print(f"   Last seen:  {opportunities[-1]['k_time']}")
        
        # Calculate time from first to last
        first_ts = datetime.fromisoformat(opportunities[0]['k_time'].replace('Z', '+00:00'))
        last_ts = datetime.fromisoformat(opportunities[-1]['k_time'].replace('Z', '+00:00'))
        duration = (last_ts - first_ts).total_seconds()
        
        print(f"   Total duration: {duration:.0f} seconds ({duration/60:.1f} minutes)")
        print(f"   Instances captured: {len(opportunities)}")
        print(f"   Average profit: {sum(o['profit_pct'] for o in opportunities)/len(opportunities):.2f}%")
        print(f"   Best profit: {max(o['profit_pct'] for o in opportunities):.2f}%")
        
        # Show some snapshots
        print(f"\n   📸 Sample snapshots:")
        for i, opp in enumerate(opportunities[:5], 1):
            print(f"      {i}. {opp['k_time']}: K_bid=${opp['k_bid']:.4f} > P=${opp['p_price']:.4f} = {opp['profit_pct']:.2f}% profit")
        
        if len(opportunities) > 5:
            print(f"      ... ({len(opportunities) - 5} more instances)")
        
        # Check if it was continuous or intermittent
        gaps = []
        for i in range(1, len(opportunities)):
            prev_ts = datetime.fromisoformat(opportunities[i-1]['k_time'].replace('Z', '+00:00'))
            curr_ts = datetime.fromisoformat(opportunities[i]['k_time'].replace('Z', '+00:00'))
            gap = (curr_ts - prev_ts).total_seconds()
            if gap > 10:  # More than 10 seconds = gap
                gaps.append(gap)
        
        if gaps:
            print(f"\n   ⚠️  Opportunity was INTERMITTENT:")
            print(f"      Found {len(gaps)} gaps > 10 seconds")
            print(f"      Largest gap: {max(gaps):.0f} seconds")
            print(f"      This means the opportunity appeared/disappeared multiple times")
        else:
            print(f"\n   ✓ Opportunity was CONTINUOUS")
            print(f"      No gaps > 10 seconds between snapshots")

conn.close()

print("\n" + "=" * 80)
print("📊 SUMMARY")
print("=" * 80)
print("\n💡 Key Insights:")
print("   • Your 3-second collection cycles captured these opportunities")
print("   • Duration analysis shows how fleeting (or persistent) they were")
print("   • If duration < 30 seconds → need VERY fast execution")
print("   • If duration > 5 minutes → more time to analyze and act")
print("\n" + "=" * 80)
print("✅ Duration analysis complete!")
print("=" * 80)

