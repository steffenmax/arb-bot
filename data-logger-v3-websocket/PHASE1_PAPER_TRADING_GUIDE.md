# Phase 1: Paper Trading Guide

**Status**: ✅ Ready to Start  
**Date**: January 6, 2026  
**Duration**: Recommended 24-48 hours  
**Risk Level**: ⚠️ ZERO (No real money at risk)

## What is Paper Trading?

Paper trading is **simulation mode** where the bot:
- ✅ Connects to **real live data** via WebSockets
- ✅ Detects **real arbitrage opportunities** in real-time
- ✅ Applies **real risk management** rules
- ✅ Logs what trades **WOULD** be executed
- ❌ **DOES NOT** place any real orders
- ✅ Tracks **simulated P&L**

## Why Start with Paper Trading?

### 1. **Learn the System** 🎓
- Understand how opportunities are detected
- See what edge thresholds trigger trades
- Learn how risk limits work
- Get familiar with the dashboard

### 2. **Build Confidence** 💪
- Verify the bot detects real opportunities
- Check that edge calculations make sense
- Ensure WebSocket connections are stable
- Validate that profitability is achievable

### 3. **Collect Data** 📊
- Build fill rate history
- Calibrate race model parameters
- Measure opportunity frequency
- Estimate realistic returns

### 4. **Zero Risk** 🛡️
- No API keys needed for execution
- No real money at risk
- No order errors to worry about
- Perfect for testing

## Step-by-Step Instructions

### Step 1: Verify Setup ✓

Make sure you have:
- [x] Virtual environment activated
- [x] All dependencies installed (`../venv/bin/python3 test_setup.py`)
- [x] Markets configured in `config/markets.json`
- [x] API credentials in `.env` (for data only, not execution)

```bash
cd /Users/maxsteffen/Desktop/arbitrage_bot/data-logger-v3-websocket

# Quick test
../venv/bin/python3 test_setup.py
```

Expected output: All components should show ✓

### Step 2: Review Paper Trading Config ⚙️

Check `config/bot_config_paper.json`:

```json
{
  "mode": "maker_hedge",
  "paper_trading": true,              ← NO REAL ORDERS
  "execution_enabled": false,          ← DOUBLE SAFETY
  "scan_interval_s": 1.0,
  "stats_interval_s": 30,
  "risk_limits": {
    "max_trade_size_usd": 100,
    "min_edge_bps": 50,                ← Lower threshold to see more opps
    "max_slippage_bps": 300            ← More lenient for data collection
  }
}
```

**Key Settings**:
- `paper_trading: true` - Simulation mode enabled
- `min_edge_bps: 50` - Lower than live (100) to detect more opportunities
- `stats_interval_s: 30` - More frequent stats printing

### Step 3: Launch Paper Trading Bot 🚀

**Terminal 1** - Start the bot:

```bash
cd /Users/maxsteffen/Desktop/arbitrage_bot/data-logger-v3-websocket
./START_PAPER_TRADING.sh
```

You should see:

```
====================================================================
  🔔 PAPER TRADING MODE - NO REAL ORDERS WILL BE PLACED 🔔
====================================================================

INITIALIZING ARBITRAGE BOT
====================================================================

✓ Orderbook manager initialized
✓ Depth calculator initialized
✓ Race model initialized
✓ Arb detector initialized
✓ Inventory tracker initialized
✓ Risk manager initialized
✓ All components initialized

====================================================================
STARTING BOT
Mode: maker_hedge
====================================================================
🔔 PAPER TRADING MODE - NO REAL ORDERS 🔔
====================================================================
✓ Simulated trades will be logged to: data/paper_trades.csv
====================================================================

Subscribing to markets...
✓ Subscribed to 5 markets

Starting arbitrage scan loop...

✓ Bot is running!
```

### Step 4: Launch Dashboard 📊

**Terminal 2** - Start the dashboard:

```bash
cd /Users/maxsteffen/Desktop/arbitrage_bot/data-logger-v3-websocket
./START_DASHBOARD.sh
```

You should see the live dashboard with:
- Real-time orderbook data
- Detected opportunities
- Simulated positions
- Bot health status

