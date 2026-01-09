#!/usr/bin/env python3
"""
CORRECTED Arbitrage Analysis - Understanding Kalshi Mechanics

KEY INSIGHT from old bot:
- Kalshi markets have YES and NO sides
- "YES price" = probability team wins
- "NO price" = probability team loses (= 1 - YES price, roughly)
- You BUY YES or BUY NO, you don't "short sell"

CORRECTED ARBITRAGE:
If Kalshi shows Golden State:
- YES ask = 0.73 (buy to bet Golden State wins)
- NO ask = 0.27 (buy to bet Golden State loses)

And Polymarket shows Warriors:
- Price = 0.695 (buy to bet Warriors win)

Then the arbitrage is:
- BUY NO on Kalshi @ 0.27 (bet Golden State loses)
- BUY YES on Polymarket @ 0.695 (bet Warriors win)
- PROBLEM: You're betting OPPOSITE outcomes! Not arbitrage!

OR ALTERNATIVELY:
- BUY YES on both platforms
- Kalshi YES @ 0.73 + Polymarket YES @ 0.695 = 1.425
- Total cost > 1.0 = NOT arbitrage

Let me recalculate what the ACTUAL opportunity is...
"""

import sqlite3

TEAM_MAP = {
    'Boston': 'Celtics', 'Utah': 'Jazz', 'Golden State': 'Warriors',
    'Charlotte': 'Hornets', 'Portland': 'Trail Blazers', 'Oklahoma City': 'Thunder',
    'Minnesota': 'Timberwolves', 'Atlanta': 'Hawks', 'Orlando': 'Magic',
    'Indiana': 'Pacers', 'Phoenix': 'Suns', 'Cleveland': 'Cavaliers',
    'Denver': 'Nuggets', 'Toronto': 'Raptors', 'Chicago': 'Bulls',
    'New Orleans': 'Pelicans', 'New York': 'Knicks', 'San Antonio': 'Spurs',
    'Milwaukee': 'Bucks', 'Washington': 'Wizards'
}

print("=" * 80)
print("🔍 UNDERSTANDING KALSHI MECHANICS")
print("=" * 80)

conn = sqlite3.connect("data/market_data.db")
conn.row_factory = sqlite3.Row

# Get a sample of actual data to understand the structure
print("\n📊 Sample Data from Database:")
print("-" * 80)

query = """
SELECT 
    tm.description,
    ps.platform,
    ps.market_side,
    ps.yes_price,
    ps.yes_bid,
    ps.yes_ask,
    ps.no_price,
    ps.no_bid,
    ps.no_ask
FROM price_snapshots ps
JOIN tracked_markets tm ON ps.event_id = tm.event_id
WHERE tm.description = 'Golden State vs Charlotte Winner?'
    AND ps.timestamp > datetime('now', '-2 hours')
    AND ps.id IN (
        SELECT MAX(id)
        FROM price_snapshots
        WHERE event_id = ps.event_id
        GROUP BY platform, market_side
    )
ORDER BY platform, market_side;
"""

cursor = conn.cursor()
cursor.execute(query)
rows = cursor.fetchall()

print("\nGolden State vs Charlotte:")
for row in rows:
    print(f"\n{row['platform'].upper()} - {row['market_side']}:")
    print(f"  YES price: {row['yes_price']}")
    print(f"  YES bid:   {row['yes_bid']}")
    print(f"  YES ask:   {row['yes_ask']}")
    print(f"  NO price:  {row['no_price']}")
    print(f"  NO bid:    {row['no_bid']}")
    print(f"  NO ask:    {row['no_ask']}")

print("\n" + "=" * 80)
print("💡 KALSHI MECHANICS EXPLAINED")
print("=" * 80)

