#!/usr/bin/env python3
"""
Real-Time Arbitrage Analysis with Orderbook Depth

Analyzes collected data to find arbitrage opportunities accounting for:
- Orderbook depth and slippage
- Realistic tradeable sizes
- Fee structures
- Opportunity duration
"""

import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict

def analyze_arbitrage_with_depth(db_path="data/market_data.db", lookback_minutes=120):
    """Analyze arbitrage opportunities using orderbook depth data"""
    
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    
    print("=" * 100)
    print("🔍 ARBITRAGE ANALYSIS WITH ORDERBOOK DEPTH")
    print("=" * 100)
    
    # Get time range
    cursor = conn.execute("SELECT MIN(timestamp), MAX(timestamp) FROM price_snapshots")
    first, last = cursor.fetchone()
    print(f"\nData Range: {first} to {last}")
    
    cutoff = (datetime.now() - timedelta(minutes=lookback_minutes)).isoformat()
    
    print(f"Analyzing last {lookback_minutes} minutes (since {cutoff})")
    
    # Find opportunities where Kalshi + Polymarket < 1.0 (both-outcome arbitrage)
    # For each game, we need to match:
    # - Kalshi team A YES + Polymarket team B YES (opposite teams)
    # - Check if their sum < 1.0
    
    print("\n" + "=" * 100)
    print("📊 FINDING ARBITRAGE OPPORTUNITIES")
    print("=" * 100)
    
    # Get all unique games
    cursor = conn.execute("""
        SELECT DISTINCT event_id 
        FROM price_snapshots 
        WHERE timestamp > ?
    """, (cutoff,))
    
    games = [row[0] for row in cursor]
    print(f"\nAnalyzing {len(games)} games...")
    
    opportunities = []
    
    for game in games:
        # Get synchronized snapshots (within 5 seconds of each other)
        cursor = conn.execute("""
            WITH kalshi_data AS (
                SELECT 
                    id as snapshot_id,
                    market_side,
                    yes_ask,
                    timestamp
                FROM price_snapshots
                WHERE event_id = ? 
                AND platform = 'kalshi'
                AND yes_ask IS NOT NULL
                AND timestamp > ?
            ),
            poly_data AS (
                SELECT 
                    id as snapshot_id,
                    market_side,
                    yes_ask,
                    timestamp
                FROM price_snapshots
                WHERE event_id = ?
                AND platform = 'polymarket'
                AND yes_ask IS NOT NULL
                AND timestamp > ?
            )
            SELECT 
                k.snapshot_id as kalshi_snapshot,
                k.market_side as kalshi_side,
                k.yes_ask as kalshi_ask,
                k.timestamp as kalshi_time,
                p.snapshot_id as poly_snapshot,
                p.market_side as poly_side,
                p.yes_ask as poly_ask,
                p.timestamp as poly_time
            FROM kalshi_data k
            CROSS JOIN poly_data p
            WHERE k.market_side != p.market_side
            AND ABS(
                (julianday(k.timestamp) - julianday(p.timestamp)) * 86400
            ) < 5
            AND (k.yes_ask + p.yes_ask) < 0.98
            ORDER BY k.timestamp DESC
        """, (game, cutoff, game, cutoff))
        
        for row in cursor:
            # Calculate profit
            total_cost = row['kalshi_ask'] + row['poly_ask']
            gross_profit = 1.0 - total_cost
            gross_profit_pct = (gross_profit / total_cost) * 100
            
            # Get orderbook depth for both sides
            kalshi_depth = get_orderbook_depth(conn, row['kalshi_snapshot'])
            poly_depth = get_orderbook_depth(conn, row['poly_snapshot'])
            
            # Calculate tradeable sizes at different capital levels
            trade_analysis = analyze_trade_sizes(
                kalshi_depth, poly_depth, 
                row['kalshi_ask'], row['poly_ask']
            )
            
            opportunities.append({
                'game': game,
                'kalshi_side': row['kalshi_side'],
                'kalshi_ask': row['kalshi_ask'],
                'kalshi_snapshot': row['kalshi_snapshot'],
                'poly_side': row['poly_side'],
                'poly_ask': row['poly_ask'],
                'poly_snapshot': row['poly_snapshot'],
                'total_cost': total_cost,
                'gross_profit_pct': gross_profit_pct,
                'timestamp': row['kalshi_time'],
                'trade_analysis': trade_analysis
            })
    
    # Display opportunities
    if not opportunities:
        print("\n❌ No arbitrage opportunities found in the analyzed period.")
        print("\nThis could mean:")
        print("  - Markets are efficient (no mispricing)")
        print("  - Spreads are too wide")
        print("  - Opportunities existed but were too brief to capture")
        return
    
    print(f"\n✅ Found {len(opportunities)} potential arbitrage opportunities!")
    print("\n" + "=" * 100)
    print("📋 OPPORTUNITY DETAILS")
    print("=" * 100)
    
    # Sort by profit
    opportunities.sort(key=lambda x: x['gross_profit_pct'], reverse=True)
    
    for i, opp in enumerate(opportunities[:20], 1):  # Show top 20
        print(f"\n{'─' * 100}")
        print(f"Opportunity #{i} - {opp['timestamp']}")
        print(f"{'─' * 100}")
        print(f"Game: {opp['game']}")
        print(f"\n💰 Trade Structure:")
        print(f"  Buy {opp['kalshi_side']} on Kalshi: ${opp['kalshi_ask']:.3f}")
        print(f"  Buy {opp['poly_side']} on Polymarket: ${opp['poly_ask']:.3f}")
        print(f"  Total Cost: ${opp['total_cost']:.3f}")
        print(f"  Gross Profit: {opp['gross_profit_pct']:.2f}%")
        
        if opp['trade_analysis']:
            print(f"\n📊 Tradeable Sizes (with VWAP from orderbook):")
            for size_info in opp['trade_analysis']:
                print(f"  ${size_info['capital']:>6,}: "
                      f"Kalshi ${size_info['kalshi_vwap']:.3f}, "
                      f"Poly ${size_info['poly_vwap']:.3f}, "
                      f"Total: ${size_info['total_vwap']:.3f}, "
                      f"Profit: {size_info['profit_pct']:>5.2f}% "
                      f"({size_info['status']})")
    
    # Summary statistics
    print("\n\n" + "=" * 100)
    print("📈 SUMMARY STATISTICS")
    print("=" * 100)
    
    total_opps = len(opportunities)
    avg_profit = sum(o['gross_profit_pct'] for o in opportunities) / total_opps
    max_profit = max(o['gross_profit_pct'] for o in opportunities)
    
    print(f"\nTotal opportunities: {total_opps}")
    print(f"Average profit: {avg_profit:.2f}%")
    print(f"Maximum profit: {max_profit:.2f}%")
    
    # Duration analysis
    print(f"\n⏱️  Duration Analysis:")
    opp_by_game = defaultdict(list)
    for opp in opportunities:
        opp_by_game[opp['game']].append(opp)
    
    for game, game_opps in opp_by_game.items():
        if len(game_opps) > 1:
            timestamps = [datetime.fromisoformat(o['timestamp'].replace('Z', '')) for o in game_opps]
            duration = (max(timestamps) - min(timestamps)).total_seconds()
            print(f"  {game[:30]}: {len(game_opps)} opportunities over {duration:.0f} seconds")
    
    conn.close()