### Step 5: Let it Run ⏱️

**Recommended duration**: 24-48 hours

During this time, the bot will:
- Detect opportunities as they appear
- Log simulated trades to `data/paper_trades.csv`
- Build statistical history
- Track simulated P&L

**What to watch for**:
- ✅ WebSocket connections stay green (●)
- ✅ Data staleness stays low (<2 seconds)
- ✅ Opportunities are detected regularly
- ✅ Simulated P&L trends positive
- ⚠️ Red flags: Constant stale data, no opportunities, negative P&L

### Step 6: Monitor and Adjust 🔍

**Every few hours, check**:

1. **Dashboard** - Are opportunities showing up?
2. **Bot stats** - What's the approval rate?
3. **Paper trades CSV** - Are trades being logged?

**Common observations**:

| Observation | What it Means | Action |
|-------------|---------------|---------|
| Many opportunities detected | Markets are active | Good! Continue monitoring |
| Low approval rate (<10%) | Risk limits too strict | Consider lowering `min_edge_bps` |
| High approval rate (>50%) | Risk limits too loose | Tighten limits before live trading |
| No opportunities | Markets inactive OR config issue | Check markets.json, verify WebSockets connected |
| Negative simulated P&L | Edge estimates too optimistic | Review slippage assumptions, increase `min_edge_bps` |

### Step 7: Analyze Results 📈

After 24-48 hours, analyze the data:

```bash
# View paper trades
cat data/paper_trades.csv | column -t -s,

# Count opportunities
wc -l data/paper_trades.csv

# Calculate average edge
awk -F, 'NR>1 {sum+=$4; count++} END {print "Avg Edge:", sum/count, "bps"}' data/paper_trades.csv

# Calculate total simulated P&L
awk -F, 'NR>1 {sum+=$6} END {print "Total Simulated P&L: $" sum}' data/paper_trades.csv
```

**Key Metrics to Extract**:

1. **Opportunity Frequency**
   - How many opportunities per hour?
   - Are there dry spells? When?

2. **Edge Distribution**
   - What's the average edge in bps?
   - What's the median edge?
   - How often do >100bp opportunities appear?

3. **Simulated Profitability**
   - Total simulated P&L over 24-48 hours
   - Average P&L per trade
   - Win rate (positive vs negative trades)

4. **Market Timing**
   - When are most opportunities detected?
   - Are there better times of day?

### Step 8: Decide on Next Steps ✅

**If results look good**:
- ✅ Positive simulated P&L
- ✅ Regular opportunities (e.g., 5+ per hour)
- ✅ Average edge >100bps
- ✅ WebSockets stable
- ✅ No major technical issues

**→ Proceed to Phase 2: Live Trading (Small Size)**

**If results are mixed**:
- ⚠️ Low opportunity frequency
- ⚠️ Small or negative simulated P&L
- ⚠️ Inconsistent WebSocket connections

**→ Actions**:
1. Review and adjust `min_edge_bps` threshold
2. Add more markets to `config/markets.json`
3. Check slippage assumptions in `depth_calculator.py`
4. Verify API credentials and WebSocket stability
5. Run paper trading for another 24-48 hours

**If results are bad**:
- ❌ No opportunities detected
- ❌ Consistently negative P&L
- ❌ Technical errors or crashes

**→ Debug**:
1. Verify markets in `config/markets.json` are active
2. Check orderbook data quality (dashboard staleness)
3. Review arb detection logic in `arb_detector.py`
4. Consult `TROUBLESHOOTING.md`

## Files to Monitor

### 1. `data/paper_trades.csv`
All simulated trades with full details:
```csv
timestamp,event_id,direction,edge_bps,size_usd,simulated_pnl,confidence,buy_platform,sell_platform,buy_price,sell_price
2026-01-06T18:32:15,nba-bos-mia-2026-01-06,kalshi_buy,125,100.00,1.25,high,kalshi,polymarket,0.5300,0.4825
```

### 2. `data/bot_state.json`
Current bot status:
```json
{
  "running": true,
  "mode": "maker_hedge",
  "uptime_s": 3600,
  "opportunities_detected": 47,
  "trades_executed": 12,
  "total_pnl": 23.45
}
```

