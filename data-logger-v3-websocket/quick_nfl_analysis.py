#!/usr/bin/env python3
"""
Quick analysis of NFL data collected so far
"""

import sqlite3
from datetime import datetime

DB_PATH = "data/market_data.db"

print("=" * 80)
print("🏈 NFL DATA COLLECTION ANALYSIS")
print("=" * 80)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# Get overall stats
cursor = conn.cursor()

print("\n📊 COLLECTION STATISTICS:")
print("-" * 80)

# Total snapshots
cursor.execute("SELECT COUNT(*) as count FROM price_snapshots")
total_snapshots = cursor.fetchone()['count']
print(f"Total snapshots collected: {total_snapshots:,}")

# By platform
cursor.execute("""
    SELECT platform, COUNT(*) as count 
    FROM price_snapshots 
    GROUP BY platform
""")
for row in cursor.fetchall():
    print(f"  {row['platform'].capitalize()}: {row['count']:,} snapshots")

# Time range
cursor.execute("""
    SELECT 
        MIN(timestamp) as first_snapshot,
        MAX(timestamp) as last_snapshot
    FROM price_snapshots
""")
time_range = cursor.fetchone()
print(f"\nFirst snapshot: {time_range['first_snapshot']}")
print(f"Last snapshot:  {time_range['last_snapshot']}")

# Calculate duration
if time_range['first_snapshot'] and time_range['last_snapshot']:
    try:
        first_str = time_range['first_snapshot'].replace('Z', '').replace('+00:00', '')
        last_str = time_range['last_snapshot'].replace('Z', '').replace('+00:00', '')
        first = datetime.fromisoformat(first_str)
        last = datetime.fromisoformat(last_str)
        duration = last - first
        print(f"Duration: {duration}")
    except:
        print(f"Duration: (unable to calculate)")

# Get latest prices for each game
print("\n" + "=" * 80)
print("💰 LATEST PRICES")
print("=" * 80)

cursor.execute("""
    SELECT DISTINCT event_id, description 
    FROM tracked_markets 
    WHERE sport = 'NFL'
""")
games = cursor.fetchall()

for game in games:
    event_id = game['event_id']
    description = game['description']
    
    print(f"\n{description}")
    print("-" * 80)
    
    # Get latest Kalshi prices
    cursor.execute("""
        SELECT market_side, yes_ask, no_ask, yes_bid, no_bid, timestamp
        FROM price_snapshots
        WHERE event_id = ? AND platform = 'kalshi'
        ORDER BY timestamp DESC
        LIMIT 1
    """, (event_id,))
    
    kalshi = cursor.fetchone()
    if kalshi:
        print(f"\n📈 Kalshi - {kalshi['market_side']} market:")
        print(f"   YES: bid={kalshi['yes_bid']:.3f}, ask={kalshi['yes_ask']:.3f}")
        print(f"   NO:  bid={kalshi['no_bid']:.3f}, ask={kalshi['no_ask']:.3f}")
        print(f"   Time: {kalshi['timestamp']}")
    
    # Get latest Polymarket prices (both teams)
    cursor.execute("""
        SELECT market_side, yes_price, timestamp
        FROM price_snapshots
        WHERE event_id = ? AND platform = 'polymarket'
        ORDER BY timestamp DESC
        LIMIT 2
    """, (event_id,))
    
    poly_teams = cursor.fetchall()
    if poly_teams:
        print(f"\n📊 Polymarket:")
        for team in poly_teams:
            print(f"   {team['market_side']}: {team['yes_price']:.3f}")
        print(f"   Time: {poly_teams[0]['timestamp']}")

# Quick arbitrage check
print("\n" + "=" * 80)
print("🔍 QUICK ARBITRAGE CHECK")
print("=" * 80)

for game in games:
    event_id = game['event_id']
    description = game['description']
    
    # Get latest Kalshi prices
    cursor.execute("""
        SELECT market_side, yes_ask, no_ask
        FROM price_snapshots
        WHERE event_id = ? AND platform = 'kalshi'
        ORDER BY timestamp DESC
        LIMIT 1
    """, (event_id,))
    
    kalshi = cursor.fetchone()
    
    # Get latest Polymarket prices
    cursor.execute("""
        SELECT market_side, yes_price
        FROM price_snapshots
        WHERE event_id = ? AND platform = 'polymarket'
        ORDER BY timestamp DESC
        LIMIT 2
    """, (event_id,))
    
    poly_teams = cursor.fetchall()
    
    if kalshi and len(poly_teams) == 2:
        print(f"\n{description}")
        
        kalshi_team = kalshi['market_side']
        kalshi_yes_ask = kalshi['yes_ask']
        kalshi_no_ask = kalshi['no_ask']
        
        # Find which Polymarket team matches Kalshi YES team
        poly_same_team = None
        poly_opposite_team = None
        
        for p in poly_teams:
            # Simple matching - check if team name contains part of Kalshi team
            if kalshi_team.lower() in p['market_side'].lower() or p['market_side'].lower() in kalshi_team.lower():
                poly_same_team = p
            else:
                poly_opposite_team = p
        
        if poly_same_team and poly_opposite_team:
            # Both-outcome arbitrage: Kalshi YES + Polymarket opposite team
            combo1_total = kalshi_yes_ask + poly_opposite_team['yes_price']
            combo1_profit = 1.0 - combo1_total
            
            # Both-outcome arbitrage: Kalshi NO + Polymarket same team
            combo2_total = kalshi_no_ask + poly_same_team['yes_price']
            combo2_profit = 1.0 - combo2_total
            
            print(f"  Combo 1: Kalshi YES ({kalshi_team}) @ {kalshi_yes_ask:.3f} + Poly {poly_opposite_team['market_side']} @ {poly_opposite_team['yes_price']:.3f}")
            print(f"           Total: {combo1_total:.4f} → Profit: {combo1_profit:.4f} ({combo1_profit*100:.2f}%)")
            if combo1_profit > 0:
                print(f"           ✅ ARBITRAGE OPPORTUNITY!")
            
            print(f"\n  Combo 2: Kalshi NO ({kalshi_team}) @ {kalshi_no_ask:.3f} + Poly {poly_same_team['market_side']} @ {poly_same_team['yes_price']:.3f}")
            print(f"           Total: {combo2_total:.4f} → Profit: {combo2_profit:.4f} ({combo2_profit*100:.2f}%)")
            if combo2_profit > 0:
                print(f"           ✅ ARBITRAGE OPPORTUNITY!")

conn.close()

print("\n" + "=" * 80)
print("✅ Analysis complete!")
print("=" * 80)
print("\n💡 The data logger is still running in the background")
print("   It will continue collecting data for arbitrage analysis")

