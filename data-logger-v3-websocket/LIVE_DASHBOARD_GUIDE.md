# Live Dashboard Guide

## Overview

The **Live Dashboard** gives you real-time visibility into your arbitrage bot's operations. It displays:

- ✅ All games being monitored
- ✅ Latest ask prices from both Kalshi and Polymarket
- ✅ Top-of-book volumes for each market
- ✅ Best arbitrage combinations automatically calculated
- ✅ **GREEN highlighting** when profitable opportunities exist (total cost < 1.0)
- ✅ Live CSV export for Excel/Google Sheets

## Quick Start

### Method 1: Using the Startup Script (Recommended)

```bash
# Terminal 1: Start data collection
python data_logger_depth.py

# Terminal 2: Start live dashboard
./START_DASHBOARD.sh
```

### Method 2: Direct Python Execution

```bash
# Terminal 1: Start data collection
python data_logger_depth.py

# Terminal 2: Start dashboard
python live_dashboard.py
```

## Dashboard Display

### Terminal View

The dashboard shows a live-updating table with the following columns:

| Column | Description |
|--------|-------------|
| **GAME** | Game description (e.g., "Arizona at Los Angeles R Winner?") |
| **TEAM A** | First team name |
| **TEAM B** | Second team name |
| **K-A ASK** | Kalshi ask price for Team A |
| **K-A VOL** | Kalshi top-of-book volume for Team A |
| **K-B ASK** | Kalshi ask price for Team B |
| **K-B VOL** | Kalshi top-of-book volume for Team B |
| **P-A ASK** | Polymarket ask price for Team A |
| **P-A VOL** | Polymarket top-of-book volume for Team A |
| **P-B ASK** | Polymarket ask price for Team B |
| **P-B VOL** | Polymarket top-of-book volume for Team B |
| **BEST COMBO** | Which combination to bet (e.g., "K:Pit + P:Bal") |
| **TOTAL** | Total cost of both positions |
| **PROFIT** | Expected profit percentage |
| **STATUS** | "ARB" if profitable, "-" otherwise |

### Color Coding

- 🟢 **GREEN rows**: Profitable arbitrage opportunity detected (total < 1.0)
- ⚪ **White rows**: No current arbitrage opportunity

### Example Display

```
================================================================================
                    LIVE ARBITRAGE DASHBOARD - 14:32:45
================================================================================

GAME                             TEAM A          TEAM B          K-A ASK   K-A VOL   K-B ASK   K-B VOL   P-A ASK   P-A VOL   P-B ASK   P-B VOL   BEST COMBO           TOTAL     PROFIT    STATUS
────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
Baltimore at Pittsburgh Winner?  Pittsburgh      Baltimore       0.520     2.5k      0.480     3.1k      0.515     1.8k      0.485     2.2k      K:Pit + P:Bal        0.9850    1.52%     ARB    
Arizona at Los Angeles R Winner? Los Angeles R   Arizona         0.620     1.2k      0.380     1.5k      0.625     800       0.375     900       K:Los + P:Ari        0.9950    0.50%     ARB    
```

## Excel/Spreadsheet Integration

The dashboard automatically exports data to:
```
data/live_dashboard.csv
```

### Using with Excel (Mac)

1. Open Excel
2. File → Open → Select `data/live_dashboard.csv`
3. The file updates every second automatically
4. To see updates: Just reopen the file or set auto-refresh if your Excel version supports it

### Using with Google Sheets

1. Go to Google Sheets
2. File → Import → Upload `data/live_dashboard.csv`
3. Refresh the import periodically to see updates
4. Or use Google Sheets' built-in data refresh features

### Using with Numbers (Mac)

1. Open Numbers
2. File → Open → Select `data/live_dashboard.csv`
3. Numbers can auto-update: File → Advanced → Auto Update External References

## Understanding the Arbitrage Logic

The dashboard calculates **both possible cross-platform combinations** for each game:

### Combination A
- Buy Team A on Kalshi (YES)
- Buy Team B on Polymarket (YES)
- **Total Cost** = Kalshi A Ask + Polymarket B Ask

### Combination B
- Buy Team B on Kalshi (YES)
- Buy Team A on Polymarket (YES)
- **Total Cost** = Kalshi B Ask + Polymarket A Ask

The dashboard shows the **BEST** combination (lowest total cost).

### When is it Profitable?

✅ **PROFITABLE** (shows in GREEN):
- Total cost < 1.0
- You're guaranteed to win $1.00 no matter which team wins
- Profit = $1.00 - Total Cost

❌ **NOT PROFITABLE**:
- Total cost ≥ 1.0
- No arbitrage opportunity

### Example

```
Game: Steelers vs Ravens
K-Steelers Ask: $0.52
K-Ravens Ask: $0.48
P-Steelers Ask: $0.51
P-Ravens Ask: $0.49

Combo A: K-Steelers + P-Ravens = $0.52 + $0.49 = $1.01 (NO)
Combo B: K-Ravens + P-Steelers = $0.48 + $0.51 = $0.99 (YES! 1% profit)

Dashboard shows: "K:Rav + P:Ste" with TOTAL: 0.9900 in GREEN
```

## Configuration

You can adjust the dashboard settings by editing `live_dashboard.py`:

```python
REFRESH_INTERVAL = 1  # Update every N seconds
MAX_DATA_AGE = 10     # Only show data from last N seconds
```

## Troubleshooting

### "No data showing"
- Make sure `data_logger_depth.py` is running
- Check that it's collecting data (look for price snapshots in terminal)
- Verify database exists at `data/market_data.db`

### "All prices show as dashes (---)"
- Data might be stale (older than 10 seconds)
- Check if data logger is successfully fetching from APIs
- Verify your API keys are configured correctly

### "CSV file not updating"
- The CSV updates every second while dashboard is running
- Close and reopen in Excel to see latest data
- Check file permissions on `data/` folder

### Terminal too small
- Dashboard is designed for 180+ column width
- Maximize your terminal window
- Or use the CSV export for better viewing

## Advanced Usage

### Running in Background with Logging

```bash
# Run data logger in background
nohup python data_logger_depth.py > logs/data_logger.log 2>&1 &

# Run dashboard (foreground to see display)
python live_dashboard.py
```

### Checking Historical Data

The dashboard only shows live data (last 10 seconds). To analyze historical arbitrage opportunities:

```bash
python analyze_arbitrage.py
# or
python realtime_arb_monitor_v2.py
```

## Tips

1. **Use two monitors**: Data logger on one, dashboard on the other
2. **Check volumes**: Low volume might mean high slippage
3. **Act fast**: Profitable opportunities can disappear in seconds
4. **Verify in CSV**: Double-check prices in the CSV export before trading
5. **Monitor status**: Watch for "ARB" status to appear in real-time

## Files Created

- `live_dashboard.py` - Main dashboard script
- `START_DASHBOARD.sh` - Convenient startup script
- `data/live_dashboard.csv` - Auto-updated CSV export
- `LIVE_DASHBOARD_GUIDE.md` - This guide

## Support

If you encounter issues:
1. Check that data logger is running and collecting data
2. Verify database has recent data: `sqlite3 data/market_data.db "SELECT COUNT(*) FROM price_snapshots;"`
3. Check terminal size (needs 180+ columns wide)
4. Review data logger logs for API errors

---

**Happy Arbitraging! 📊💰**

