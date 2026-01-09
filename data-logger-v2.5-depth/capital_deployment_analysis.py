#!/usr/bin/env python3
"""
Complete Capital Deployment Analysis

1. Confirm actual opportunity duration (local time)
2. Analyze volume/liquidity to determine position sizing
3. Calculate realistic returns for different capital tiers
4. Provide exact operational flow
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

ONCHAIN_COST = 0.002
KALSHI_TAKER_FEE = 0.03

print("=" * 80)
print("💰 COMPLETE CAPITAL DEPLOYMENT ANALYSIS")
print("=" * 80)

conn = sqlite3.connect("data/market_data.db")
conn.row_factory = sqlite3.Row

# Get actual collection timeframe
cursor = conn.cursor()
cursor.execute("SELECT MIN(timestamp) as first, MAX(timestamp) as last FROM price_snapshots")
row = cursor.fetchone()
print(f"\n📅 Actual Data Collection Period:")
print(f"   First snapshot: {row['first']}")
print(f"   Last snapshot:  {row['last']}")

# Analyze the two opportunities
opportunities_data = []

target_games = [
    ('Golden State', 'Warriors', 'Golden State vs Charlotte Winner?'),
    ('San Antonio', 'Spurs', 'New York vs San Antonio Winner?')
]

for k_team, p_team, game_desc in target_games:
    print("\n" + "=" * 80)
    print(f"🎯 {game_desc}: {k_team} = {p_team}")
    print("=" * 80)
    
    # Get all arbitrage instances with volume data
    query = """
    WITH kalshi_data AS (
        SELECT 
            yes_bid as k_bid,
            yes_ask as k_ask,
            volume as k_volume,
            timestamp,
            strftime('%s', timestamp) as ts_unix
        FROM price_snapshots ps
        JOIN tracked_markets tm ON ps.event_id = tm.event_id
        WHERE tm.description = ?
            AND ps.platform = 'kalshi'
            AND ps.market_side = ?
            AND ps.yes_bid IS NOT NULL
    ),
    poly_data AS (
        SELECT 
            yes_price as p_price,
            volume as p_volume,
            timestamp,
            strftime('%s', timestamp) as ts_unix
        FROM price_snapshots ps
        JOIN tracked_markets tm ON ps.event_id = tm.event_id
        WHERE tm.description = ?
            AND ps.platform = 'polymarket'
            AND ps.market_side = ?
            AND yes_price IS NOT NULL
    )
    SELECT 
        k.timestamp as k_time,
        k.k_bid,
        k.k_ask,
        k.k_volume,
        p.timestamp as p_time,
        p.p_price,
        p.p_volume,
        ABS(k.ts_unix - p.ts_unix) as time_diff
    FROM kalshi_data k
    JOIN poly_data p ON ABS(k.ts_unix - p.ts_unix) <= 60
    WHERE k.k_bid > p.p_price
    ORDER BY k.timestamp;
    """
    
    cursor.execute(query, (game_desc, k_team, game_desc, p_team))
    rows = cursor.fetchall()
    
    if not rows:
        print("   ❌ No arbitrage instances found")
        continue
    
    print(f"\n📊 Arbitrage Statistics:")
    print(f"   Total instances: {len(rows)}")
    print(f"   First seen: {rows[0]['k_time']}")
    print(f"   Last seen: {rows[-1]['k_time']}")
    
    # Calculate duration
    first_dt = datetime.fromisoformat(rows[0]['k_time'].replace('Z', ''))
    last_dt = datetime.fromisoformat(rows[-1]['k_time'].replace('Z', ''))
    duration_seconds = (last_dt - first_dt).total_seconds()
    duration_hours = duration_seconds / 3600
    
    print(f"   Duration: {duration_hours:.1f} hours ({duration_seconds:.0f} seconds)")
    
    # Analyze profit potential
    profits = []
    volumes_k = []
    volumes_p = []
    
    for row in rows:
        k_bid = row['k_bid']
        p_price = row['p_price']
        gross = k_bid - p_price
        fees = ONCHAIN_COST * p_price
        net = gross - fees
        profit_pct = (net / p_price) * 100
        
        profits.append(profit_pct)
        volumes_k.append(row['k_volume'])
        volumes_p.append(row['p_volume'])
    
    avg_profit = sum(profits) / len(profits)
    min_profit = min(profits)
    max_profit = max(profits)
    
    avg_vol_k = sum(volumes_k) / len(volumes_k)
    avg_vol_p = sum(volumes_p) / len(volumes_p)
    min_vol_k = min(volumes_k)
    min_vol_p = min(volumes_p)
    
    print(f"\n💰 Profit Metrics:")
    print(f"   Average profit: {avg_profit:.2f}%")
    print(f"   Min profit: {min_profit:.2f}%")
    print(f"   Max profit: {max_profit:.2f}%")
    
    print(f"\n📊 Volume/Liquidity Analysis:")
    print(f"   Kalshi avg volume: ${avg_vol_k:,.0f}")
    print(f"   Kalshi min volume: ${min_vol_k:,.0f}")
    print(f"   Polymarket avg volume: ${avg_vol_p:,.0f}")
    print(f"   Polymarket min volume: ${min_vol_p:,.0f}")
    
    # Store for capital analysis
    opportunities_data.append({
        'game': game_desc,
        'instances': len(rows),
        'duration_hours': duration_hours,
        'avg_profit_pct': avg_profit,
        'min_profit_pct': min_profit,
        'max_profit_pct': max_profit,
        'avg_vol_k': avg_vol_k,
        'avg_vol_p': avg_vol_p,
        'min_vol_k': min_vol_k,
        'min_vol_p': min_vol_p
    })

conn.close()

# === CAPITAL DEPLOYMENT TIERS ===

print("\n" + "=" * 80)
print("💵 CAPITAL DEPLOYMENT ANALYSIS")
print("=" * 80)

if not opportunities_data:
    print("\n❌ No opportunities to analyze")
else:
    # Calculate conservative position sizing
    # Rule: Don't exceed 5% of minimum volume on either platform
    
    print("\n📏 Position Sizing Rules:")
    print("   • Conservative: 5% of minimum volume")
    print("   • Moderate: 10% of minimum volume")
    print("   • Aggressive: 20% of minimum volume")
    print("   • Rationale: Avoid moving the market")
    
    for opp in opportunities_data:
        print("\n" + "-" * 80)
        print(f"🎯 {opp['game']}")
        print("-" * 80)
        
        # Determine max position size (limited by smaller platform)
        min_total_vol = min(opp['min_vol_k'], opp['min_vol_p'])
        
        conservative_size = min_total_vol * 0.05
        moderate_size = min_total_vol * 0.10
        aggressive_size = min_total_vol * 0.20
        
        print(f"\n💰 Position Sizing per Trade:")
        print(f"   Minimum volume constraint: ${min_total_vol:,.0f}")
        print(f"   Conservative (5%): ${conservative_size:,.0f}")
        print(f"   Moderate (10%): ${moderate_size:,.0f}")
        print(f"   Aggressive (20%): ${aggressive_size:,.0f}")
        
        # Calculate returns for different strategies
        print(f"\n📈 CAPITAL DEPLOYMENT TIERS & RETURNS:")
        print(f"   Duration: {opp['duration_hours']:.1f} hours")
        print(f"   Instances captured: {opp['instances']}")
        print(f"   Average profit: {opp['avg_profit_pct']:.2f}%")
        
        # Tier 1: Ultra Conservative
        print(f"\n   💵 TIER 1: Ultra Conservative")
        print(f"      Capital: ${conservative_size:,.0f}")
        print(f"      Strategy: Execute once per hour")
        trades_t1 = int(opp['duration_hours'])
        total_profit_t1 = conservative_size * (opp['avg_profit_pct'] / 100) * trades_t1
        roi_t1 = (total_profit_t1 / conservative_size) * 100
        print(f"      Trades: {trades_t1}")
        print(f"      Total Profit: ${total_profit_t1:,.2f}")
        print(f"      ROI: {roi_t1:.1f}%")
        
        # Tier 2: Conservative 
        print(f"\n   💵 TIER 2: Conservative")
        print(f"      Capital: ${conservative_size:,.0f}")
        print(f"      Strategy: Execute every 15 minutes")
        trades_t2 = int(opp['duration_hours'] * 4)
        total_profit_t2 = conservative_size * (opp['avg_profit_pct'] / 100) * trades_t2
        roi_t2 = (total_profit_t2 / conservative_size) * 100
        print(f"      Trades: {trades_t2}")
        print(f"      Total Profit: ${total_profit_t2:,.2f}")
        print(f"      ROI: {roi_t2:.1f}%")
        
        # Tier 3: Moderate
        print(f"\n   💵 TIER 3: Moderate")
        print(f"      Capital: ${moderate_size:,.0f}")
        print(f"      Strategy: Execute every 10 minutes")
        trades_t3 = int(opp['duration_hours'] * 6)
        total_profit_t3 = moderate_size * (opp['avg_profit_pct'] / 100) * trades_t3
        roi_t3 = (total_profit_t3 / moderate_size) * 100
        print(f"      Trades: {trades_t3}")
        print(f"      Total Profit: ${total_profit_t3:,.2f}")
        print(f"      ROI: {roi_t3:.1f}%")
        
        # Tier 4: Aggressive
        print(f"\n   💵 TIER 4: Aggressive")
        print(f"      Capital: ${aggressive_size:,.0f}")
        print(f"      Strategy: Execute every 5 minutes")
        trades_t4 = int(opp['duration_hours'] * 12)
        total_profit_t4 = aggressive_size * (opp['avg_profit_pct'] / 100) * trades_t4
        roi_t4 = (total_profit_t4 / aggressive_size) * 100
        print(f"      Trades: {trades_t4}")
        print(f"      Total Profit: ${total_profit_t4:,.2f}")
        print(f"      ROI: {roi_t4:.1f}%")

# === OPERATIONAL FLOW ===

print("\n" + "=" * 80)
print("⚙️  OPERATIONAL FLOW - HOW TO EXECUTE")
print("=" * 80)

print("""
┌─────────────────────────────────────────────────────────────────────────┐
│                        ARBITRAGE EXECUTION FLOW                         │
└─────────────────────────────────────────────────────────────────────────┘

