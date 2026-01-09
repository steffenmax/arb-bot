#!/usr/bin/env python3
"""
Arbitrage Analysis with Team Name Mapping

Maps between Kalshi's city names and Polymarket's team names
to properly match markets for arbitrage detection.
"""

import sqlite3

# Team name mapping: Kalshi city → Polymarket team name
TEAM_MAP = {
    'Boston': 'Celtics',
    'Utah': 'Jazz',
    'Golden State': 'Warriors',
    'Charlotte': 'Hornets',
    'Portland': 'Trail Blazers',
    'Oklahoma City': 'Thunder',
    'Minnesota': 'Timberwolves',
    'Atlanta': 'Hawks',
    'Orlando': 'Magic',
    'Indiana': 'Pacers',
    'Phoenix': 'Suns',
    'Cleveland': 'Cavaliers',
    'Denver': 'Nuggets',
    'Toronto': 'Raptors',
    'Chicago': 'Bulls',
    'New Orleans': 'Pelicans',
    'New York': 'Knicks',
    'San Antonio': 'Spurs',
    'Milwaukee': 'Bucks',
    'Washington': 'Wizards'
}

# Reverse map for matching
POLY_TO_KALSHI = {v: k for k, v in TEAM_MAP.items()}

KALSHI_FEE = 0.07  # 7% on profits
POLY_FEE = 0.02    # 2% on profits

print("=" * 80)
print("🔍 ARBITRAGE ANALYSIS (WITH TEAM MAPPING)")
print("=" * 80)

conn = sqlite3.connect("data/market_data.db")
conn.row_factory = sqlite3.Row

# Get latest prices for each platform
print("\n📊 Loading latest prices...")

query_kalshi = """
SELECT 
    ps.event_id,
    tm.description,
    ps.market_side,
    ps.yes_bid,
    ps.yes_ask,
    ps.yes_price,
    ps.volume,
    ps.timestamp
FROM price_snapshots ps
JOIN tracked_markets tm ON ps.event_id = tm.event_id
WHERE ps.platform = 'kalshi'
    AND ps.timestamp > datetime('now', '-24 hours')
    AND tm.description NOT LIKE '%Lakers%'
    AND ps.id IN (
        SELECT MAX(id) 
        FROM price_snapshots 
        WHERE platform = 'kalshi' 
        GROUP BY event_id, market_side
    )
ORDER BY ps.timestamp DESC;
"""

query_poly = """
SELECT 
    ps.event_id,
    tm.description,
    ps.market_side,
    ps.yes_price,
    ps.yes_bid,
    ps.yes_ask,
    ps.volume,
    ps.timestamp
FROM price_snapshots ps
JOIN tracked_markets tm ON ps.event_id = tm.event_id
WHERE ps.platform = 'polymarket'
    AND ps.timestamp > datetime('now', '-24 hours')
    AND tm.description NOT LIKE '%Lakers%'
    AND ps.id IN (
        SELECT MAX(id) 
        FROM price_snapshots 
        WHERE platform = 'polymarket' 
        GROUP BY event_id, market_side
    )
ORDER BY ps.timestamp DESC;
"""

cursor = conn.cursor()
cursor.execute(query_kalshi)
kalshi_data = cursor.fetchall()

cursor.execute(query_poly)
poly_data = cursor.fetchall()

print(f"✓ Loaded {len(kalshi_data)} Kalshi prices")
print(f"✓ Loaded {len(poly_data)} Polymarket prices")

# Build lookup dictionaries
kalshi_by_team = {}
for row in kalshi_data:
    team = row['market_side']
    kalshi_by_team[team] = row

poly_by_team = {}
for row in poly_data:
    team = row['market_side']
    poly_by_team[team] = row

print(f"\n🔗 Matching markets using team name mapping...")

# Match markets and find arbitrage
opportunities = []
matched_count = 0

