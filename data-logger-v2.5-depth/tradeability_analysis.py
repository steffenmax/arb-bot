#!/usr/bin/env python3
"""
Comprehensive Arbitrage Tradeability Analysis for Panthers vs Bucs

Analyzes:
1. All arbitrage opportunities >= 1%
2. Duration of each opportunity
3. Available liquidity/volume
4. Realistic trade execution scenarios
"""

import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict

DB_PATH = "data/market_data.db"
EVENT_ID = "kxnflgame_26jan04cartb_car"
MIN_PROFIT_THRESHOLD = 0.001  # 0.1% (to see all opportunities)

# Kalshi fees
KALSHI_MAKER_FEE = 0.00  # 0% maker fee
KALSHI_TAKER_FEE = 0.03  # 3% taker fee (conservative)

# Polymarket fees
POLYMARKET_FEE = 0.00  # 0% trading fee
ON_CHAIN_COST = 0.002  # 0.2% for gas/on-chain friction

print("=" * 100)
print("🏈 PANTHERS vs BUCCANEERS - ARBITRAGE TRADEABILITY ANALYSIS")
print("=" * 100)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# Get all snapshots for this game
cursor = conn.cursor()
cursor.execute("""
    SELECT 
        platform,
        market_side,
        yes_price,
        yes_bid,
        yes_ask,
        no_bid,
        no_ask,
        volume,
        timestamp,
        id
    FROM price_snapshots
    WHERE event_id = ?
    ORDER BY timestamp ASC
""", (EVENT_ID,))

all_snapshots = cursor.fetchall()

print(f"\n📊 DATA SUMMARY:")
print("-" * 100)
print(f"Total snapshots: {len(all_snapshots):,}")

# Group by timestamp to get synchronized price data
price_data = defaultdict(dict)

for snap in all_snapshots:
    ts = snap['timestamp']
    platform = snap['platform']
    side = snap['market_side']
    
    if platform == 'kalshi':
        if side == 'Carolina':
            price_data[ts]['kalshi_yes_ask'] = snap['yes_ask']
            price_data[ts]['kalshi_no_ask'] = snap['no_ask']
            price_data[ts]['kalshi_yes_bid'] = snap['yes_bid']
            price_data[ts]['kalshi_no_bid'] = snap['no_bid']
            price_data[ts]['kalshi_volume'] = snap['volume']
    elif platform == 'polymarket':
        if side == 'Panthers':
            price_data[ts]['poly_panthers'] = snap['yes_price']
        elif side == 'Buccaneers':
            price_data[ts]['poly_bucs'] = snap['yes_price']
        
        # Volume is the same for both teams (total market volume)
        if 'poly_volume' not in price_data[ts]:
            price_data[ts]['poly_volume'] = snap['volume']

# Find arbitrage opportunities
print(f"\n🔍 SCANNING FOR ARBITRAGE OPPORTUNITIES (>= {MIN_PROFIT_THRESHOLD*100:.1f}%)...")
print("-" * 100)

opportunities = []

