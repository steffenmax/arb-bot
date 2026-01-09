# Live Dashboard Integration - COMPLETE ✅

## Summary

A live Excel-style monitoring dashboard has been successfully integrated into your data-logger-v2.5-depth bot!

**Created:** January 5, 2026

---

## What Was Added

### 1. **live_dashboard.py** 
The main dashboard script that provides:
- Real-time terminal display with color-coded arbitrage opportunities
- Live CSV export for Excel/Spreadsheet viewing
- Auto-refresh every 1 second
- Displays all markets being monitored with:
  - Latest ask prices from both Kalshi and Polymarket
  - Top-of-book volumes for liquidity visibility
  - Best arbitrage combination automatically calculated
  - **GREEN highlighting when total cost < 1.0** (profitable!)

### 2. **START_DASHBOARD.sh**
Convenient startup script that:
- Checks if data logger is running
- Provides helpful warnings and instructions
- Launches the dashboard with one command

### 3. **LIVE_DASHBOARD_GUIDE.md**
Complete documentation including:
- Quick start instructions
- Column explanations
- Excel/Google Sheets integration guide
- Arbitrage logic explanation
- Troubleshooting tips
- Configuration options

---

## How to Use

### Step 1: Start Data Collection
```bash
cd /Users/maxsteffen/Desktop/arbitrage_bot/data-logger-v2.5-depth
python data_logger_depth.py
```

### Step 2: Start Dashboard (in a new terminal)
```bash
cd /Users/maxsteffen/Desktop/arbitrage_bot/data-logger-v2.5-depth
./START_DASHBOARD.sh
```

Or directly:
```bash
python live_dashboard.py
```

---

## Dashboard Features

### Terminal Display
```
================================================================================
                    LIVE ARBITRAGE DASHBOARD - 14:32:45
================================================================================

GAME                             TEAM A          TEAM B          K-A ASK   K-A VOL   K-B ASK   K-B VOL   P-A ASK   P-A VOL   P-B ASK   P-B VOL   BEST COMBO           TOTAL     PROFIT    STATUS
────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
Baltimore at Pittsburgh Winner?  Pittsburgh      Baltimore       0.520     2.5k      0.480     3.1k      0.515     1.8k      0.485     2.2k      K:Pit + P:Bal        0.9850    1.52%     ARB    
```

**Color Coding:**
- 🟢 **GREEN** = Profitable arbitrage (total < 1.0)
- ⚪ **WHITE** = No arbitrage opportunity

### CSV Export
Location: `data/live_dashboard.csv`

This file updates every second and can be opened in:
- Microsoft Excel
- Google Sheets
- Apple Numbers
- Any spreadsheet application

Perfect for:
- Sharing with team members
- Importing into trading tools
- Historical snapshots (save/rename the CSV)
- Analysis in Excel with formulas

---

## Understanding the Display

### Columns Explained

| Column | What It Shows |
|--------|---------------|
| **GAME** | The matchup being monitored |
| **TEAM A/B** | The two teams |
| **K-A ASK** | Price to buy Team A on Kalshi |
| **K-A VOL** | Available volume for Team A on Kalshi |
| **K-B ASK** | Price to buy Team B on Kalshi |
| **K-B VOL** | Available volume for Team B on Kalshi |
| **P-A ASK** | Price to buy Team A on Polymarket |
| **P-A VOL** | Available volume for Team A on Polymarket |
| **P-B ASK** | Price to buy Team B on Polymarket |
| **P-B VOL** | Available volume for Team B on Polymarket |
| **BEST COMBO** | Which cross-platform bet combo is cheapest |
| **TOTAL** | Sum of the two positions in best combo |
| **PROFIT** | Expected profit percentage if total < 1.0 |
| **STATUS** | "ARB" if profitable, "-" otherwise |

### Arbitrage Logic

For each game, the bot checks **TWO combinations**:

**Combo A:** Kalshi Team A + Polymarket Team B
**Combo B:** Kalshi Team B + Polymarket Team A

It shows the **cheaper one** (best opportunity).

**Example:**
```
Steelers vs Ravens
K-Steelers: $0.52
K-Ravens: $0.48  
P-Steelers: $0.51
P-Ravens: $0.49

Combo A: 0.52 + 0.49 = $1.01 ❌ (lose $0.01)
Combo B: 0.48 + 0.51 = $0.99 ✅ (profit $0.01 = 1%)

Display shows: "K:Rav + P:Ste" | 0.9900 | 1.01% | ARB (in GREEN)
```

---

## Quick Reference