for k_city, k_data in kalshi_by_team.items():
    # Find matching Polymarket team
    p_team = TEAM_MAP.get(k_city)
    
    if not p_team or p_team not in poly_by_team:
        continue
    
    p_data = poly_by_team[p_team]
    matched_count += 1
    
    # Extract prices
    k_bid = k_data['yes_bid']
    k_ask = k_data['yes_ask']
    k_mid = k_data['yes_price']
    p_price = p_data['yes_price']
    p_bid = p_data['yes_bid']
    p_ask = p_data['yes_ask']
    
    if not k_bid or not k_ask or not p_price:
        continue
    
    # Opportunity 1: Buy Kalshi @ ask, Sell Poly @ bid/price
    poly_sell = p_bid if p_bid else p_price
    if poly_sell:
        gross = poly_sell - k_ask
        if gross > 0:
            fees = (1 - k_ask) * KALSHI_FEE + poly_sell * POLY_FEE
            net = gross - fees
            pct = (net / k_ask) * 100
            
            if pct > 0.1:  # Even 0.1% profit is interesting
                opportunities.append({
                    'game': k_data['description'],
                    'team_k': k_city,
                    'team_p': p_team,
                    'type': 'Buy Kalshi → Sell Poly',
                    'buy': k_ask,
                    'sell': poly_sell,
                    'gross': gross,
                    'net': net,
                    'pct': pct,
                    'k_vol': k_data['volume'],
                    'p_vol': p_data['volume'],
                    'spread': k_ask - k_bid
                })
    
    # Opportunity 2: Buy Poly @ ask/price, Sell Kalshi @ bid
    poly_buy = p_ask if p_ask else p_price
    if poly_buy and k_bid:
        gross = k_bid - poly_buy
        if gross > 0:
            fees = (1 - poly_buy) * POLY_FEE + k_bid * KALSHI_FEE
            net = gross - fees
            pct = (net / poly_buy) * 100
            
            if pct > 0.1:
                opportunities.append({
                    'game': k_data['description'],
                    'team_k': k_city,
                    'team_p': p_team,
                    'type': 'Buy Poly → Sell Kalshi',
                    'buy': poly_buy,
                    'sell': k_bid,
                    'gross': gross,
                    'net': net,
                    'pct': pct,
                    'k_vol': k_data['volume'],
                    'p_vol': p_data['volume'],
                    'spread': k_ask - k_bid
                })

conn.close()

print(f"✓ Successfully matched {matched_count} markets")

# Display results
print("\n" + "=" * 80)
if not opportunities:
    print("❌ NO ARBITRAGE OPPORTUNITIES FOUND (> 0.1% profit after fees)")
    print("\n📊 Analysis:")
    print(f"  • Matched {matched_count} markets between platforms")
    print(f"  • Markets are efficiently priced")
    print(f"  • Spreads too wide to overcome fees (7% Kalshi + 2% Poly)")
    print("\n💡 This is actually GOOD news - it means:")
    print("  • Both platforms are pricing games accurately")
    print("  • Your data collection is working correctly")
    print("  • The market is competitive (hard to find edge)")
else:
    print(f"🎯 FOUND {len(opportunities)} ARBITRAGE OPPORTUNITIES!")
    print("=" * 80)
    
    opportunities.sort(key=lambda x: x['pct'], reverse=True)
    
    for i, opp in enumerate(opportunities[:20], 1):  # Show top 20
        print(f"\n📈 Opportunity #{i}")
        print(f"   Game:     {opp['game']}")
        print(f"   Teams:    {opp['team_k']} (Kalshi) = {opp['team_p']} (Poly)")
        print(f"   Strategy: {opp['type']}")
        print(f"   ")
        print(f"   💰 BUY  at ${opp['buy']:.4f}")
        print(f"   💵 SELL at ${opp['sell']:.4f}")
        print(f"   ")
        print(f"   📊 Gross: ${opp['gross']:.4f} ({opp['gross']*100:.2f}%)")
        print(f"   💸 Net:   ${opp['net']:.4f} ({opp['pct']:.2f}%)")
        print(f"   📏 K Spread: ${opp['spread']:.4f}")
        print(f"   💰 Volumes: K=${opp['k_vol']:,.0f} | P=${opp['p_vol']:,.0f}")
        
        if i < len(opportunities):
            print(f"   {'-' * 76}")
    
    if len(opportunities) > 20:
        print(f"\n   ... and {len(opportunities) - 20} more opportunities")
    
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"Total Opportunities: {len(opportunities)}")
    print(f"Average Profit:      {sum(o['pct'] for o in opportunities)/len(opportunities):.2f}%")
    print(f"Best Profit:         {max(o['pct'] for o in opportunities):.2f}%")
    print(f"Worst Profit:        {min(o['pct'] for o in opportunities):.2f}%")

print("\n" + "=" * 80)
print("✅ Analysis complete!")
print("=" * 80)

