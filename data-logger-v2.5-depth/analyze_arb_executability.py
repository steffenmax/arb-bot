#!/usr/bin/env python3
"""
Analyze arbitrage opportunity executability based on top-of-book liquidity
Shows how much you could actually trade at the displayed prices
"""

import sqlite3
import json
from datetime import datetime, timedelta

DB_PATH = "data/market_data.db"
CONFIG_PATH = "config/markets.json"

def get_top_of_book_liquidity(conn, event_id, platform, team, max_age_seconds=10):
    """Get liquidity available at the best ask price"""
    cutoff = (datetime.now() - timedelta(seconds=max_age_seconds)).isoformat()
    
    # Get the latest price snapshot to know what the current ask is
    cursor = conn.execute("""
        SELECT yes_ask, no_ask, market_side
        FROM price_snapshots
        WHERE event_id = ?
        AND platform = ?
        AND market_side = ?
        AND timestamp > ?
        ORDER BY timestamp DESC
        LIMIT 1
    """, (event_id, platform, team, cutoff))
    
    price_row = cursor.fetchone()
    if not price_row:
        return None
    
    yes_ask, no_ask, market_side = price_row
    
    # Get the most recent snapshot_id for this market
    cursor = conn.execute("""
        SELECT snapshot_id
        FROM orderbook_snapshots
        WHERE event_id = ?
        AND platform = ?
        AND side = ?
        AND timestamp > ?
        ORDER BY timestamp DESC
        LIMIT 1
    """, (event_id, platform, team, cutoff))
    
    snapshot_row = cursor.fetchone()
    if not snapshot_row:
        return None
    
    snapshot_id = snapshot_row[0]
    
    # Get all ask orders from this snapshot (order_type = 'ask')
    cursor = conn.execute("""
        SELECT price, size
        FROM orderbook_snapshots
        WHERE snapshot_id = ?
        AND order_type = 'ask'
        ORDER BY price ASC
    """, (snapshot_id,))
    
    asks = cursor.fetchall()
    
    # Find liquidity at the yes_ask price (what we want to buy)
    yes_liquidity = 0
    for price, size in asks:
        # Match the price (with small tolerance for floating point)
        if abs(price - yes_ask) < 0.001:
            yes_liquidity = price * size  # Convert to dollar amount
            break
    
    return {
        'ask_price': yes_ask,
        'liquidity_at_ask': yes_liquidity,
        'team': team
    }

