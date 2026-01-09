# 🚀 START HERE - Data Logger Quick Start

**Status:** ✅ Ready to collect data from NBA markets  
**Your markets:** 20 NBA games configured and ready

---

## What You Have

✅ **Kalshi credentials** - Configured and working  
✅ **NBA markets** - 20 games discovered from Kalshi  
✅ **Database** - Set up and tested  
✅ **Data logger** - Ready to run

---

## Quick Start (3 Commands)

### 1. Review Your Markets
```bash
cat config/markets.json
```

You have 20 NBA games ready to track (Portland vs OKC, etc.)

### 2. (Optional) Add Polymarket IDs

If you want to track Polymarket too for arbitrage detection:
```bash
python3 add_polymarket_ids.py --interactive --input config/markets.json
```

Or skip this - you can add Polymarket later.

### 3. Start Collecting Data!
```bash
python3 data_logger.py --hours 24
```

**That's it!** The system will collect price data every 30 seconds.

---

## What Happens Next

The data logger will:
- ✅ Collect prices from 20 NBA games on Kalshi
- ✅ Store everything in SQLite database
- ✅ Run for 24 hours (or until you stop it)
- ✅ Show progress after each cycle
- ✅ Handle errors gracefully

**Example output:**
```
======================================================================
Collection Cycle #1 - 2025-12-29 16:00:00
======================================================================

[1/20] Portland vs Oklahoma City
  ✓ Kalshi: 2 market(s) collected

[2/20] Los Angeles vs Boston
  ✓ Kalshi: 2 market(s) collected

──────────────────────────────────────────────────────────────────
Cycle #1 Summary:
  Kalshi:     40 success, 0 failed
──────────────────────────────────────────────────────────────────

⏱️  Waiting 28.5s until next cycle
```

---

## After Data Collection

Once you have data (after a few hours or 24 hours):

```bash
python3 analysis/analyze_opportunities.py
```

This will:
- ✅ Find time-matched prices
- ✅ Calculate arbitrage opportunities
- ✅ Account for fees (7% Kalshi + 2% Polymarket)
- ✅ Show if profitable opportunities existed

---

## Common Commands

### Start Collecting (24 hours)
```bash
python3 data_logger.py --hours 24
```

### Start Collecting (1 hour test)
```bash
python3 data_logger.py --hours 1
```

### Stop Collecting
Press `Ctrl+C` (stops gracefully)

### Check Database
```bash
sqlite3 data/market_data.db "SELECT COUNT(*) FROM price_snapshots"
```

### Analyze Data
```bash
python3 analysis/analyze_opportunities.py
```

### Discover More Markets
```bash
# Find more NBA games
python3 discover_markets_improved.py --sport NBA --save

# Find NHL games
python3 discover_markets_improved.py --sport NHL --save

# Find NFL games
python3 discover_markets_improved.py --sport NFL --save
```

---

## File Structure

```
data-logger/
├── config/
│   └── markets.json          ← Your 20 NBA games (configured!)
├── data/
│   └── market_data.db        ← Price data stored here
├── analysis/
│   └── analyze_opportunities.py  ← Run after collection
├── data_logger.py            ← Main script (run this!)
├── discover_markets_improved.py  ← Find more markets
└── add_polymarket_ids.py     ← Add Polymarket (optional)
```

---

## Understanding Your Markets

Each market in `config/markets.json` looks like:

```json
{
  "event_id": "kxnbagame_25dec31porokc_por",
  "description": "Portland vs Oklahoma City Winner?",
  "teams": {
    "yes_team": "Portland",
    "note": "Kalshi YES = this team wins"
  },
  "kalshi": {
    "enabled": true,
    "markets": {
      "main": "KXNBAGAME-25DEC31POROKC-POR"
    },
    "yes_refers_to": "Portland"
  }
}
```

**Important:** `yes_refers_to` tells you which team "YES" means wins. This is critical for arbitrage matching!

---

## Adding Polymarket (For Arbitrage)

Right now you only have Kalshi. To detect arbitrage, you need both platforms.

### Option 1: Add Polymarket IDs Interactively
```bash
python3 add_polymarket_ids.py --interactive --input config/markets.json
```

This will prompt you for each game to add Polymarket condition IDs.

### Option 2: Add Manually

Edit `config/markets.json` and for each game add:
```json
"polymarket": {
  "enabled": true,
  "markets": {
    "game": "CONDITION_ID_HERE"
  }
}
```

Find condition IDs at https://polymarket.com by searching for the game.

---

## Troubleshooting

### "No markets configured"
```bash
# Make sure markets.json exists
ls -la config/markets.json

# Should show 20 markets
cat config/markets.json | grep event_id | wc -l
```

### "Authentication failed"
```bash
# Test Kalshi credentials
python3 test_kalshi_auth.py
```

### "Database error"
```bash
# Recreate database
python3 db_setup.py
```

### "Want different markets"
```bash
# Discover fresh markets
python3 discover_markets_improved.py --sport NBA --save
cp markets_discovered_improved.json config/markets.json
```

---

## What's Next?

### Immediate: Start Collecting
```bash
python3 data_logger.py --hours 24
```

### Later: Analyze Results
After 24 hours:
```bash
python3 analysis/analyze_opportunities.py
```

### Optional: Add More Sports
```bash
python3 discover_markets_improved.py --sport NHL --save
# Review and merge with existing markets.json
```

---

## Key Points

✅ **You have 20 NBA games ready** - No setup needed  
✅ **Kalshi credentials work** - Already tested  
✅ **Just run data_logger.py** - That's all you need  
✅ **Add Polymarket later** - Optional for arbitrage  
✅ **Analyze after 24 hours** - See if opportunities exist

---

## Your Next Command

```bash
python3 data_logger.py --hours 24
```

Press `Ctrl+C` anytime to stop gracefully.

Good luck! 🎯

