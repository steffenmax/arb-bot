# Data Logger v1.5 - Quick Start

## ✅ Issues Fixed

### 1. **Bot Logging Now Clean & Transparent**

**Before** (confusing):
```
[2/20] Portland vs Oklahoma City Winner?
  ✓ Kalshi: 1 market(s) collected
  ↷ Polymarket: already fetched this cycle  ❌ Confusing!
```

**After** (clear):
```
[1/20] Portland vs Oklahoma City Winner?
  ✓ Kalshi: Portland
  ✓ Polymarket: 2 outcome(s) collected
  
[2/20] Portland vs Oklahoma City Winner?
  ✓ Kalshi: Oklahoma City
  (Polymarket: silent - already got both teams)
```

### 2. **SQLite Queries Show Team Names**

**Your data DOES have team names** - they're in the `market_side` column!

**Quick View**:
```bash
sqlite3 data/market_data.db "
SELECT datetime(timestamp), platform, market_side, ROUND(yes_price,3)
FROM price_snapshots ORDER BY timestamp DESC LIMIT 20;
"
```

**Output**:
```
2025-12-30 18:26:11|kalshi    |Boston       |0.715
2025-12-30 18:26:11|polymarket|Celtics      |0.715
2025-12-30 18:26:10|kalshi    |Utah         |0.285
2025-12-30 18:26:11|polymarket|Jazz         |0.285
```

## 📊 Best Queries

### Latest Prices (Most Common)
```bash
cd data-logger-v1.5
sqlite3 -column -header data/market_data.db "
SELECT 
  datetime(timestamp) as time,
  platform,
  market_side as team,
  ROUND(yes_price, 3) as price,
  ROUND(volume, 0) as volume
FROM price_snapshots
ORDER BY timestamp DESC
LIMIT 30;
"
```

### Compare Kalshi vs Polymarket
```bash
sqlite3 -column -header data/market_data.db "
SELECT 
  k.market_side as kalshi_team,
  ROUND(k.yes_price, 3) as k_price,
  p.market_side as poly_team,
  ROUND(p.yes_price, 3) as p_price,
  ROUND(ABS(k.yes_price - p.yes_price), 3) as diff
FROM price_snapshots k
LEFT JOIN price_snapshots p ON k.event_id = p.event_id
WHERE k.platform = 'kalshi' AND p.platform = 'polymarket'
  AND k.timestamp > datetime('now', '-5 minutes')
ORDER BY k.timestamp DESC
LIMIT 20;
"
```

### Find Arbitrage (Price Differences > 5%)
```bash
sqlite3 -column -header data/market_data.db "
SELECT 
  k.market_side as kalshi_team,
  ROUND(k.yes_price, 3) as k_price,
  p.market_side as poly_team,
  ROUND(p.yes_price, 3) as p_price,
  ROUND(ABS(k.yes_price - p.yes_price), 3) as diff
FROM price_snapshots k
JOIN price_snapshots p ON k.event_id = p.event_id
WHERE k.platform = 'kalshi' AND p.platform = 'polymarket'
  AND k.timestamp > datetime('now', '-5 minutes')
  AND ABS(k.yes_price - p.yes_price) > 0.05
ORDER BY ABS(k.yes_price - p.yes_price) DESC;
"
```

## 🎯 Team Name Mapping

| Kalshi (City Name) | Polymarket (Team Name) |
|-------------------|------------------------|
| Boston | Celtics |
| Golden State | Warriors |
| Portland | Trail Blazers |
| Oklahoma City | Thunder |
| Utah | Jazz |
| Charlotte | Hornets |
| Orlando | Magic |
| Indiana | Pacers |
| Phoenix | Suns |
| Cleveland | Cavaliers |
| Minnesota | Timberwolves |
| Atlanta | Hawks |
| Denver | Nuggets |
| Toronto | Raptors |
| Milwaukee | Bucks |
| Washington | Wizards |
| Chicago | Bulls |
| New Orleans | Pelicans |
| New York | Knicks |
| San Antonio | Spurs |

## 🔄 Restart Bot to See New Logging

```bash
cd "/Users/maxsteffen/Library/Mobile Documents/com~apple~CloudDocs/arbitrage_bot/data-logger-v1.5"

# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null

# Restart
caffeinate -i python3 data_logger.py --hours 24
```

**New output will show**:
- ✅ Team names in logging
- ✅ Clear cycle summaries
- ✅ No confusing "already fetched" messages

## 📁 New Files

- `QUERY_EXAMPLES.md` - Comprehensive query templates
- `QUICK_QUERIES.sh` - Copy/paste ready queries
- `IMPROVEMENTS_v1.5.md` - Detailed changelog
- `README_v1.5.md` - This file

## 🚀 Current Status

**Your bot is still running** with the old code. When you restart:
1. Logging will be cleaner
2. Cycle summaries will be clearer
3. All queries above will work (they already do!)

---

**Bottom Line**: 
- ✅ Team names ARE in your database (always were!)
- ✅ Logging is now cleaner (after restart)
- ✅ Use the queries above to see team names clearly