for ts, prices in sorted(price_data.items()):
    # Need all 4 prices for analysis
    if all(k in prices for k in ['kalshi_yes_ask', 'kalshi_no_ask', 'poly_panthers', 'poly_bucs']):
        
        # Strategy 1: Buy Kalshi YES (Panthers) + Buy Poly Bucs
        combo1_total = prices['kalshi_yes_ask'] + prices['poly_bucs']
        combo1_gross_profit = 1.0 - combo1_total
        
        # Calculate net profit after fees (conservative: assume taker on both)
        kalshi_cost = prices['kalshi_yes_ask']
        poly_cost = prices['poly_bucs']
        kalshi_fee = kalshi_cost * KALSHI_TAKER_FEE
        poly_fee = poly_cost * ON_CHAIN_COST
        combo1_net_profit = combo1_gross_profit - kalshi_fee - poly_fee
        
        if combo1_gross_profit >= MIN_PROFIT_THRESHOLD:
            opportunities.append({
                'timestamp': ts,
                'strategy': 'Kalshi YES (Panthers) + Poly Bucs',
                'kalshi_side': 'YES Panthers',
                'kalshi_price': prices['kalshi_yes_ask'],
                'poly_side': 'Buccaneers',
                'poly_price': prices['poly_bucs'],
                'gross_profit_pct': combo1_gross_profit * 100,
                'net_profit_pct': combo1_net_profit * 100,
                'kalshi_volume': prices.get('kalshi_volume', 0),
                'poly_volume': prices.get('poly_volume', 0)
            })
        
        # Strategy 2: Buy Kalshi NO (Bucs) + Buy Poly Panthers
        combo2_total = prices['kalshi_no_ask'] + prices['poly_panthers']
        combo2_gross_profit = 1.0 - combo2_total
        
        kalshi_cost2 = prices['kalshi_no_ask']
        poly_cost2 = prices['poly_panthers']
        kalshi_fee2 = kalshi_cost2 * KALSHI_TAKER_FEE
        poly_fee2 = poly_cost2 * ON_CHAIN_COST
        combo2_net_profit = combo2_gross_profit - kalshi_fee2 - poly_fee2
        
        if combo2_gross_profit >= MIN_PROFIT_THRESHOLD:
            opportunities.append({
                'timestamp': ts,
                'strategy': 'Kalshi NO (Bucs) + Poly Panthers',
                'kalshi_side': 'NO Carolina (= Bucs)',
                'kalshi_price': prices['kalshi_no_ask'],
                'poly_side': 'Panthers',
                'poly_price': prices['poly_panthers'],
                'gross_profit_pct': combo2_gross_profit * 100,
                'net_profit_pct': combo2_net_profit * 100,
                'kalshi_volume': prices.get('kalshi_volume', 0),
                'poly_volume': prices.get('poly_volume', 0)
            })

print(f"\n✅ Found {len(opportunities):,} arbitrage opportunities")

if not opportunities:
    print("\n❌ No arbitrage opportunities found >= 1%")
    conn.close()
    exit()

# Analyze opportunity windows (consecutive opportunities = same window)
print(f"\n⏱️  ANALYZING OPPORTUNITY WINDOWS...")
print("-" * 100)

windows = []
current_window = None

for opp in opportunities:
    opp_time = datetime.fromisoformat(opp['timestamp'].replace('Z', ''))
    
    if current_window is None:
        # Start new window
        current_window = {
            'start': opp_time,
            'end': opp_time,
            'strategy': opp['strategy'],
            'opportunities': [opp],
            'min_net_profit': opp['net_profit_pct'],
            'max_net_profit': opp['net_profit_pct'],
            'avg_kalshi_volume': opp['kalshi_volume'],
            'avg_poly_volume': opp['poly_volume']
        }
    else:
        # Check if this is part of the same window (within 10 seconds and same strategy)
        time_diff = (opp_time - current_window['end']).total_seconds()
        
        if time_diff <= 10 and opp['strategy'] == current_window['strategy']:
            # Extend current window
            current_window['end'] = opp_time
            current_window['opportunities'].append(opp)
            current_window['min_net_profit'] = min(current_window['min_net_profit'], opp['net_profit_pct'])
            current_window['max_net_profit'] = max(current_window['max_net_profit'], opp['net_profit_pct'])
        else:
            # Close current window and start new one
            current_window['duration'] = (current_window['end'] - current_window['start']).total_seconds()
            windows.append(current_window)
            
            current_window = {
                'start': opp_time,
                'end': opp_time,
                'strategy': opp['strategy'],
                'opportunities': [opp],
                'min_net_profit': opp['net_profit_pct'],
                'max_net_profit': opp['net_profit_pct'],
                'avg_kalshi_volume': opp['kalshi_volume'],
                'avg_poly_volume': opp['poly_volume']
            }

# Don't forget the last window
if current_window:
    current_window['duration'] = (current_window['end'] - current_window['start']).total_seconds()
    windows.append(current_window)

