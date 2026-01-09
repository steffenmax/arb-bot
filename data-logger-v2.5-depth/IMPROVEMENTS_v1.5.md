# v1.5 Improvements

## Changes from v1.0

### 1. ✅ Cleaner Logging Output

**Before:**
```
[1/20] Portland vs Oklahoma City Winner?
  ✓ Kalshi: 1 market(s) collected
  
[2/20] Portland vs Oklahoma City Winner?
  ✓ Kalshi: 1 market(s) collected
  ↷ Polymarket: already fetched this cycle  ← Confusing!
```

**After:**
```
[1/20] Portland vs Oklahoma City Winner?
  ✓ Kalshi: Portland
  ✓ Polymarket: 2 outcome(s) collected
  
[2/20] Portland vs Oklahoma City Winner?
  ✓ Kalshi: Oklahoma City
  (no Polymarket message - already got both teams)
```

**Why**: 
- Removed confusing "already fetched" messages
- Shows team names directly
- Makes it clear Polymarket gets both teams at once

### 2. ✅ Better Cycle Summaries

**Before:**
```
Cycle #5 Summary:
  Kalshi:     20 success, 0 failed
  Polymarket: 0 success, 0 failed
```

**After:**
```
Cycle #5 Summary:
  Kalshi:     20 markets collected, 0 failed
  Polymarket: 20 outcomes collected, 0 failed
              (10 games × 2 teams = 20 outcomes)
```

**Why**:
- Clarifies what the numbers mean
- Explains relationship between games and outcomes
- More transparent about what's happening

### 3. ✅ SQL Query Templates

Created `QUERY_EXAMPLES.md` with ready-to-use queries:

**Quick View with Team Names:**
```sql
SELECT 
  datetime(timestamp) as time,
  platform,
  market_side as team,  ← Team name here!
  ROUND(yes_price, 3) as price,
  ROUND(volume, 0) as volume
FROM price_snapshots
ORDER BY timestamp DESC
LIMIT 20;
```

**Compare Platforms:**
```sql
SELECT 
  k.market_side as kalshi_team,
  ROUND(k.yes_price, 3) as kalshi_price,
  p.market_side as poly_team,
  ROUND(p.yes_price, 3) as poly_price,
  ROUND(k.yes_price - p.yes_price, 3) as diff
FROM price_snapshots k
LEFT JOIN price_snapshots p 
  ON k.event_id = p.event_id 
  AND k.market_side = p.market_side
WHERE k.platform = 'kalshi'
  AND p.platform = 'polymarket'
ORDER BY k.timestamp DESC
LIMIT 20;
```

**Find Arbitrage:**
```sql
-- See QUERY_EXAMPLES.md for full query
-- Finds price differences > 5%
```

## How Team Names Work

### In Database (`market_side` column):

**Kalshi**:
- Shows city name: `Boston`, `Golden State`, `Portland`
- YES price = probability this team wins
- NO price = probability other team wins

**Polymarket**:
- Shows team name: `Celtics`, `Warriors`, `Trail Blazers`
- Price = direct probability this team wins
- No YES/NO - just team probability

### Example Data:

```
time                | platform   | team           | price
--------------------|------------|----------------|------
2025-12-30 18:26:11 | kalshi     | Boston         | 0.715
2025-12-30 18:26:11 | polymarket | Celtics        | 0.715
2025-12-30 18:26:10 | kalshi     | Utah           | 0.285
2025-12-30 18:26:11 | polymarket | Jazz           | 0.285
```

**Same Game, Different Labels**:
- Kalshi: Boston (0.715) vs Utah (0.285)
- Polymarket: Celtics (0.715) vs Jazz (0.285)

## Quick Reference

### View Latest with Team Names
```bash
cd data-logger-v1.5
sqlite3 data/market_data.db "
SELECT datetime(timestamp), platform, market_side, ROUND(yes_price,3)
FROM price_snapshots ORDER BY timestamp DESC LIMIT 20;
"
```

### Check Which Team is Which
```bash
sqlite3 data/market_data.db "
SELECT DISTINCT event_id, market_side, platform
FROM price_snapshots
WHERE event_id LIKE '%bosuta%'
ORDER BY platform, market_side;
"
```

### Compare Prices
```bash
sqlite3 data/market_data.db "
SELECT 
  k.market_side as kalshi_team,
  ROUND(k.yes_price, 3) as k_price,
  p.market_side as poly_team,
  ROUND(p.yes_price, 3) as p_price
FROM price_snapshots k
LEFT JOIN price_snapshots p 
  ON k.event_id = p.event_id
WHERE k.platform = 'kalshi'
  AND p.platform = 'polymarket'
  AND k.timestamp > datetime('now', '-5 minutes')
ORDER BY k.timestamp DESC
LIMIT 10;
"
```

## Files Added

- `QUERY_EXAMPLES.md` - Comprehensive SQL query templates
- `IMPROVEMENTS_v1.5.md` - This file
- `VERSION.md` - Version documentation

## Next Steps

1. **Test the new logging**: Restart bot and verify output is clearer
2. **Try the queries**: Use `QUERY_EXAMPLES.md` templates
3. **Monitor collection**: Check cycle summaries make sense
4. **Find arbitrage**: Use the arbitrage queries to spot opportunities

---

**Date**: December 30, 2025  
**Status**: Ready to restart and test  
**Changes**: Logging clarity + SQL query templates

