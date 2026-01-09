# Useful SQL Queries for Market Data

## Quick View - Latest Prices with Team Names

### Both Platforms Side-by-Side
```sql
SELECT 
  datetime(timestamp) as time,
  platform,
  market_side as team,
  ROUND(yes_price, 3) as price,
  ROUND(volume, 0) as volume
FROM price_snapshots
WHERE timestamp > datetime('now', '-10 minutes')
ORDER BY timestamp DESC, platform
LIMIT 40;
```

### Latest Price for Each Team (Last Snapshot)
```sql
WITH latest AS (
  SELECT MAX(timestamp) as max_time
  FROM price_snapshots
)
SELECT 
  datetime(p.timestamp) as time,
  p.platform,
  p.market_side as team,
  ROUND(p.yes_price, 3) as price,
  ROUND(p.yes_bid, 3) as bid,
  ROUND(p.yes_ask, 3) as ask,
  ROUND(p.volume, 0) as volume
FROM price_snapshots p, latest
WHERE p.timestamp = latest.max_time
ORDER BY p.platform, p.market_side;
```

## Compare Platforms - Same Game

### Compare Kalshi vs Polymarket for One Game
```sql
-- Boston vs Utah example
SELECT 
  datetime(timestamp) as time,
  platform,
  market_side as team,
  ROUND(yes_price, 3) as price,
  ROUND(yes_bid, 3) as bid,
  ROUND(yes_ask, 3) as ask,
  ROUND(volume, 0) as volume
FROM price_snapshots
WHERE event_id LIKE '%bosuta%'
  AND timestamp > datetime('now', '-30 minutes')
ORDER BY timestamp DESC, platform, market_side
LIMIT 20;
```

### Side-by-Side Comparison (Latest Only)
```sql
SELECT 
  k.market_side as kalshi_team,
  ROUND(k.yes_price, 3) as kalshi_price,
  p.market_side as poly_team,
  ROUND(p.yes_price, 3) as poly_price,
  ROUND(k.yes_price - p.yes_price, 3) as price_diff,
  datetime(k.timestamp) as time
FROM price_snapshots k
LEFT JOIN price_snapshots p 
  ON k.event_id = p.event_id 
  AND k.market_side = p.market_side
  AND ABS(julianday(k.timestamp) - julianday(p.timestamp)) < 0.001
WHERE k.platform = 'kalshi'
  AND p.platform = 'polymarket'
  AND k.timestamp > datetime('now', '-5 minutes')
ORDER BY k.timestamp DESC
LIMIT 20;
```

## Find Arbitrage Opportunities

### Price Differences > 5%
```sql
WITH kalshi_prices AS (
  SELECT 
    event_id,
    market_side,
    yes_price as k_price,
    timestamp
  FROM price_snapshots
  WHERE platform = 'kalshi'
    AND timestamp > datetime('now', '-5 minutes')
),
poly_prices AS (
  SELECT 
    event_id,
    market_side,
    yes_price as p_price,
    timestamp
  FROM price_snapshots
  WHERE platform = 'polymarket'
    AND timestamp > datetime('now', '-5 minutes')
)
SELECT 
  k.market_side as team,
  ROUND(k.k_price, 3) as kalshi,
  ROUND(p.p_price, 3) as polymarket,
  ROUND(ABS(k.k_price - p.p_price), 3) as difference,
  datetime(k.timestamp) as time
FROM kalshi_prices k
JOIN poly_prices p 
  ON k.event_id = p.event_id
  AND k.market_side = p.market_side
  AND ABS(julianday(k.timestamp) - julianday(p.timestamp)) < 0.001
WHERE ABS(k.k_price - p.p_price) > 0.05
ORDER BY ABS(k.k_price - p.p_price) DESC;
```

## Data Quality Checks

