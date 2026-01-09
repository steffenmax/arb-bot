#!/usr/bin/env python3
"""
CORRECTED Arbitrage Analysis

Uses ACTUAL fee structures:
- Kalshi: ~3% taker fee (price-dependent), 0% to -0.5% maker fee
- Polymarket: 0% trading fee on main product

Two strategies analyzed:
1. Both-outcome arbitrage: (PriceA + PriceB) < 1.0 - fees
2. Same-contract arbitrage: Kalshi_bid > Polymarket_ask (or vice versa)
"""

import sqlite3
from datetime import datetime

# CORRECTED FEE STRUCTURE
KALSHI_TAKER_FEE = 0.03  # ~3% conservative estimate for mid-prices
KALSHI_MAKER_FEE = 0.00  # 0% (can be negative, but use 0 conservatively)
POLYMARKET_FEE = 0.00    # 0% trading fee
ONCHAIN_COST = 0.002     # ~0.2% for on-chain costs (conservative)

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
print("🔥 CORRECTED ARBITRAGE ANALYSIS")
print("=" * 80)
print("\nCORRECTED FEE STRUCTURE:")
print(f"  Kalshi Taker:  {KALSHI_TAKER_FEE*100}%")
print(f"  Kalshi Maker:  {KALSHI_MAKER_FEE*100}%")
print(f"  Polymarket:    {POLYMARKET_FEE*100}%")
print(f"  On-chain:      {ONCHAIN_COST*100}%")
print(f"\n  Total Hurdle (Taker/Taker): ~{(KALSHI_TAKER_FEE + POLYMARKET_FEE + ONCHAIN_COST)*100:.1f}%")
print(f"  Total Hurdle (Maker/Maker): ~{(KALSHI_MAKER_FEE + POLYMARKET_FEE + ONCHAIN_COST)*100:.1f}%")
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
print("Looking for TWO types of arbitrage:\n")
print("1️⃣  BOTH-OUTCOME ARB: (PriceA + PriceB) < 0.97")
print("2️⃣  SAME-CONTRACT ARB: Kalshi_bid > Poly_ask (or vice versa)")
print("\n" + "=" * 80)

both_outcome_opps = []
same_contract_opps = []