### Files Created
```
live_dashboard.py              # Main dashboard script
START_DASHBOARD.sh             # Startup helper
LIVE_DASHBOARD_GUIDE.md        # Detailed documentation
DASHBOARD_INTEGRATION_COMPLETE.md  # This file
data/live_dashboard.csv        # Auto-generated CSV export
```

### Key Settings (in live_dashboard.py)
```python
REFRESH_INTERVAL = 1    # Update frequency (seconds)
MAX_DATA_AGE = 10       # Only show recent data (seconds)
```

### Commands
```bash
# Start dashboard
./START_DASHBOARD.sh
# or
python live_dashboard.py

# Stop dashboard
Press Ctrl+C

# Check if data logger is running
pgrep -f "data_logger_depth.py"
```

---

## What Happens When You Run It

1. **Loads Configuration** - Reads `config/markets.json` for tracked games
2. **Connects to Database** - Accesses `data/market_data.db` for live prices
3. **Fetches Latest Data** - Gets prices from last 10 seconds
4. **Calculates Arbitrage** - Checks both cross-platform combinations
5. **Displays Table** - Shows results with color coding
6. **Exports CSV** - Writes to `data/live_dashboard.csv`
7. **Refreshes** - Repeats every 1 second

---

## Tips for Success

### Best Practices
1. ✅ Always run data logger first (it needs to be collecting data)
2. ✅ Use a wide terminal window (180+ columns recommended)
3. ✅ Watch for GREEN rows - they're your opportunities
4. ✅ Check volumes - high volume = more liquidity = less slippage
5. ✅ Open CSV in Excel for easier viewing/sharing

### Two-Monitor Setup
- **Monitor 1:** Data logger terminal (shows collection stats)
- **Monitor 2:** Dashboard (shows live opportunities)
- **Excel on side:** CSV open for detailed analysis

### When You See Green (ARB)
1. Note the **BEST COMBO** column (tells you what to bet)
2. Check the **VOLUMES** (make sure there's enough liquidity)
3. Verify the **TOTAL** is actually < 1.0
4. Act quickly - opportunities disappear fast!

---

## Troubleshooting

### No Data Showing?
```bash
# Check if data logger is running
pgrep -f "data_logger_depth"

# Check database has data
sqlite3 data/market_data.db "SELECT COUNT(*) FROM price_snapshots WHERE timestamp > datetime('now', '-1 minute');"
```

### All Prices Show "---"?
- Data might be too old (>10 seconds)
- Data logger might not be fetching successfully
- Check data logger terminal for API errors

### Terminal Display Looks Weird?
- Make terminal window wider (needs 180+ columns)
- Or just use the CSV export in Excel

---

## Next Steps

### Ready to Trade?
When you see a profitable opportunity (GREEN):
1. Verify prices are still valid
2. Check volumes are sufficient
3. Place orders on both platforms simultaneously
4. Monitor fill prices (watch for slippage)

### Want to Analyze History?
```bash
# See all arbitrage opportunities over time
python analyze_arbitrage.py

# Real-time monitor with duration tracking
python realtime_arb_monitor_v2.py
```

### Want to Customize?
Edit `live_dashboard.py` to:
- Change refresh interval
- Adjust data age threshold
- Modify column widths
- Add more metrics
- Change color scheme

---

## Architecture

```
┌─────────────────────────┐
│  data_logger_depth.py   │  ← Collects market data
│  (Terminal 1)           │     Stores in database
└───────────┬─────────────┘
            │
            ↓
┌─────────────────────────┐
│   market_data.db        │  ← SQLite database
│   (Shared)              │     - price_snapshots
│                         │     - orderbook_snapshots
└───────────┬─────────────┘
            │
            ↓
┌─────────────────────────┐
│  live_dashboard.py      │  ← Reads and displays
│  (Terminal 2)           │     Shows opportunities
│                         │     Exports to CSV
└───────────┬─────────────┘
            │
            ↓
┌─────────────────────────┐
│  live_dashboard.csv     │  ← Excel-compatible
│  (Auto-updated)         │     View in spreadsheet
└─────────────────────────┘
```

---

## Success! 🎉

Your live dashboard is now ready to use. You have:

✅ Real-time terminal display with color coding
✅ Excel-compatible CSV export (auto-updating)
✅ Automatic arbitrage calculation
✅ Volume visibility for liquidity assessment
✅ Easy startup script
✅ Comprehensive documentation

**You're ready to monitor your arbitrage bot in real-time!**

---

*Integration completed on January 5, 2026*
*Located in: `/Users/maxsteffen/Desktop/arbitrage_bot/data-logger-v2.5-depth/`*

