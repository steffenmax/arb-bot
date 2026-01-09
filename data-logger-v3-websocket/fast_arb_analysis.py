#!/usr/bin/env python3
"""
Fast Arbitrage Analysis - Optimized for Large Datasets
"""

import sqlite3
from datetime import datetime

# Database path
DB_PATH = "data/market_data.db"

# Fee assumptions
KALSHI_FEE = 0.07  # 7% on profits
POLY_FEE = 0.02    # 2% on profits

print("=" * 80)
print("🔍 FAST ARBITRAGE ANALYSIS")
print("=" * 80)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# Count data first
print("\n📊 Checking data volume...")
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM price_snapshots WHERE timestamp > datetime('now', '-24 hours')")
total = cursor.fetchone()[0]
print(f"Total snapshots in last 24h: {total:,}")

# Use optimized SQL to find opportunities directly in database
print("\n🔍 Analyzing for arbitrage opportunities...")
print("(This uses SQL aggregation for speed)")

query = """
WITH latest_prices AS (
    -- Get most recent price for each game/platform/team combination
    SELECT 
        ps.event_id,
        tm.description,
        ps.market_side,
        ps.platform,
        ps.yes_price,
        ps.yes_bid,
        ps.yes_ask,
        ps.volume,
        ps.timestamp,
        ROW_NUMBER() OVER (
            PARTITION BY ps.event_id, ps.platform, ps.market_side 
            ORDER BY ps.timestamp DESC
        ) as rn
    FROM price_snapshots ps
    JOIN tracked_markets tm ON ps.event_id = tm.event_id
    WHERE ps.timestamp > datetime('now', '-24 hours')
        AND tm.description NOT LIKE '%Lakers%'
),
price_pairs AS (
    -- Join Kalshi and Polymarket prices for same game/team
    SELECT 
        k.description as game,
        k.market_side as team,
        k.yes_bid as k_bid,
        k.yes_ask as k_ask,
        k.yes_price as k_mid,
        k.volume as k_volume,
        k.timestamp as k_time,
        p.yes_price as p_price,
        p.yes_bid as p_bid,
        p.yes_ask as p_ask,
        p.volume as p_volume,
        p.timestamp as p_time
    FROM latest_prices k
    JOIN latest_prices p 
        ON k.event_id = p.event_id 
        AND k.market_side = p.market_side
    WHERE k.rn = 1 
        AND p.rn = 1
        AND k.platform = 'kalshi'
        AND p.platform = 'polymarket'
        AND k.yes_ask IS NOT NULL
        AND k.yes_bid IS NOT NULL
        AND p.yes_price IS NOT NULL
)
SELECT 
    game,
    team,
    k_bid,
    k_ask,
    k_mid,
    p_price,
    p_bid,
    p_ask,
    k_volume,
    p_volume,
    k_time,
    p_time,
    -- Calculate opportunity 1: Buy Kalshi, Sell Poly
    CASE WHEN p_bid IS NOT NULL THEN p_bid ELSE p_price END as poly_sell,
    -- Calculate opportunity 2: Buy Poly, Sell Kalshi  
    CASE WHEN p_ask IS NOT NULL THEN p_ask ELSE p_price END as poly_buy
FROM price_pairs
ORDER BY game, team;
"""

cursor.execute(query)
rows = cursor.fetchall()

print(f"✓ Found {len(rows)} game/team combinations to check\n")

opportunities = []

for row in rows:
    game = row['game']
    team = row['team']
    k_bid = row['k_bid']
    k_ask = row['k_ask']
    poly_sell = row['poly_sell']
    poly_buy = row['poly_buy']
    
    # Opportunity 1: Buy Kalshi @ ask, Sell Poly @ bid/price
    if k_ask and poly_sell:
        gross = poly_sell - k_ask
        if gross > 0:
            fees = (1 - k_ask) * KALSHI_FEE + poly_sell * POLY_FEE
            net = gross - fees
            pct = (net / k_ask) * 100
            
            if pct > 0.5:  # At least 0.5% profit
                opportunities.append({
                    'game': game,
                    'team': team,
                    'type': 'Buy Kalshi → Sell Poly',
                    'buy': k_ask,
                    'sell': poly_sell,
                    'gross': gross,
                    'net': net,
                    'pct': pct,
                    'k_vol': row['k_volume'],
                    'p_vol': row['p_volume']
                })
    
    # Opportunity 2: Buy Poly @ ask/price, Sell Kalshi @ bid
    if poly_buy and k_bid:
        gross = k_bid - poly_buy
        if gross > 0:
            fees = (1 - poly_buy) * POLY_FEE + k_bid * KALSHI_FEE
            net = gross - fees
            pct = (net / poly_buy) * 100
            
            if pct > 0.5:
                opportunities.append({
                    'game': game,
                    'team': team,
                    'type': 'Buy Poly → Sell Kalshi',
                    'buy': poly_buy,
                    'sell': k_bid,
                    'gross': gross,
                    'net': net,
                    'pct': pct,
                    'k_vol': row['k_volume'],
                    'p_vol': row['p_volume']
                })

conn.close()

# Display results
print("=" * 80)
if not opportunities:
    print("❌ NO ARBITRAGE OPPORTUNITIES FOUND (> 0.5% profit after fees)")
    print("\nThis means:")
    print("  • Markets are efficiently priced ✓")
    print("  • Spreads too wide to overcome 7% + 2% fees")
    print("  • Both platforms pricing games similarly")
else:
    print(f"🎯 FOUND {len(opportunities)} ARBITRAGE OPPORTUNITIES!")
    print("=" * 80)
    
    # Sort by profit
    opportunities.sort(key=lambda x: x['pct'], reverse=True)
    
    for i, opp in enumerate(opportunities, 1):
        print(f"\n📈 #{i}: {opp['game']} - {opp['team']}")
        print(f"   Strategy: {opp['type']}")
        print(f"   Buy at:  ${opp['buy']:.3f}")
        print(f"   Sell at: ${opp['sell']:.3f}")
        print(f"   Profit:  ${opp['net']:.4f} ({opp['pct']:.2f}%)")
        print(f"   Volumes: K=${opp['k_vol']:,.0f} | P=${opp['p_vol']:,.0f}")
    
    print("\n" + "=" * 80)
    print(f"Average Profit: {sum(o['pct'] for o in opportunities)/len(opportunities):.2f}%")
    print(f"Best Profit:    {max(o['pct'] for o in opportunities):.2f}%")

print("=" * 80)
print("✅ Analysis complete!")