### Count Snapshots by Platform
```sql
SELECT 
  platform,
  COUNT(*) as total_snapshots,
  COUNT(DISTINCT event_id) as unique_games,
  MIN(datetime(timestamp)) as first_snapshot,
  MAX(datetime(timestamp)) as last_snapshot,
  ROUND((julianday(MAX(timestamp)) - julianday(MIN(timestamp))) * 24, 1) as hours_collected
FROM price_snapshots
GROUP BY platform;
```

### Missing Data (Games with No Polymarket)
```sql
SELECT DISTINCT
  k.event_id,
  k.market_side as team,
  'Missing Polymarket data' as issue
FROM price_snapshots k
LEFT JOIN price_snapshots p 
  ON k.event_id = p.event_id 
  AND p.platform = 'polymarket'
WHERE k.platform = 'kalshi'
  AND p.event_id IS NULL
  AND k.timestamp > datetime('now', '-30 minutes');
```

## Price Movement Tracking

### Track One Team's Price Over Time
```sql
SELECT 
  datetime(timestamp) as time,
  platform,
  market_side as team,
  ROUND(yes_price, 3) as price,
  ROUND(volume, 0) as volume
FROM price_snapshots
WHERE market_side LIKE '%Thunder%'  -- Change team name here
  OR market_side LIKE '%Oklahoma City%'
ORDER BY timestamp DESC
LIMIT 50;
```

### Price Changes in Last Hour
```sql
WITH recent AS (
  SELECT * FROM price_snapshots
  WHERE timestamp > datetime('now', '-1 hour')
),
first_prices AS (
  SELECT 
    platform,
    market_side,
    MIN(timestamp) as first_time,
    yes_price as first_price
  FROM recent
  GROUP BY platform, market_side
),
last_prices AS (
  SELECT 
    platform,
    market_side,
    MAX(timestamp) as last_time,
    yes_price as last_price
  FROM recent
  GROUP BY platform, market_side
)
SELECT 
  f.platform,
  f.market_side as team,
  ROUND(f.first_price, 3) as starting_price,
  ROUND(l.last_price, 3) as current_price,
  ROUND(l.last_price - f.first_price, 3) as change,
  ROUND((l.last_price - f.first_price) / f.first_price * 100, 1) as pct_change
FROM first_prices f
JOIN last_prices l 
  ON f.platform = l.platform 
  AND f.market_side = l.market_side
WHERE ABS(l.last_price - f.first_price) > 0.01
ORDER BY ABS(l.last_price - f.first_price) DESC;
```

## Export for Analysis

### Export to CSV (run in terminal)
```bash
sqlite3 -header -csv data/market_data.db \
  "SELECT * FROM price_snapshots WHERE timestamp > datetime('now', '-1 hour')" \
  > data_export.csv
```

### Summary Stats
```sql
SELECT 
  platform,
  market_side as team,
  COUNT(*) as snapshots,
  ROUND(AVG(yes_price), 3) as avg_price,
  ROUND(MIN(yes_price), 3) as min_price,
  ROUND(MAX(yes_price), 3) as max_price,
  ROUND(MAX(yes_price) - MIN(yes_price), 3) as price_range
FROM price_snapshots
WHERE timestamp > datetime('now', '-1 hour')
GROUP BY platform, market_side
HAVING COUNT(*) > 10
ORDER BY platform, market_side;
```

---

## Quick Reference

### View Latest (Most Common)
```bash
cd data-logger-v1.5
sqlite3 data/market_data.db "
SELECT datetime(timestamp), platform, market_side, ROUND(yes_price,3), ROUND(volume,0)
FROM price_snapshots
ORDER BY timestamp DESC LIMIT 20;
"
```

### Check Collection Status
```bash
sqlite3 data/market_data.db "
SELECT platform, COUNT(*) as count, MAX(datetime(timestamp)) as latest
FROM price_snapshots
GROUP BY platform;
"
```

### Find Arbitrage
```bash
sqlite3 data/market_data.db "
-- Use the 'Price Differences > 5%' query above
"
```

