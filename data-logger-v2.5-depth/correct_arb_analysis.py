#!/usr/bin/env python3
"""
CORRECT Arbitrage Analysis - Both Outcomes Strategy

Classic sports arbitrage: Bet both outcomes of a game across platforms
to guarantee profit regardless of winner.

Example:
- Game: Boston vs Utah
- Bet $500 on Boston at 0.70 (Kalshi)
- Bet $500 on Utah at 0.30 (Polymarket)
- Total cost: $1000
- If Boston wins: Get $714 (profit $14)
- If Utah wins: Get $1667 (profit $667)
- Either way, you profit!

The key: (Price_A + Price_B) < 1.0 = Guaranteed profit
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

KALSHI_FEE = 0.07
POLY_FEE = 0.02

print("=" * 80)
print("🎯 CORRECT ARBITRAGE ANALYSIS - Both Outcomes Strategy")
print("=" * 80)
print("\nLooking for opportunities where:")
print("  (Price_TeamA + Price_TeamB) < 1.0")
print("  = Guaranteed profit regardless of winner!")
print("=" * 80)

conn = sqlite3.connect("data/market_data.db")
conn.row_factory = sqlite3.Row

# Get all games and their teams
query = """
SELECT DISTINCT 
    tm.description,
    tm.event_id
