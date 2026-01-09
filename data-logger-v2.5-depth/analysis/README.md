# Analysis Guide

This folder contains scripts for analyzing collected price data.

## Scripts

### `analyze_opportunities.py`

Analyzes price snapshots to find arbitrage opportunities.

**What it does:**
1. Loads all price data from the database
2. Finds Kalshi/Polymarket price pairs within a time window (default: 5 seconds)
3. Calculates arbitrage opportunities for complementary outcomes
4. Accounts for exchange fees (Kalshi 7%, Polymarket 2%)
5. Generates a detailed report

**Usage:**

```bash
# Basic analysis
python analyze_opportunities.py

# Custom database path
python analyze_opportunities.py --db /path/to/market_data.db

# Wider time matching window (10 seconds)
python analyze_opportunities.py --window 10
```

**Options:**
- `--db PATH` - Path to database file (default: `../data/market_data.db`)
- `--window SECONDS` - Time matching window in seconds (default: 5)

## Understanding the Analysis

### Arbitrage Calculation

For arbitrage to work, you need **complementary outcomes**:

✅ **Example 1: Opposite Teams**
- Buy Lakers to WIN on Kalshi
- Buy Celtics to WIN on Polymarket
- You're guaranteed to win on one side

✅ **Example 2: Opposite Outcomes**
- Buy Lakers YES on Kalshi  
- Buy Lakers NO on Polymarket
- You're guaranteed to win on one side

**Formula:**
```
Total Cost = Kalshi Price + Polymarket Price
Gross Profit = $1.00 - Total Cost
Kalshi Fee = Kalshi Price × 0.07
Polymarket Fee = Polymarket Price × 0.02
Net Profit = Gross Profit - Kalshi Fee - Polymarket Fee
```

**Opportunity exists when:** Total Cost < $1.00  
**Profitable after fees when:** Net Profit > $0

### Time Matching Window

The analysis matches Kalshi and Polymarket prices within a time window (default 5 seconds).

- **Narrower window (1-3s)**: More accurate price matching, fewer matches
- **Wider window (10-30s)**: More matches, but prices may have moved

If you're finding zero opportunities, try increasing the window:
```bash
python analyze_opportunities.py --window 10
```

### Reading the Report

**Overall Statistics:**
- Shows total opportunities found across all markets
- Profitability rate after fees

**Per-Market Analysis:**
- Data points collected for each market
- Number of time-matched pairs
- Best opportunity details (prices, profit, ROI)

**Conclusions:**
- Summary of whether profitable arbitrage exists
- Timing analysis (how long opportunities last)
- Recommendations

## What the Results Tell You

### Scenario 1: No Opportunities Found

```
❌ NO PROFITABLE ARBITRAGE OPPORTUNITIES FOUND
```

**Possible reasons:**
1. **Markets are efficient** - Prices stay aligned between platforms
2. **Fees are too high** - 9% total fees (7% + 2%) eliminate margins
3. **Not enough data** - Collect for longer (24-48 hours recommended)
4. **Time window too strict** - Try `--window 10` or `--window 15`
5. **Wrong markets compared** - Verify you're tracking complementary outcomes

**What to do:**
- Collect more data (run for 24-48 hours)
- Try different sports/events
- Check that you're comparing opposite outcomes
- Increase time matching window

### Scenario 2: Opportunities Found (Before Fees)

```
✅ FOUND 47 OPPORTUNITIES (0 PROFITABLE AFTER FEES)
```

**This means:**
- Arbitrage opportunities DO exist
- But 9% fees eliminate all profit

**What to do:**
- If you can negotiate lower fees, there may be profit potential
- Consider the opportunity cost of capital
- Look for larger price discrepancies

### Scenario 3: Profitable Opportunities Found

```
✅ FOUND 12 PROFITABLE OPPORTUNITIES
Average profit: $0.0234 per opportunity
Maximum profit: $0.0891
```