def analyze_arbitrage_executability():
    """Analyze current arbitrage opportunities for executability"""
    
    # Load config
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
        markets = {m['event_id']: m for m in config.get('markets', [])}
    
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    
    print("=" * 100)
    print("ARBITRAGE EXECUTABILITY ANALYSIS - TOP OF BOOK LIQUIDITY")
    print("=" * 100)
    print("\nChecking all markets for arbitrage opportunities...\n")
    
    opportunities = []
    
    for event_id, market_config in markets.items():
        team_a = market_config['teams']['team_a']
        team_b = market_config['teams']['team_b']
        description = market_config['description']
        
        # Get Kalshi data for both teams
        kalshi_a = get_top_of_book_liquidity(conn, event_id, 'kalshi', team_a)
        kalshi_b = get_top_of_book_liquidity(conn, event_id, 'kalshi', team_b)
        
        # Get Polymarket data for both teams (they use nicknames)
        poly_a = get_top_of_book_liquidity(conn, event_id, 'polymarket', team_a)
        poly_b = get_top_of_book_liquidity(conn, event_id, 'polymarket', team_b)
        
        # Check both combinations
        combinations = []
        
        # Combo 1: Kalshi A + Poly B
        if kalshi_a and poly_b:
            total = kalshi_a['ask_price'] + poly_b['ask_price']
            if total < 1.0:
                combinations.append({
                    'kalshi_side': team_a,
                    'kalshi_price': kalshi_a['ask_price'],
                    'kalshi_liq': kalshi_a['liquidity_at_ask'],
                    'poly_side': team_b,
                    'poly_price': poly_b['ask_price'],
                    'poly_liq': poly_b['liquidity_at_ask'],
                    'total': total,
                    'profit_pct': ((1.0 - total) / total) * 100
                })
        
        # Combo 2: Kalshi B + Poly A
        if kalshi_b and poly_a:
            total = kalshi_b['ask_price'] + poly_a['ask_price']
            if total < 1.0:
                combinations.append({
                    'kalshi_side': team_b,
                    'kalshi_price': kalshi_b['ask_price'],
                    'kalshi_liq': kalshi_b['liquidity_at_ask'],
                    'poly_side': team_a,
                    'poly_price': poly_a['ask_price'],
                    'poly_liq': poly_a['liquidity_at_ask'],
                    'total': total,
                    'profit_pct': ((1.0 - total) / total) * 100
                })
        
        if combinations:
            best = min(combinations, key=lambda x: x['total'])
            opportunities.append({
                'game': description,
                'combo': best
            })
    
    conn.close()
    
    if not opportunities:
        print("❌ No arbitrage opportunities detected at this moment.\n")
        return
    
    print(f"✅ Found {len(opportunities)} arbitrage opportunity(ies)!\n")
    
    for i, opp in enumerate(opportunities, 1):
        game = opp['game']
        c = opp['combo']
        
        print(f"{'='*100}")
        print(f"OPPORTUNITY #{i}: {game}")
        print(f"{'='*100}")
        
        print(f"\n📊 TRADE STRUCTURE:")
        print(f"  Kalshi:     Buy {c['kalshi_side']:<20} @ ${c['kalshi_price']:.3f}")
        print(f"  Polymarket: Buy {c['poly_side']:<20} @ ${c['poly_price']:.3f}")
        print(f"  Total Cost: ${c['total']:.4f}")
        print(f"  Profit:     {c['profit_pct']:.2f}%")
        
        print(f"\n💰 TOP-OF-BOOK LIQUIDITY (at exact ask prices):")
        print(f"  Kalshi {c['kalshi_side']:<15} @ ${c['kalshi_price']:.3f}: ${c['kalshi_liq']:.2f}")
        print(f"  Polymarket {c['poly_side']:<12} @ ${c['poly_price']:.3f}: ${c['poly_liq']:.2f}")
        
        # Calculate max executable
        min_liq = min(c['kalshi_liq'], c['poly_liq'])
        bottleneck = 'Kalshi' if c['kalshi_liq'] < c['poly_liq'] else 'Polymarket'
        
        print(f"\n🎯 EXECUTABILITY:")
        print(f"  Bottleneck: {bottleneck}")
        print(f"  Max Trade Size: ${min_liq:.2f}")
        
        if min_liq > 0:
            # Calculate how many contracts and profit
            kalshi_contracts = min_liq / c['kalshi_price']
            poly_contracts = min_liq / c['poly_price']
            
            # Investment calculation
            total_investment = (kalshi_contracts * c['kalshi_price']) + (poly_contracts * c['poly_price'])
            guaranteed_payout = max(kalshi_contracts, poly_contracts)  # Winner pays $1 per contract
            profit = guaranteed_payout - total_investment
            
            print(f"  Contracts: ~{min(kalshi_contracts, poly_contracts):.0f}")
            print(f"  Investment: ${total_investment:.2f}")
            print(f"  Guaranteed Payout: ${guaranteed_payout:.2f}")
            print(f"  Risk-Free Profit: ${profit:.2f}")
            
            # Executability rating
            if min_liq >= 100:
                rating = "🟢 HIGHLY EXECUTABLE"
            elif min_liq >= 50:
                rating = "🟡 MODERATELY EXECUTABLE"
            elif min_liq >= 20:
                rating = "🟠 SMALL TRADE ONLY"
            else:
                rating = "🔴 VERY LIMITED LIQUIDITY"
            
            print(f"  Rating: {rating}")
        else:
            print(f"  Rating: 🔴 NOT EXECUTABLE (No liquidity at ask price)")
        
        print()
    
    print(f"{'='*100}")
    print(f"Analysis complete. Data from last 10 seconds.")
    print(f"{'='*100}\n")

if __name__ == "__main__":
    analyze_arbitrage_executability()