print("""
Kalshi has TWO SEPARATE MARKETS per game:
1. Market for Team A (e.g., "Golden State")
2. Market for Team B (e.g., "Charlotte")

Each market has:
- YES = this team wins
- NO = this team loses

Example: If Golden State market shows:
- YES ask = 0.73 → Pay $0.73 to win $1 if Golden State wins
- NO ask = 0.27 → Pay $0.27 to win $1 if Golden State loses

KEY INSIGHT:
- Golden State YES = Golden State wins
- Golden State NO = Golden State loses (= Charlotte wins)
- These are EQUIVALENT to each other!

Charlotte YES = Charlotte wins = Golden State loses = Golden State NO!

So if:
- Golden State YES ask = 0.73
- Charlotte YES ask = 0.29

Then (0.73 + 0.29) = 1.02 is the "overround" (market's profit margin)
""")

print("\n" + "=" * 80)
print("🎯 RECALCULATING THE REAL ARBITRAGE")
print("=" * 80)

# Now let's check what the ACTUAL arbitrage opportunity was
# We need to look at BOTH Golden State and Charlotte markets on Kalshi

query_both_teams = """
WITH latest_kalshi AS (
    SELECT 
        ps.market_side,
        ps.yes_price,
        ps.yes_bid,
        ps.yes_ask,
        ps.no_price,
        ps.no_bid,
        ps.no_ask
    FROM price_snapshots ps
    JOIN tracked_markets tm ON ps.event_id = tm.event_id
    WHERE tm.description = 'Golden State vs Charlotte Winner?'
        AND ps.platform = 'kalshi'
        AND ps.timestamp > datetime('now', '-2 hours')
        AND ps.id IN (
            SELECT MAX(id)
            FROM price_snapshots
            WHERE event_id = ps.event_id AND platform = 'kalshi'
            GROUP BY market_side
        )
),
latest_poly AS (
    SELECT 
        ps.market_side,
        ps.yes_price,
        ps.yes_bid,
        ps.yes_ask
    FROM price_snapshots ps
    JOIN tracked_markets tm ON ps.event_id = tm.event_id
    WHERE tm.description = 'Golden State vs Charlotte Winner?'
        AND ps.platform = 'polymarket'
        AND ps.timestamp > datetime('now', '-2 hours')
        AND ps.id IN (
            SELECT MAX(id)
            FROM price_snapshots
            WHERE event_id = ps.event_id AND platform = 'polymarket'
            GROUP BY market_side
        )
)
SELECT * FROM latest_kalshi
UNION ALL
SELECT * FROM latest_poly;
"""

cursor.execute(query_both_teams)
data = cursor.fetchall()

kalshi_gs = None
kalshi_char = None
poly_warriors = None
poly_hornets = None

for row in data:
    if row['market_side'] == 'Golden State':
        kalshi_gs = row
    elif row['market_side'] == 'Charlotte':
        kalshi_char = row
    elif row['market_side'] == 'Warriors':
        poly_warriors = row
    elif row['market_side'] == 'Hornets':
        poly_hornets = row

