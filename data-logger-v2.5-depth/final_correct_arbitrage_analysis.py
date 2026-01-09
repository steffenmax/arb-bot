#!/usr/bin/env python3
"""
CORRECTLY RECALCULATED Arbitrage Analysis

Understanding Kalshi properly:
- You can only BUY YES or BUY NO
- You CANNOT "short sell" or "sell to open"
- Kalshi has separate markets for each team

True Both-Outcome Arbitrage:
- Buy Team A to win on one platform
- Buy Team B to win on the other platform
- Total cost < $1.00 = guaranteed profit

Checking:
1. Kalshi Team A YES ask + Polymarket Team B price < 1.0
2. Kalshi Team B YES ask + Polymarket Team A price < 1.0
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

# Reverse map
POLY_TO_KALSHI = {v: k for k, v in TEAM_MAP.items()}

KALSHI_TAKER_FEE = 0.03
POLY_FEE = 0.00
ONCHAIN_COST = 0.002

print("=" * 80)
print("🔥 CORRECTLY RECALCULATED ARBITRAGE ANALYSIS")
print("=" * 80)
print("\n✅ CORRECT Understanding of Kalshi:")
print("   • You BUY YES (team wins) or BUY NO (team loses)")
print("   • You CANNOT short-sell or sell-to-open")
print("   • Kalshi has SEPARATE markets for each team")
print("\n🎯 Looking for TRUE both-outcome arbitrage:")
print("   • Buy Team A on Kalshi + Buy Team B on Polymarket")
print("   • Total cost < $1.00 = guaranteed profit")
print("=" * 80)

conn = sqlite3.connect("data/market_data.db")
conn.row_factory = sqlite3.Row

# Get all games
query_games = """
SELECT DISTINCT event_id, description
FROM tracked_markets
WHERE description NOT LIKE '%Lakers%'
ORDER BY description;
"""

cursor = conn.cursor()
cursor.execute(query_games)
games = cursor.fetchall()

print(f"\n📊 Analyzing {len(games)} games...")

all_opportunities = []

for game in games:
    event_id = game['event_id']
    game_desc = game['description']
    
    # Get all latest prices for this game
    query_prices = """
    SELECT 
        platform,
        market_side,
        yes_price,
        yes_ask,
        no_ask,
        volume,
        timestamp
    FROM price_snapshots
    WHERE event_id = ?
        AND timestamp > datetime('now', '-24 hours')
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
    
    # Organize data
    kalshi_prices = {}
    poly_prices = {}
    
    for p in prices:
        if p['platform'] == 'kalshi':
            kalshi_prices[p['market_side']] = p
        else:
            poly_prices[p['market_side']] = p
    
    # Need prices from both platforms for both teams
    if len(kalshi_prices) < 2 or len(poly_prices) < 2:
        continue
    
    kalshi_teams = list(kalshi_prices.keys())
    if len(kalshi_teams) != 2:
        continue
    
    team_a_k, team_b_k = kalshi_teams[0], kalshi_teams[1]
    team_a_p = TEAM_MAP.get(team_a_k)
    team_b_p = TEAM_MAP.get(team_b_k)
    
    if not team_a_p or not team_b_p:
        continue
    
    if team_a_p not in poly_prices or team_b_p not in poly_prices:
        continue
    
    # Now check the arbitrage opportunities
    # Opportunity 1: Buy Team A on Kalshi + Buy Team B on Polymarket
    k_team_a_yes_ask = kalshi_prices[team_a_k]['yes_ask']
    p_team_b_price = poly_prices[team_b_p]['yes_price']
    
    if k_team_a_yes_ask and p_team_b_price:
        total_cost = k_team_a_yes_ask + p_team_b_price
        
        if total_cost < 1.0:
            gross_profit = 1.0 - total_cost
            
            # Calculate fees
            # Worst case: both are taker fees
            kalshi_fee = (1.0 - k_team_a_yes_ask) * KALSHI_TAKER_FEE
            poly_fee = ONCHAIN_COST * p_team_b_price
            total_fees = kalshi_fee + poly_fee
            
            net_profit = gross_profit - total_fees
            
            if net_profit > 0:
                profit_pct = (net_profit / total_cost) * 100
                
                all_opportunities.append({
                    'game': game_desc,
                    'strategy': f'Buy {team_a_k} (Kalshi) + Buy {team_b_p} (Poly)',
                    'kalshi_action': f'BUY YES on {team_a_k}',
                    'kalshi_price': k_team_a_yes_ask,
                    'kalshi_vol': kalshi_prices[team_a_k]['volume'],
                    'poly_action': f'BUY {team_b_p}',
                    'poly_price': p_team_b_price,
                    'poly_vol': poly_prices[team_b_p]['volume'],
                    'total_cost': total_cost,
                    'gross_profit': gross_profit,
                    'fees': total_fees,
                    'net_profit': net_profit,
                    'profit_pct': profit_pct
                })
    
    # Opportunity 2: Buy Team B on Kalshi + Buy Team A on Polymarket
    k_team_b_yes_ask = kalshi_prices[team_b_k]['yes_ask']
    p_team_a_price = poly_prices[team_a_p]['yes_price']
    
    if k_team_b_yes_ask and p_team_a_price:
        total_cost = k_team_b_yes_ask + p_team_a_price
        
        if total_cost < 1.0:
            gross_profit = 1.0 - total_cost
            
            kalshi_fee = (1.0 - k_team_b_yes_ask) * KALSHI_TAKER_FEE
            poly_fee = ONCHAIN_COST * p_team_a_price
            total_fees = kalshi_fee + poly_fee
            
            net_profit = gross_profit - total_fees
            
            if net_profit > 0:
                profit_pct = (net_profit / total_cost) * 100
                
                all_opportunities.append({
                    'game': game_desc,
                    'strategy': f'Buy {team_b_k} (Kalshi) + Buy {team_a_p} (Poly)',
                    'kalshi_action': f'BUY YES on {team_b_k}',
                    'kalshi_price': k_team_b_yes_ask,
                    'kalshi_vol': kalshi_prices[team_b_k]['volume'],
                    'poly_action': f'BUY {team_a_p}',
                    'poly_price': p_team_a_price,
                    'poly_vol': poly_prices[team_a_p]['volume'],
                    'total_cost': total_cost,
                    'gross_profit': gross_profit,
                    'fees': total_fees,
                    'net_profit': net_profit,
                    'profit_pct': profit_pct
                })