def get_orderbook_depth(conn, snapshot_id):
    """Get orderbook depth for a snapshot"""
    cursor = conn.execute("""
        SELECT side, order_type, level, price, size
        FROM orderbook_snapshots
        WHERE snapshot_id = ?
        ORDER BY side, order_type, level
    """, (snapshot_id,))
    
    depth = {'yes': {'bid': [], 'ask': []}, 'no': {'bid': [], 'ask': []}}
    
    for row in cursor:
        depth[row['side']][row['order_type']].append({
            'level': row['level'],
            'price': row['price'],
            'size': row['size']
        })
    
    return depth


def analyze_trade_sizes(kalshi_depth, poly_depth, kalshi_top_ask, poly_top_ask):
    """Analyze tradeable sizes at different capital levels"""
    
    # Test capital levels
    capital_levels = [100, 500, 1000, 2000, 5000]
    
    results = []
    
    for capital in capital_levels:
        # For Kalshi: capital buys (capital / kalshi_price) contracts
        # For Poly: same
        # But we need to check orderbook depth
        
        kalshi_contracts = capital / kalshi_top_ask
        poly_contracts = capital / poly_top_ask
        
        # Calculate VWAP from orderbook
        kalshi_vwap = calculate_vwap(kalshi_depth, kalshi_contracts, 'ask')
        poly_vwap = calculate_vwap(poly_depth, poly_contracts, 'ask')
        
        if kalshi_vwap and poly_vwap:
            total_cost = kalshi_vwap + poly_vwap
            gross_profit = 1.0 - total_cost
            profit_pct = (gross_profit / total_cost) * 100
            
            status = "✅" if profit_pct > 2 else "⚠️" if profit_pct > 0 else "❌"
            
            results.append({
                'capital': capital,
                'kalshi_vwap': kalshi_vwap,
                'poly_vwap': poly_vwap,
                'total_vwap': total_cost,
                'profit_pct': profit_pct,
                'status': status
            })
        else:
            results.append({
                'capital': capital,
                'kalshi_vwap': 0,
                'poly_vwap': 0,
                'total_vwap': 0,
                'profit_pct': 0,
                'status': '❌ Insufficient liquidity'
            })
    
    return results


def calculate_vwap(orderbook_depth, target_contracts, order_type='ask'):
    """Calculate VWAP for a target number of contracts"""
    
    # Get the relevant orderbook side (yes ask for buying)
    orders = orderbook_depth.get('yes', {}).get(order_type, [])
    
    if not orders:
        return None
    
    total_cost = 0
    filled = 0
    
    for order in orders:
        if filled >= target_contracts:
            break
        
        fill_size = min(order['size'], target_contracts - filled)
        total_cost += order['price'] * fill_size
        filled += fill_size
    
    if filled == 0:
        return None
    
    return total_cost / filled


if __name__ == "__main__":
    import sys
    
    lookback = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    
    try:
        analyze_arbitrage_with_depth(lookback_minutes=lookback)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

