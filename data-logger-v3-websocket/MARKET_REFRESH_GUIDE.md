# Market Refresh Guide

## Quick Refresh

When games are completed and you need fresh markets:

```bash
cd /Users/maxsteffen/Desktop/arbitrage_bot/data-logger-v2.5-depth
python3 refresh_markets_improved.py
```

This will:
1. ✅ Discover all active NFL and NBA games on both platforms
2. ✅ Match games using team codes
3. ✅ Backup your old `config/markets.json`
4. ✅ Update with fresh active markets
5. ✅ Show you what was configured

## What Gets Updated

The script automatically updates `config/markets.json` with:
- **NFL playoff games** (from KXNFLGAME series on Kalshi)
- **NBA games** (from KXNBAGAME series on Kalshi)
- Only games that exist on **BOTH** Kalshi and Polymarket

## Last Refresh: January 5, 2026 at 20:27

**Current Markets:** 4 NFL Playoff Games

1. **Green Bay at Chicago** (Jan 24, 2026)
2. **Los Angeles Rams at Carolina** (Jan 24, 2026)
3. **San Francisco at Philadelphia** (Jan 25, 2026)
4. **Houston at Pittsburgh** (Jan 26, 2026)

## Backup Files

Old configurations are automatically backed up to:
```
config/markets.json.backup.YYYYMMDD_HHMMSS
```

You can restore a previous configuration by:
```bash
cp config/markets.json.backup.20260105_202701 config/markets.json
```

## How the Matching Works

The script extracts team codes from both platforms:

**Kalshi Ticker Example:**
```
KXNFLGAME-26JAN10GBCHI-CHI
          └─────┬────────┘
         GB + CHI = Green Bay vs Chicago
```

**Polymarket Slug Example:**
```
nfl-gb-chi-2026-01-10
    └──┘ └──┘
    GB   CHI = Green Bay vs Chicago
```

Games are matched when both team codes match!

## Troubleshooting

### No Markets Found

If the script finds 0 markets:
- Both platforms may not have matching games scheduled
- Check if games are too far in the future (script looks 7 days ahead)
- NBA markets might not exist on Polymarket yet

### Partial Matches

If you see "Found 10 games on Kalshi, 5 on Polymarket, matched 3":
- This is normal! Not all games exist on both platforms
- The bot will track the 3 that match

### Want to Add Manual Markets?

Edit `config/markets.json` directly and follow the format:

```json
{
  "event_id": "unique_id_here",
  "description": "Team A vs Team B Winner?",
  "sport": "NFL",
  "teams": {
    "team_a": "Team A Name",
    "team_b": "Team B Name"
  },
  "kalshi": {
    "enabled": true,
    "markets": {
      "main": "KALSHI-TICKER-A",
      "opponent": "KALSHI-TICKER-B"
    }
  },
  "polymarket": {
    "enabled": true,
    "markets": {
      "slug": "polymarket-slug-here"
    }
  }
}
```

## When to Refresh

Refresh markets when:
- ✅ Games you're tracking have completed
- ✅ You want to track new upcoming games
- ✅ Starting a new betting session
- ✅ Weekly (recommended)

## After Refreshing

1. Review the new markets in `config/markets.json`
2. Start the data logger: `python data_logger_depth.py`
3. Start the dashboard: `./START_DASHBOARD.sh`
4. Watch for arbitrage opportunities!

---

**Pro Tip:** Run the refresh script before each major game day (NFL Sundays, NBA nights) to ensure you have the latest markets!