FROM tracked_markets tm
WHERE tm.description NOT LIKE '%Lakers%'
ORDER BY tm.description;
"""

cursor = conn.cursor()
cursor.execute(query)
games = cursor.fetchall()

print(f"\n📊 Analyzing {len(games)} games...")

# For each game, get latest prices for both teams on both platforms
opportunities = []

for game in games:
    game_desc = game['description']
    event_id = game['event_id']
    
    # Get all prices for this game
    query_prices = """
    SELECT 
        platform,
        market_side,
        yes_price,
        yes_bid,
        yes_ask,
        volume
    FROM price_snapshots
    WHERE event_id = ?
        AND timestamp > datetime('now', '-2 hours')
        AND id IN (
            SELECT MAX(id)
            FROM price_snapshots
            WHERE event_id = ?
            GROUP BY platform, market_side
        )
    ORDER BY platform, market_side;
    """
    
    cursor.execute(query_prices, (event_id, event_id))
    prices = cursor.fetchall()
    
    # Organize by platform and team
    kalshi_prices = {}
    poly_prices = {}
    
    for p in prices:
        if p['platform'] == 'kalshi':
            kalshi_prices[p['market_side']] = p
        else:
            poly_prices[p['market_side']] = p
    
    if len(kalshi_prices) < 2 or len(poly_prices) < 2:
        continue  # Need both teams on both platforms
    
    # Get team pairs (each game has 2 teams)
    kalshi_teams = list(kalshi_prices.keys())
    poly_teams = list(poly_prices.keys())
    
    if len(kalshi_teams) != 2 or len(poly_prices) != 2:
        continue
    
    team_a_k = kalshi_teams[0]
    team_b_k = kalshi_teams[1]
    
    # Find matching Polymarket teams
    team_a_p = TEAM_MAP.get(team_a_k)
    team_b_p = TEAM_MAP.get(team_b_k)
    
    if not team_a_p or not team_b_p:
        continue
    
    if team_a_p not in poly_prices or team_b_p not in poly_prices:
        continue
    
    # Now check all 4 combinations:
    # 1. Buy TeamA on Kalshi + Buy TeamB on Poly
    # 2. Buy TeamB on Kalshi + Buy TeamA on Poly
    # 3. Buy TeamA on Poly + Buy TeamB on Kalshi
    # 4. Buy TeamB on Poly + Buy TeamA on Kalshi
    
    combinations = [
        {
            'bet1_platform': 'Kalshi',
            'bet1_team': team_a_k,
            'bet1_price': kalshi_prices[team_a_k]['yes_ask'],
            'bet1_vol': kalshi_prices[team_a_k]['volume'],
            'bet2_platform': 'Polymarket',
            'bet2_team': team_b_p,
            'bet2_price': poly_prices[team_b_p]['yes_price'],
            'bet2_vol': poly_prices[team_b_p]['volume'],
        },
        {
            'bet1_platform': 'Kalshi',
            'bet1_team': team_b_k,
            'bet1_price': kalshi_prices[team_b_k]['yes_ask'],
            'bet1_vol': kalshi_prices[team_b_k]['volume'],
            'bet2_platform': 'Polymarket',
            'bet2_team': team_a_p,
            'bet2_price': poly_prices[team_a_p]['yes_price'],
            'bet2_vol': poly_prices[team_a_p]['volume'],
        },
        {
            'bet1_platform': 'Polymarket',
            'bet1_team': team_a_p,
            'bet1_price': poly_prices[team_a_p]['yes_price'],
            'bet1_vol': poly_prices[team_a_p]['volume'],
            'bet2_platform': 'Kalshi',
            'bet2_team': team_b_k,
            'bet2_price': kalshi_prices[team_b_k]['yes_ask'],
            'bet2_vol': kalshi_prices[team_b_k]['volume'],
        },
        {
            'bet1_platform': 'Polymarket',
            'bet1_team': team_b_p,
            'bet1_price': poly_prices[team_b_p]['yes_price'],
            'bet1_vol': poly_prices[team_b_p]['volume'],
            'bet2_platform': 'Kalshi',
            'bet2_team': team_a_k,
            'bet2_price': kalshi_prices[team_a_k]['yes_ask'],
            'bet2_vol': kalshi_prices[team_a_k]['volume'],
        }
    ]
    
    for combo in combinations:
        p1 = combo['bet1_price']
        p2 = combo['bet2_price']
        
        if not p1 or not p2:
            continue
        
        # Total cost to bet $1 on each outcome
        total_cost = p1 + p2
        
        # If total < 1.0, we have arbitrage!
        if total_cost < 1.0:
            # Calculate profit
            gross_profit = 1.0 - total_cost
            
            # Calculate fees (simplified - on the winning bet only)
            # Worst case: pay fee on the larger bet
            fee1 = KALSHI_FEE if 'Kalshi' in combo['bet1_platform'] else POLY_FEE
            fee2 = KALSHI_FEE if 'Kalshi' in combo['bet2_platform'] else POLY_FEE
            
            # Conservative estimate: pay fee on both potential wins
            max_fee = (1.0 - p1) * fee1 + (1.0 - p2) * fee2
            
            net_profit = gross_profit - max_fee
            profit_pct = (net_profit / total_cost) * 100
            
            opportunities.append({
                'game': game_desc,
                'bet1_platform': combo['bet1_platform'],
                'bet1_team': combo['bet1_team'],
                'bet1_price': p1,
                'bet1_vol': combo['bet1_vol'],
                'bet2_platform': combo['bet2_platform'],
                'bet2_team': combo['bet2_team'],
                'bet2_price': p2,
                'bet2_vol': combo['bet2_vol'],
                'total_cost': total_cost,
                'gross_profit': gross_profit,
                'net_profit': net_profit,
                'profit_pct': profit_pct
            })

conn.close()

# Display results
print("\n" + "=" * 80)
if not opportunities:
    print("❌ NO ARBITRAGE OPPORTUNITIES FOUND")
    print("\n📊 This means:")
    print("  • For every game: (Price_A + Price_B) >= 1.0")
    print("  • Markets are efficiently priced")
    print("  • No guaranteed profit available")
else:
    print(f"🎯 FOUND {len(opportunities)} ARBITRAGE OPPORTUNITIES!")
    print("=" * 80)
    
    opportunities.sort(key=lambda x: x['profit_pct'], reverse=True)
    
    for i, opp in enumerate(opportunities, 1):
        print(f"\n💰 Opportunity #{i}: {opp['game']}")
        print(f"   {'─' * 76}")
        print(f"   Bet 1: ${opp['bet1_price']:.4f} on {opp['bet1_team']} ({opp['bet1_platform']})")
        print(f"   Bet 2: ${opp['bet2_price']:.4f} on {opp['bet2_team']} ({opp['bet2_platform']})")
        print(f"   ")
        print(f"   Total Cost:   ${opp['total_cost']:.4f}")
        print(f"   Payout:       $1.0000 (guaranteed)")
        print(f"   Gross Profit: ${opp['gross_profit']:.4f} ({opp['gross_profit']*100:.2f}%)")
        print(f"   After Fees:   ${opp['net_profit']:.4f} ({opp['profit_pct']:.2f}%)")
        print(f"   ")
        print(f"   Volumes: {opp['bet1_platform'][0]}=${opp['bet1_vol']:,.0f} | {opp['bet2_platform'][0]}=${opp['bet2_vol']:,.0f}")
        
        if i < len(opportunities):
            print(f"   {'─' * 76}")
    
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"Total Opportunities: {len(opportunities)}")
    print(f"Average Profit:      {sum(o['profit_pct'] for o in opportunities)/len(opportunities):.2f}%")
    print(f"Best Profit:         {max(o['profit_pct'] for o in opportunities):.2f}%")

print("\n" + "=" * 80)
print("✅ Analysis complete!")