print(f"\n📈 ARBITRAGE WINDOWS DETECTED: {len(windows)}")
print("-" * 100)

for i, window in enumerate(windows, 1):
    print(f"\n🎯 Window #{i}")
    print(f"   Strategy: {window['strategy']}")
    print(f"   Start:    {window['start'].strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   End:      {window['end'].strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Duration: {window['duration']:.1f} seconds")
    print(f"   Snapshots: {len(window['opportunities'])}")
    print(f"   Net Profit Range: {window['min_net_profit']:.2f}% - {window['max_net_profit']:.2f}%")
    print(f"   Avg Kalshi Volume: ${window['avg_kalshi_volume']:,.2f}")
    print(f"   Avg Poly Volume: ${window['avg_poly_volume']:,.2f}")

# Calculate tradeability
print("\n" + "=" * 100)
print("💰 TRADEABILITY ANALYSIS")
print("=" * 100)

print("\n📊 SUMMARY STATISTICS:")
print("-" * 100)
total_duration = sum(w['duration'] for w in windows)
avg_duration = total_duration / len(windows) if windows else 0
max_duration = max(w['duration'] for w in windows) if windows else 0
min_duration = min(w['duration'] for w in windows) if windows else 0

print(f"Total windows: {len(windows)}")
print(f"Total opportunity time: {total_duration:.1f} seconds ({total_duration/60:.1f} minutes)")
print(f"Average window duration: {avg_duration:.1f} seconds")
print(f"Longest window: {max_duration:.1f} seconds")
print(f"Shortest window: {min_duration:.1f} seconds")

# Find best opportunities
best_windows = sorted(windows, key=lambda w: w['max_net_profit'], reverse=True)[:5]

print("\n🔥 TOP 5 MOST PROFITABLE WINDOWS:")
print("-" * 100)
for i, window in enumerate(best_windows, 1):
    print(f"\n#{i} - {window['strategy']}")
    print(f"    Time: {window['start'].strftime('%H:%M:%S')} - {window['end'].strftime('%H:%M:%S')}")
    print(f"    Duration: {window['duration']:.1f}s")
    print(f"    Max Net Profit: {window['max_net_profit']:.2f}%")
    print(f"    Volume: Kalshi ${window['avg_kalshi_volume']:,.0f} | Poly ${window['avg_poly_volume']:,.0f}")

# Realistic execution analysis
print("\n" + "=" * 100)
print("🎯 REALISTIC EXECUTION SCENARIOS")
print("=" * 100)

print("\n⏱️  EXECUTION TIME REQUIREMENTS:")
print("-" * 100)
print("Human execution time: ~30-60 seconds (manual trading)")
print("Bot execution time: ~2-5 seconds (automated)")
print("")

tradeable_windows_human = [w for w in windows if w['duration'] >= 30]
tradeable_windows_bot = [w for w in windows if w['duration'] >= 5]

print(f"Windows tradeable by HUMAN (>= 30s): {len(tradeable_windows_human)} ({len(tradeable_windows_human)/len(windows)*100:.1f}%)")
print(f"Windows tradeable by BOT (>= 5s): {len(tradeable_windows_bot)} ({len(tradeable_windows_bot)/len(windows)*100:.1f}%)")

if tradeable_windows_human:
    print("\n💵 CAPITAL DEPLOYMENT SCENARIOS (Human-tradeable windows):")
    print("-" * 100)
    
    capital_tiers = [100, 500, 1000, 5000]
    
    for capital in capital_tiers:
        total_profit = 0
        for window in tradeable_windows_human:
            # Use minimum net profit for conservative estimate
            profit = capital * (window['min_net_profit'] / 100)
            total_profit += profit
        
        print(f"\n💰 ${capital:,} per trade:")
        print(f"    Number of trades: {len(tradeable_windows_human)}")
        print(f"    Total profit: ${total_profit:.2f}")
        print(f"    ROI: {(total_profit / capital) * 100:.1f}%")

conn.close()

print("\n" + "=" * 100)
print("✅ ANALYSIS COMPLETE")
print("=" * 100)