for game in games:
    event_id = game['event_id']
    game_desc = game['description']
    
    # Get latest prices for all teams/platforms
    query_latest = """
    SELECT 
        platform,
        market_side,
        yes_price,
        yes_bid,
        yes_ask,
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
    
    cursor.execute(query_latest, (event_id, event_id))
    prices = cursor.fetchall()
    
    # Organize by platform and team
    kalshi_prices = {}
    poly_prices = {}
    
    for p in prices:
        if p['platform'] == 'kalshi':
            kalshi_prices[p['market_side']] = p
        else:
            poly_prices[p['market_side']] = p
    
    # Need data from both platforms
    if not kalshi_prices or not poly_prices:
        continue
    
    # === ANALYSIS 1: BOTH-OUTCOME ARBITRAGE ===
    
    if len(kalshi_prices) >= 2 and len(poly_prices) >= 2:
        kalshi_teams = list(kalshi_prices.keys())
        if len(kalshi_teams) == 2:
            team_a_k, team_b_k = kalshi_teams[0], kalshi_teams[1]
            team_a_p = TEAM_MAP.get(team_a_k)
            team_b_p = TEAM_MAP.get(team_b_k)
            
            if team_a_p and team_b_p and team_a_p in poly_prices and team_b_p in poly_prices:
                # Check all 4 combinations
                combos = [
                    (team_a_k, 'k', team_b_p, 'p'),  # TeamA Kalshi + TeamB Poly
                    (team_b_k, 'k', team_a_p, 'p'),  # TeamB Kalshi + TeamA Poly
                    (team_a_p, 'p', team_b_k, 'k'),  # TeamA Poly + TeamB Kalshi
                    (team_b_p, 'p', team_a_k, 'k'),  # TeamB Poly + TeamA Kalshi
                ]
                
                for t1, plat1, t2, plat2 in combos:
                    if plat1 == 'k':
                        p1 = kalshi_prices[t1]['yes_ask']
                        p1_bid = kalshi_prices[t1]['yes_bid']
                        vol1 = kalshi_prices[t1]['volume']
                    else:
                        p1 = poly_prices[t1]['yes_price']
                        p1_bid = None
                        vol1 = poly_prices[t1]['volume']
                    
                    if plat2 == 'k':
                        p2 = kalshi_prices[t2]['yes_ask']
                        p2_bid = kalshi_prices[t2]['yes_bid']
                        vol2 = kalshi_prices[t2]['volume']
                    else:
                        p2 = poly_prices[t2]['yes_price']
                        p2_bid = None
                        vol2 = poly_prices[t2]['volume']
                    
                    if not p1 or not p2:
                        continue
                    
                    total_cost = p1 + p2
                    
                    # Calculate fees (worst case: both are taker)
                    fee1 = KALSHI_TAKER_FEE if plat1 == 'k' else (POLYMARKET_FEE + ONCHAIN_COST)
                    fee2 = KALSHI_TAKER_FEE if plat2 == 'k' else (POLYMARKET_FEE + ONCHAIN_COST)
                    
                    # Fee is on profit, so on winning outcome
                    # Conservative: assume we pay fee on the larger win
                    max_win = max(1.0 - p1, 1.0 - p2)
                    total_fees = max_win * max(fee1, fee2)
                    
                    gross_profit = 1.0 - total_cost
                    net_profit = gross_profit - total_fees
                    
                    if net_profit > 0:
                        profit_pct = (net_profit / total_cost) * 100
                        
                        both_outcome_opps.append({
                            'game': game_desc,
                            'bet1': f"{t1} ({'Kalshi' if plat1=='k' else 'Poly'})",
                            'price1': p1,
                            'vol1': vol1,
                            'bet2': f"{t2} ({'Kalshi' if plat2=='k' else 'Poly'})",
                            'price2': p2,
                            'vol2': vol2,
                            'total_cost': total_cost,
                            'gross_profit': gross_profit,
                            'fees': total_fees,
                            'net_profit': net_profit,
                            'profit_pct': profit_pct
                        })
    
    # === ANALYSIS 2: SAME-CONTRACT ARBITRAGE ===
    
    for k_team, k_data in kalshi_prices.items():
        p_team = TEAM_MAP.get(k_team)
        
        if not p_team or p_team not in poly_prices:
            continue
        
        p_data = poly_prices[p_team]
        
        k_bid = k_data['yes_bid']
        k_ask = k_data['yes_ask']
        k_mid = k_data['yes_price']
        p_price = p_data['yes_price']
        p_bid = p_data['yes_bid']
        p_ask = p_data['yes_ask']
        
        if not all([k_bid, k_ask, p_price]):
            continue
        
        # Use p_price if no bid/ask (common for Polymarket)
        p_effective_bid = p_bid if p_bid else p_price
        p_effective_ask = p_ask if p_ask else p_price
        
        # Opportunity A: Sell on Kalshi (at bid), Buy on Poly (at ask)
        # Profit if: k_bid > p_effective_ask + fees
        if k_bid > p_effective_ask:
            gross = k_bid - p_effective_ask
            # Fees: Kalshi maker (0%) + Poly (0%) + onchain
            fees = ONCHAIN_COST * p_effective_ask
            net = gross - fees
            
            if net > 0:
                profit_pct = (net / p_effective_ask) * 100
                
                same_contract_opps.append({
                    'game': game_desc,
                    'team': f"{k_team} = {p_team}",
                    'direction': 'Sell Kalshi → Buy Poly',
                    'sell_platform': 'Kalshi',
                    'sell_price': k_bid,
                    'buy_platform': 'Polymarket',
                    'buy_price': p_effective_ask,
                    'gross': gross,
                    'fees': fees,
                    'net': net,
                    'profit_pct': profit_pct,
                    'k_vol': k_data['volume'],
                    'p_vol': p_data['volume'],
                    'spread_k': k_ask - k_bid if k_ask and k_bid else 0,
                    'spread_p': (p_ask - p_bid) if p_ask and p_bid else 0
                })
        
        # Opportunity B: Sell on Poly (at bid), Buy on Kalshi (at ask)
        # Profit if: p_effective_bid > k_ask + fees
        if p_effective_bid and p_effective_bid > k_ask:
            gross = p_effective_bid - k_ask
            # Fees: Poly (0%) + Kalshi taker (3%) + onchain
            fees = KALSHI_TAKER_FEE * k_ask + ONCHAIN_COST * k_ask
            net = gross - fees
            
            if net > 0:
                profit_pct = (net / k_ask) * 100
                
                same_contract_opps.append({
                    'game': game_desc,
                    'team': f"{k_team} = {p_team}",
                    'direction': 'Sell Poly → Buy Kalshi',
                    'sell_platform': 'Polymarket',
                    'sell_price': p_effective_bid,
                    'buy_platform': 'Kalshi',
                    'buy_price': k_ask,
                    'gross': gross,
                    'fees': fees,
                    'net': net,
                    'profit_pct': profit_pct,
                    'k_vol': k_data['volume'],
                    'p_vol': p_data['volume'],
                    'spread_k': k_ask - k_bid if k_ask and k_bid else 0,
                    'spread_p': (p_ask - p_bid) if p_ask and p_bid else 0
                })

conn.close()

# === DISPLAY RESULTS ===

print("\n" + "=" * 80)
print("📊 RESULTS - BOTH-OUTCOME ARBITRAGE")
print("=" * 80)

if not both_outcome_opps:
    print("\n❌ NO both-outcome arbitrage found")
    print("   (Even with corrected 3% fee hurdle)")
else:
    print(f"\n🎯 FOUND {len(both_outcome_opps)} BOTH-OUTCOME OPPORTUNITIES!")
    both_outcome_opps.sort(key=lambda x: x['profit_pct'], reverse=True)
    
    for i, opp in enumerate(both_outcome_opps[:10], 1):
        print(f"\n💰 Opportunity #{i}: {opp['game']}")
        print(f"   Bet 1: ${opp['price1']:.4f} on {opp['bet1']}")
        print(f"   Bet 2: ${opp['price2']:.4f} on {opp['bet2']}")
        print(f"   Total Cost: ${opp['total_cost']:.4f}")
        print(f"   Gross Profit: ${opp['gross_profit']:.4f}")
        print(f"   Fees: ${opp['fees']:.4f}")
        print(f"   NET PROFIT: ${opp['net_profit']:.4f} ({opp['profit_pct']:.2f}%)")
        print(f"   Volumes: ${opp['vol1']:,.0f} / ${opp['vol2']:,.0f}")
    
    if len(both_outcome_opps) > 10:
        print(f"\n   ... and {len(both_outcome_opps) - 10} more")

print("\n" + "=" * 80)
print("📊 RESULTS - SAME-CONTRACT ARBITRAGE")
print("=" * 80)

if not same_contract_opps:
    print("\n❌ NO same-contract arbitrage found")
    print("   (No instances where Kalshi_bid > Poly_ask or vice versa)")
else:
    print(f"\n🔥 FOUND {len(same_contract_opps)} SAME-CONTRACT OPPORTUNITIES!")
    same_contract_opps.sort(key=lambda x: x['profit_pct'], reverse=True)
    
    for i, opp in enumerate(same_contract_opps[:10], 1):
        print(f"\n⚡ Opportunity #{i}: {opp['game']}")
        print(f"   Team: {opp['team']}")
        print(f"   Strategy: {opp['direction']}")
        print(f"   ")
        print(f"   SELL on {opp['sell_platform']} @ ${opp['sell_price']:.4f}")
        print(f"   BUY on {opp['buy_platform']} @ ${opp['buy_price']:.4f}")
        print(f"   ")
        print(f"   Gross: ${opp['gross']:.4f} ({opp['gross']*100:.2f}%)")
        print(f"   Fees:  ${opp['fees']:.4f}")
        print(f"   NET:   ${opp['net']:.4f} ({opp['profit_pct']:.2f}%)")
        print(f"   ")
        print(f"   Kalshi spread: ${opp['spread_k']:.4f}")
        print(f"   Poly spread:   ${opp['spread_p']:.4f}")
        print(f"   Volumes: K=${opp['k_vol']:,.0f} | P=${opp['p_vol']:,.0f}")
    
    if len(same_contract_opps) > 10:
        print(f"\n   ... and {len(same_contract_opps) - 10} more")

print("\n" + "=" * 80)
print("📊 SUMMARY")
print("=" * 80)
print(f"\nBoth-Outcome Opportunities:  {len(both_outcome_opps)}")
print(f"Same-Contract Opportunities: {len(same_contract_opps)}")
print(f"\nTOTAL OPPORTUNITIES FOUND:   {len(both_outcome_opps) + len(same_contract_opps)}")

if same_contract_opps:
    avg_profit = sum(o['profit_pct'] for o in same_contract_opps) / len(same_contract_opps)
    max_profit = max(o['profit_pct'] for o in same_contract_opps)
    print(f"\nSame-Contract Stats:")
    print(f"  Average Profit: {avg_profit:.2f}%")
    print(f"  Best Profit:    {max_profit:.2f}%")

print("\n" + "=" * 80)
print("✅ Analysis complete with CORRECTED fees!")
print("=" * 80)