**This means:**
- Real arbitrage exists!
- Opportunities are small but profitable

**Important factors:**
1. **Profit size**: Is it worth the execution effort?
2. **Frequency**: How often do opportunities appear?
3. **Duration**: How long do they last? (check timing analysis)
4. **Execution risk**: Can you fill both sides before prices change?

**Timing Analysis:**
```
Average time between snapshots: 2.3 seconds
```

- **< 3 seconds**: Requires very fast execution, high risk
- **3-10 seconds**: Fast execution needed, moderate risk
- **> 10 seconds**: Normal execution should work

## Example Output

```
=======================================================================
ARBITRAGE ANALYSIS REPORT
=======================================================================

Overall Statistics:
  Markets analyzed:          3
  Total price snapshots:     847
  Opportunities found:       23
  Profitable opportunities:  8
  Profitability rate:        34.8%

─────────────────────────────────────────────────────────────────────
Per-Market Analysis:
─────────────────────────────────────────────────────────────────────

📊 Lakers vs Celtics - January 15, 2025
   Event ID: lakers_celtics_2025_01_15
   Data points: 142 Kalshi, 139 Polymarket
   Time-matched pairs: 134
   Opportunities: 8 total, 3 profitable
   Average profit: $0.0189
   Average ROI: 1.94%

   💰 Best Opportunity:
      Timestamp: 2025-01-15T18:23:47.123Z
      Strategy: Kalshi YES + Polymarket NO
      Kalshi price: $0.5200
      Polymarket price: $0.4500
      Total cost: $0.9700
      Fees: $0.0454
      Net profit: $0.0246
      ROI: 2.54%

=======================================================================
CONCLUSIONS
=======================================================================

✅ FOUND 3 PROFITABLE OPPORTUNITIES

   Average profit: $0.0189 per opportunity
   Maximum profit: $0.0246

   Timing Analysis:
   Average time between snapshots: 3.2 seconds
   Min time difference: 1.1 seconds
   Max time difference: 4.8 seconds

   ⏱️  Opportunities exist within 5-second windows
      Fast execution required, but feasible.

=======================================================================
```

## Next Steps After Analysis

### If No Opportunities Found:
1. Collect more data (run for longer)
2. Try different markets/sports
3. Verify your market configuration
4. Check that you're comparing complementary outcomes

### If Opportunities Found:
1. **Evaluate viability:**
   - Are profits large enough? (Consider minimum: $5-10 per trade)
   - Do opportunities appear frequently?
   - Can you execute fast enough?

2. **Calculate expected value:**
   - Opportunities per hour × Average profit
   - Factor in execution success rate
   - Consider slippage and partial fills

3. **Decide on next steps:**
   - Build execution system (if profitable)
   - Continue monitoring (if borderline)
   - Move on (if not profitable)

## Advanced Analysis

You can modify `analyze_opportunities.py` to:

- Export results to CSV for further analysis
- Plot opportunities over time
- Analyze by time of day
- Calculate opportunity duration
- Simulate execution with slippage

The database contains all raw data - you can run custom SQL queries:

```python
import sqlite3

conn = sqlite3.connect('data/market_data.db')
cursor = conn.cursor()

# Custom query example
cursor.execute("""
    SELECT event_id, platform, AVG(yes_price) as avg_price
    FROM price_snapshots
    GROUP BY event_id, platform
""")

for row in cursor.fetchall():
    print(row)
```

## Troubleshooting

**"Database not found"**
- Make sure you've run `data_logger.py` first
- Check the database path with `--db` option

**"No price data found"**
- Verify data collection completed successfully
- Check `collection_logs` table in database

**"All prices are None"**
- API may have returned invalid data
- Check the raw_data fields in price_snapshots table
- Verify market IDs are correct

**Very few matched pairs**
- Your collection interval may be too long
- Try collecting more frequently (30 seconds recommended)
- Or increase the time window: `--window 10`

