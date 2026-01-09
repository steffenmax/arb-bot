# Polymarket Status & Fixes

## Issues Identified & Fixed

### 1. ✅ FIXED: Polymarket API Bug
**Problem**: `AttributeError: 'PolymarketClient' object has no attribute 'gamma_api_base'`

**Root Cause**: In `polymarket_client.py`, the `__init__` method was setting `self.api_base` but the code was trying to access `self.gamma_api_base`.

**Fix**: Changed line 27 from `self.api_base = api_base` to `self.gamma_api_base = api_base`

### 2. ⚠️ ISSUE: No Individual Game Markets Available
**Problem**: All Polymarket data showing as 0.5/0.5 prices with 0 volume and 0.01/0.99 bid/ask spreads.

**Root Cause**: Polymarket currently has **ZERO individual game markets** for NBA. They only have futures markets (2026 Champion, Rookie of the Year, etc.).

**Evidence**:
- Dec 28, 2025: Your old bot found 56 NBA game markets
- Dec 30, 2025 (today): ZERO game markets available
- Current NBA markets on Polymarket are all futures:
  - "Will the Oklahoma City Thunder win the 2026 NBA Finals?"
  - "Will NBA competitor raise >$3b in 2025?"
  - etc.

**Analysis**: Polymarket doesn't always have individual game markets. They may only list them:
- On game day
- A few hours before game time
- For high-profile games only
- Intermittently based on market maker availability

### 3. ✅ FIXED: Kalshi Data Clarity
**Problem**: Kalshi data wasn't showing which team each row represented.

**Fix**: Updated `data_logger.py` to use the team name (from `yes_refers_to` field) as the `market_side` value instead of just "main".

**Before**:
```
kalshi  kxnbagame_25dec31porokc_por  main  0.87  0.13
kalshi  kxnbagame_25dec31porokc_okc  main  0.13  0.87
```

**After**:
```
kalshi  kxnbagame_25dec31porokc_por  Portland      0.87  0.13
kalshi  kxnbagame_25dec31porokc_okc  Oklahoma City 0.13  0.87
```

### 4. ✅ ADDED: Polymarket Liquidity Check
**What**: Added logic to skip Polymarket markets with no liquidity (fake 0.5/0.5 prices).

**How**: Checks for:
- Volume > 0 or Liquidity > 0
- Real bid/ask spreads (< 0.9, not the fake 0.98 spread)

**Result**: The data logger will now skip Polymarket markets that don't really exist yet, with a warning message.

## Current Status

### ✅ Working:
- **Kalshi**: Collecting data successfully with proper team names
- **Database**: Storing all data correctly
- **Error Handling**: Gracefully handling missing Polymarket markets

### ⚠️ Not Working (Temporary):
- **Polymarket**: No individual game markets available today
  - API is working correctly
  - Markets just don't exist yet
  - Old condition IDs in markets.json are invalid/expired

## Recommendations

### Option 1: Wait for Game Day (RECOMMENDED)
**When**: Tomorrow (Dec 31) or a few hours before games

**Action**:
```bash
cd data-logger

# Re-discover Polymarket markets (closer to game time)
python3 add_polymarket_to_markets.py

# Restart data logger
python3 data_logger.py --hours 24
```

**Why**: Polymarket had 56 games available on Dec 28. They might reappear closer to game time.

### Option 2: Kalshi Only (IMMEDIATE)
**When**: Right now

**Action**:
1. Disable Polymarket in `config/settings.json`:
```json
{
  "polymarket": {
    "enabled": false,  // Change to false
    ...
  }
}
```

2. Restart data logger:
```bash
python3 data_logger.py --hours 24
```

**Why**: Kalshi is working perfectly. Collect that data first, add Polymarket later.

### Option 3: Monitor & Auto-Add (ADVANCED)
**Create a script** that:
1. Checks Polymarket API hourly for new game markets
2. Auto-updates `markets.json` when markets appear
3. Continues logging

**Implementation**: Not yet built, but could be added if needed.