### 3. `data/recent_opportunities.json`
Last 50 detected opportunities with decisions

### 4. `data/orderbooks.json`
Current orderbook state from both venues

## Expected Performance (Paper Trading)

Based on typical market conditions:

| Metric | Conservative | Moderate | Aggressive |
|--------|-------------|----------|------------|
| **Opportunities/hour** | 2-5 | 5-10 | 10-20 |
| **Average edge** | 80-120 bps | 100-150 bps | 150-250 bps |
| **Simulated P&L/day** | $10-30 | $30-100 | $100-300 |
| **Approval rate** | 10-20% | 20-40% | 40-60% |

**Note**: These are **optimistic simulations**. Real trading will have:
- Lower fill rates (race losses)
- Wider spreads (adverse selection)
- Slippage on larger sizes
- Network latency effects

Expect **real profits to be 30-50% of simulated** profits.

## Safety Features Active

Even in paper trading mode, all safety features are active:

✅ Risk limits enforced (max trade size, total exposure)  
✅ Consecutive loss tracking  
✅ Daily P&L limits  
✅ Staleness checks (reject stale orderbook data)  
✅ Confidence scoring (reject low-confidence opportunities)  

The only difference: **No real orders are placed**.

## Stopping the Bot

Press `Ctrl+C` in the bot terminal to stop gracefully.

The bot will:
- Close WebSocket connections
- Print final statistics
- Export final state to JSON files

You can restart anytime without losing data (all logs are persistent).

## What You'll Learn

After completing Phase 1, you should be able to answer:

1. **How often do opportunities appear?**
   - Hourly frequency, time-of-day patterns

2. **What edge levels are realistic?**
   - Distribution of edges, typical vs exceptional

3. **Are the markets liquid enough?**
   - Orderbook depth, size at best price

4. **Is the bot stable?**
   - WebSocket uptime, error rates, crashes

5. **Is this potentially profitable?**
   - Simulated P&L vs realistic expectations

## Troubleshooting

### Issue: No opportunities detected

**Check**:
- Markets in `config/markets.json` are active today
- WebSocket connections are green (●) in dashboard
- Orderbook data is not stale (no ⚠️ warnings)
- `min_edge_bps` is not too high (try 30-50 for testing)

### Issue: Bot crashes or errors

**Check**:
- All dependencies installed (`test_setup.py`)
- `.env` file has valid API credentials
- Python version is 3.10+ (`python3 --version`)
- No conflicting processes using same ports

### Issue: Simulated P&L is negative

**Check**:
- Edge calculations include fees correctly
- Slippage assumptions are not too optimistic
- Markets are not too illiquid (thin orderbooks)
- Risk limits are rejecting bad opportunities

### Issue: Dashboard shows stale data

**Check**:
- WebSocket connections are active
- Network connection is stable
- API keys have WebSocket permissions
- No rate limiting from exchanges

## Next Steps After Phase 1

Once you're satisfied with paper trading results:

→ **Phase 2: Live Trading (Small Size)**
   - Start with $50 trade sizes
   - Increase `min_edge_bps` to 100-150
   - Enable real execution
   - Run for 24 hours
   - Analyze actual fill rates and P&L

→ **Phase 3: Scale Up**
   - Gradually increase trade sizes
   - Add more markets
   - Optimize execution parameters
   - Build long-term track record

## Summary

Phase 1 Paper Trading is your **risk-free testing ground**:

✅ Learn how the bot operates  
✅ Build confidence in the system  
✅ Collect statistical data  
✅ Verify profitability potential  
✅ Identify issues before risking real money  

**Time commitment**: 10 minutes setup + 24-48 hours running  
**Risk**: Zero (no real orders)  
**Value**: Essential foundation for successful live trading  

---

**Ready to start?**

```bash
cd /Users/maxsteffen/Desktop/arbitrage_bot/data-logger-v3-websocket
./START_PAPER_TRADING.sh
```

Then in a separate terminal:
```bash
./START_DASHBOARD.sh
```

Good luck! 🚀