conn.close()

# Display results
print("\n" + "=" * 80)
print("📊 RESULTS - BOTH-OUTCOME ARBITRAGE (CORRECTLY CALCULATED)")
print("=" * 80)

if not all_opportunities:
    print("\n❌ NO ARBITRAGE OPPORTUNITIES FOUND")
    print("\n📊 This means:")
    print("   • For every game: (Kalshi Team A + Poly Team B) >= $1.00")
    print("   • And: (Kalshi Team B + Poly Team A) >= $1.00")
    print("   • Markets maintain ~2-3% overround on both platforms")
    print("   • No guaranteed profit by betting both outcomes")
else:
    print(f"\n🎯 FOUND {len(all_opportunities)} ARBITRAGE OPPORTUNITIES!")
    print("=" * 80)
    
    # Sort by profit
    all_opportunities.sort(key=lambda x: x['profit_pct'], reverse=True)
    
    for i, opp in enumerate(all_opportunities[:10], 1):
        print(f"\n💰 Opportunity #{i}: {opp['game']}")
        print(f"   Strategy: {opp['strategy']}")
        print(f"   ")
        print(f"   Step 1: {opp['kalshi_action']} @ ${opp['kalshi_price']:.4f}")
        print(f"   Step 2: {opp['poly_action']} @ ${opp['poly_price']:.4f}")
        print(f"   ")
        print(f"   Total Cost:   ${opp['total_cost']:.4f}")
        print(f"   Payout:       $1.0000 (guaranteed)")
        print(f"   Gross Profit: ${opp['gross_profit']:.4f} ({opp['gross_profit']*100:.2f}%)")
        print(f"   Fees:         ${opp['fees']:.4f}")
        print(f"   NET PROFIT:   ${opp['net_profit']:.4f} ({opp['profit_pct']:.2f}%)")
        print(f"   ")
        print(f"   Volumes: K=${opp['kalshi_vol']:,.0f} | P=${opp['poly_vol']:,.0f}")
        
        if i < len(all_opportunities) and i < 10:
            print(f"   {'-' * 76}")
    
    if len(all_opportunities) > 10:
        print(f"\n   ... and {len(all_opportunities) - 10} more opportunities")
    
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"Total Opportunities: {len(all_opportunities)}")
    print(f"Average Profit:      {sum(o['profit_pct'] for o in all_opportunities)/len(all_opportunities):.2f}%")
    print(f"Best Profit:         {max(o['profit_pct'] for o in all_opportunities):.2f}%")
    print(f"Worst Profit:        {min(o['profit_pct'] for o in all_opportunities):.2f}%")
    
    # Calculate total potential
    total_gross = sum(o['gross_profit'] for o in all_opportunities)
    print(f"\nTotal Gross Profit Available: ${total_gross:.2f}")
    print(f"(If you captured all opportunities once)")

print("\n" + "=" * 80)
print("✅ CORRECTLY CALCULATED ARBITRAGE ANALYSIS COMPLETE!")
print("=" * 80)