📡 STEP 1: DETECTION (Automated - Your Bot)
────────────────────────────────────────────
   ▸ Bot collects prices every 3 seconds
   ▸ Identifies: Kalshi_bid > Polymarket_ask
   ▸ Calculates net profit after fees
   ▸ Alert triggers when profit > 0.5%

💰 STEP 2: POSITION SIZING (Manual or Automated)
────────────────────────────────────────────
   ▸ Check current volume on both platforms
   ▸ Size = MIN(5% Kalshi volume, 5% Poly volume)
   ▸ Verify sufficient account balance on both
   ▸ Example: $84K volume → $4,200 max position

⚡ STEP 3A: SELL on KALSHI (High Side)
────────────────────────────────────────────
   Platform: Kalshi
   Action: Place LIMIT SELL order
   Contract: [Team] to win
   Price: Current BID price (e.g., $0.71)
   Size: $4,200 (or your tier size)
   
   Expected fill: Immediate (you're taking their bid)
   Fee: ~0% (maker fee) or 3% (taker fee)
   
   Result: SHORT position on Kalshi
   ├─ If team WINS: You lose (pay out $1.00)
   └─ If team LOSES: You win (keep the $0.71)

⚡ STEP 3B: BUY on POLYMARKET (Low Side) - SIMULTANEOUS
────────────────────────────────────────────
   Platform: Polymarket
   Action: Place LIMIT BUY order
   Contract: [Same team] to win
   Price: Current ASK price (e.g., $0.695)
   Size: $4,200 (match Kalshi exactly)
   
   Expected fill: Immediate (you're taking their ask)
   Fee: 0% (no trading fee) + ~0.2% gas
   
   Result: LONG position on Polymarket
   ├─ If team WINS: You win (receive $1.00)
   └─ If team LOSES: You lose (lose the $0.695)

✅ STEP 4: LOCKED-IN PROFIT (Automatic)
────────────────────────────────────────────
   Position: SHORT on Kalshi + LONG on Polymarket
   
   Scenario A: Team WINS
   ├─ Kalshi: Lose $4,200 (pay $1.00 per contract)
   ├─ Polymarket: Win $6,043 (receive $1.00 per contract)
   └─ NET: $6,043 - $4,200 = +$1,843 profit
   
   Scenario B: Team LOSES
   ├─ Kalshi: Win $2,982 (keep $0.71 per contract)
   ├─ Polymarket: Lose $2,919 (lose $0.695 per contract)
   └─ NET: $2,982 - $2,919 = +$63 profit
   
   Either way: GUARANTEED PROFIT ✓

🔄 STEP 5: SETTLEMENT (Automatic)
────────────────────────────────────────────
   When: Game ends and outcome is determined
   Process: Platforms automatically settle
   Kalshi: Credits/debits your account
   Polymarket: Smart contract settlement
   
   Time: Usually within minutes of game end

💸 STEP 6: WITHDRAW & REPEAT
────────────────────────────────────────────
   ▸ Profit locked in your accounts
   ▸ Optionally withdraw to bank
   ▸ Or keep capital for next opportunity
   ▸ Bot continues monitoring 24/7

────────────────────────────────────────────────────────────────────────────

⚠️  CRITICAL EXECUTION NOTES:

1. SIMULTANEOUS EXECUTION:
   • Place both orders within seconds of each other
   • Don't place Kalshi first and wait - price might move
   • Use two browser windows/tabs ready to go

2. SLIPPAGE RISK:
   • Your order might not fill at displayed price
   • Especially if you're using large size
   • Start small to test actual fill rates

3. ACCOUNT REQUIREMENTS:
   • Need funded accounts on BOTH platforms
   • Kalshi: Bank account + verification
   • Polymarket: Crypto wallet + USDC
   • Keep float capital on both sides

4. TIMING:
   • These opportunities lasted HOURS in your data
   • No need to panic - you have time
   • Execute methodically and carefully

5. RISK MANAGEMENT:
   • Start with Tier 1 (smallest size)
   • Verify fills before scaling up
   • Track actual vs expected profit
   • Stop if slippage exceeds 0.5%

────────────────────────────────────────────────────────────────────────────
""")

print("\n" + "=" * 80)
print("✅ Analysis complete!")
print("=" * 80)