if all([kalshi_gs, kalshi_char, poly_warriors, poly_hornets]):
    print("\n📊 ALL PRICES:")
    print("-" * 80)
    print(f"\nKalshi - Golden State:")
    print(f"  YES ask: ${kalshi_gs['yes_ask']:.3f} (buy if you think GS wins)")
    print(f"  NO ask:  ${kalshi_gs['no_ask']:.3f} (buy if you think GS loses)")
    
    print(f"\nKalshi - Charlotte:")
    print(f"  YES ask: ${kalshi_char['yes_ask']:.3f} (buy if you think Charlotte wins)")
    print(f"  NO ask:  ${kalshi_char['no_ask']:.3f} (buy if you think Charlotte loses)")
    
    print(f"\nPolymarket - Warriors (= Golden State):")
    print(f"  Price: ${poly_warriors['yes_price']:.3f}")
    
    print(f"\nPolymarket - Hornets (= Charlotte):")
    print(f"  Price: ${poly_hornets['yes_price']:.3f}")
    
    print("\n" + "=" * 80)
    print("🔥 CHECKING ALL POSSIBLE ARBITRAGE COMBINATIONS")
    print("=" * 80)
    
    # Check all possible arbitrage combinations
    opps = []
    
    # 1. Bet Golden State wins on both platforms
    if kalshi_gs['yes_ask'] and poly_warriors['yes_price']:
        total = kalshi_gs['yes_ask'] + poly_warriors['yes_price']
        if total < 1.0:
            opps.append({
                'strategy': 'Bet GS wins on both (NOT ARBITRAGE - same outcome)',
                'kalshi': f"BUY YES on GS @ ${kalshi_gs['yes_ask']:.3f}",
                'poly': f"BUY Warriors @ ${poly_warriors['yes_price']:.3f}",
                'total': total,
                'profit': 1.0 - total,
                'valid': False,
                'reason': 'Betting same outcome twice - NOT hedged!'
            })
    
    # 2. Bet Golden State wins (Kalshi YES) + Charlotte wins (Poly Hornets)
    if kalshi_gs['yes_ask'] and poly_hornets['yes_price']:
        total = kalshi_gs['yes_ask'] + poly_hornets['yes_price']
        if total < 1.0:
            opps.append({
                'strategy': 'GS wins (Kalshi) + Charlotte wins (Poly) = OPPOSITE OUTCOMES',
                'kalshi': f"BUY YES on GS @ ${kalshi_gs['yes_ask']:.3f}",
                'poly': f"BUY Hornets @ ${poly_hornets['yes_price']:.3f}",
                'total': total,
                'profit': 1.0 - total,
                'valid': True,
                'reason': 'TRUE ARBITRAGE - covers both outcomes!'
            })
    
    # 3. Bet Charlotte wins (Kalshi YES) + GS wins (Poly Warriors)
    if kalshi_char['yes_ask'] and poly_warriors['yes_price']:
        total = kalshi_char['yes_ask'] + poly_warriors['yes_price']
        if total < 1.0:
            opps.append({
                'strategy': 'Charlotte wins (Kalshi) + GS wins (Poly) = OPPOSITE OUTCOMES',
                'kalshi': f"BUY YES on Charlotte @ ${kalshi_char['yes_ask']:.3f}",
                'poly': f"BUY Warriors @ ${poly_warriors['yes_price']:.3f}",
                'total': total,
                'profit': 1.0 - total,
                'valid': True,
                'reason': 'TRUE ARBITRAGE - covers both outcomes!'
            })
    
    # 4. Bet GS loses (Kalshi NO on GS = Charlotte wins) + GS wins (Poly)
    if kalshi_gs['no_ask'] and poly_warriors['yes_price']:
        total = kalshi_gs['no_ask'] + poly_warriors['yes_price']
        if total < 1.0:
            opps.append({
                'strategy': 'GS loses (Kalshi NO on GS) + GS wins (Poly) = OPPOSITE OUTCOMES',
                'kalshi': f"BUY NO on GS @ ${kalshi_gs['no_ask']:.3f} (= bet Charlotte wins)",
                'poly': f"BUY Warriors @ ${poly_warriors['yes_price']:.3f}",
                'total': total,
                'profit': 1.0 - total,
                'valid': True,
                'reason': 'TRUE ARBITRAGE - covers both outcomes!'
            })
    
    if opps:
        for i, opp in enumerate(opps, 1):
            print(f"\n{i}. {opp['strategy']}")
            print(f"   Kalshi:  {opp['kalshi']}")
            print(f"   Poly:    {opp['poly']}")
            print(f"   Total:   ${opp['total']:.4f}")
            print(f"   Profit:  ${opp['profit']:.4f} ({opp['profit']*100:.2f}%)")
            print(f"   Valid:   {'✅ YES' if opp['valid'] else '❌ NO'}")
            print(f"   Reason:  {opp['reason']}")
    else:
        print("\n❌ NO ARBITRAGE OPPORTUNITIES FOUND")
        print("   All combinations result in total cost >= $1.00")

conn.close()

print("\n" + "=" * 80)
print("✅ Analysis complete!")
print("=" * 80)

