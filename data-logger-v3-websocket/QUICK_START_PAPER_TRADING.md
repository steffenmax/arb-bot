# Quick Start: Phase 1 Paper Trading

**⚠️ NO REAL ORDERS - SIMULATION ONLY ⚠️**

## 3-Minute Setup

### Step 1: Verify Everything is Ready ✓

```bash
cd /Users/maxsteffen/Desktop/arbitrage_bot/data-logger-v3-websocket
../venv/bin/python3 test_setup.py
```

All components should show ✓

### Step 2: Start Paper Trading Bot 🚀

**Terminal 1:**

```bash
./START_PAPER_TRADING.sh
```

You should see:
```
🔔 PAPER TRADING MODE - NO REAL ORDERS 🔔
✓ Bot is running!
```

### Step 3: Start Dashboard 📊

**Terminal 2:**

```bash
./START_DASHBOARD.sh
```

You should see live orderbook data and opportunities.

### Step 4: Let It Run ⏱️

**Recommended**: 24-48 hours

The bot will:
- Detect real opportunities
- Log simulated trades to `data/paper_trades.csv`
- Track simulated P&L
- **NOT place any real orders**

### Step 5: Check Results 📈

After 24-48 hours:

```bash
# View simulated trades
cat data/paper_trades.csv | column -t -s,

# Count opportunities
wc -l data/paper_trades.csv

# Total simulated P&L
awk -F, 'NR>1 {sum+=$6} END {print "Total Simulated P&L: $" sum}' data/paper_trades.csv
```

## What to Watch

✅ **Good Signs**:
- WebSocket connections stay green (●)
- Opportunities detected regularly (5+ per hour)
- Simulated P&L is positive
- No crashes or errors

⚠️ **Warning Signs**:
- Stale data (⚠️ warnings)
- No opportunities for long periods
- Negative simulated P&L
- Bot crashes

## Stopping the Bot

Press `Ctrl+C` in the bot terminal.

## Files Generated

- `data/paper_trades.csv` - All simulated trades
- `data/bot_state.json` - Current bot status
- `data/recent_opportunities.json` - Last 50 opportunities
- `data/orderbooks.json` - Live orderbook state

## Next Steps

If results look good after 24-48 hours:
→ Read `PHASE1_PAPER_TRADING_GUIDE.md` for detailed analysis
→ Proceed to Phase 2: Live Trading (Small Size)

If results are mixed:
→ Adjust `min_edge_bps` in `config/bot_config_paper.json`
→ Add more markets to `config/markets.json`
→ Run for another 24-48 hours

## Support

For detailed instructions: `PHASE1_PAPER_TRADING_GUIDE.md`  
For troubleshooting: `PRODUCTION_BOT_README.md`  
For transparency features: `TRANSPARENCY_FEATURES.md`