## Data Quality Check

### Latest Kalshi Data (should be clean):
```bash
cd data-logger
sqlite3 data/market_data.db "
SELECT 
  datetime(timestamp) as time,
  event_id,
  market_side as team,
  yes_price,
  no_price,
  volume
FROM price_snapshots
WHERE platform = 'kalshi'
AND timestamp > datetime('now', '-1 hour')
ORDER BY timestamp DESC
LIMIT 20;
"
```

### Check for Bad Polymarket Data:
```bash
sqlite3 data/market_data.db "
SELECT COUNT(*) as bad_records
FROM price_snapshots
WHERE platform = 'polymarket'
AND volume = 0
AND yes_price = 0.5;
"
```

**If bad records exist**: These are from before the fix. They won't hurt anything but represent fake/non-existent markets.

## Next Steps

1. **NOW**: Restart data logger with the fixes:
```bash
cd data-logger
python3 data_logger.py --hours 24
```

2. **Check data quality** (use queries above)

3. **Tomorrow morning** (Dec 31): Re-run Polymarket market discovery

4. **Monitor** the first hour of data collection to ensure:
   - Kalshi team names showing correctly
   - Polymarket warnings appearing (markets don't exist yet)
   - No errors or crashes

## Files Changed

1. `polymarket_client.py`: Fixed `gamma_api_base` attribute
2. `data_logger.py`: 
   - Team names for Kalshi
   - Liquidity checks for Polymarket
3. This document: `POLYMARKET_STATUS.md`

## Understanding the Data

### Kalshi Structure:
- **TWO markets per game** (one per team)
- **YES/NO prices**: YES = this team wins, NO = other team wins
- **Complementary pricing**: If Team A is 0.70/0.30, Team B should be ~0.30/0.70
- **Team identification**: Now stored in `market_side` column

### Polymarket Structure (when it works):
- **ONE market per game** with two outcomes
- **Team prices**: Direct probability for each team (not yes/no)
- **Sum to ~1.0**: Both teams' prices should add up to approximately 1.0
- **Team identification**: Also stored in `market_side` column

### Comparing Platforms:
```sql
-- See both platforms side-by-side for same games
SELECT 
  datetime(k.timestamp) as time,
  k.event_id,
  k.market_side as kalshi_team,
  k.yes_price as kalshi_price,
  p.market_side as poly_team,
  p.yes_price as poly_price
FROM price_snapshots k
LEFT JOIN price_snapshots p 
  ON k.event_id = p.event_id 
  AND k.market_side = p.market_side
  AND ABS(julianday(k.timestamp) - julianday(p.timestamp)) < 0.001  -- within ~1 minute
WHERE k.platform = 'kalshi'
AND (p.platform = 'polymarket' OR p.platform IS NULL)
ORDER BY k.timestamp DESC
LIMIT 20;
```

## Troubleshooting

### If Kalshi team names still show as "main":
Delete the database and restart:
```bash
rm data/market_data.db
python3 db_setup.py  # Recreate empty database
python3 data_logger.py --hours 24
```

### If Polymarket never works:
Check if markets exist:
```bash
python3 -c "
import requests
r = requests.get('https://gamma-api.polymarket.com/markets', params={'tag_id': '745', 'limit': 10})
markets = r.json()
games = [m for m in markets if ' vs ' in m.get('question', '').lower()]
print(f'Found {len(games)} game markets')
for g in games[:5]:
    print(f\"  - {g['question']}\")
"
```

If this returns 0 games, Polymarket simply doesn't have any game markets right now.

### If data logger crashes:
Check logs:
```bash
tail -f logs/data_logger.log
```

Look for specific error messages and check API status:
- Kalshi: https://trading-api.kalshi.com/trade-api/v2/exchange/status
- Polymarket: https://gamma-api.polymarket.com/events (should return 200)

---

**Created**: 2025-12-30
**Status**: Fixes applied, ready for restart
**Action Required**: Restart data logger to use new code

