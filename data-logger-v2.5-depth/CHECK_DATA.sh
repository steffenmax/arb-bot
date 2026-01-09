#!/bin/bash
# Quick database check with team names

DB="data/market_data.db"

echo "═══════════════════════════════════════════════════════════════════"
echo "📊 DATABASE CHECK - v1.5"
echo "═══════════════════════════════════════════════════════════════════"
echo ""

echo "1️⃣  OVERALL STATS:"
echo "───────────────────────────────────────────────────────────────────"
sqlite3 "$DB" "
SELECT 
  COUNT(*) as total_snapshots,
  COUNT(DISTINCT event_id) as unique_games,
  MIN(timestamp) as first_snapshot,
  MAX(timestamp) as last_snapshot,
  ROUND((julianday(MAX(timestamp)) - julianday(MIN(timestamp))) * 24, 2) as hours_running
FROM price_snapshots;
"
echo ""

echo "2️⃣  BREAKDOWN BY PLATFORM:"
echo "───────────────────────────────────────────────────────────────────"
sqlite3 "$DB" "
SELECT 
  platform,
  COUNT(*) as snapshots,
  COUNT(DISTINCT event_id) as games,
  COUNT(DISTINCT market_side) as unique_teams
FROM price_snapshots
GROUP BY platform;
"
echo ""

echo "3️⃣  LATEST DATA (WITH TEAM NAMES):"
echo "───────────────────────────────────────────────────────────────────"
sqlite3 "$DB" -header -column "
SELECT 
  platform,
  market_side as team,
  ROUND(yes_price, 3) as price,
  ROUND(yes_bid, 3) as bid,
  ROUND(yes_ask, 3) as ask,
  volume,
  datetime(timestamp) as time
FROM price_snapshots
WHERE timestamp > datetime('now', '-5 minutes')
ORDER BY timestamp DESC
LIMIT 20;
"
echo ""

echo "4️⃣  SAMPLE: SIDE-BY-SIDE COMPARISON (ONE GAME):"
echo "───────────────────────────────────────────────────────────────────"
sqlite3 "$DB" -header -column "
SELECT 
  tm.description as game,
  ps.platform,
  ps.market_side as team,
  ROUND(ps.yes_price, 3) as price,
  ROUND(ps.yes_bid, 3) as bid,
  ROUND(ps.yes_ask, 3) as ask,
  ps.volume,
  datetime(ps.timestamp) as time
FROM price_snapshots ps
JOIN tracked_markets tm ON ps.event_id = tm.event_id
WHERE ps.timestamp = (
  SELECT MAX(timestamp) 
  FROM price_snapshots 
  WHERE event_id = ps.event_id
)
LIMIT 10;
"
echo ""

echo "5️⃣  COLLECTION CYCLE PERFORMANCE:"
echo "───────────────────────────────────────────────────────────────────"
sqlite3 "$DB" -header -column "
SELECT 
  COUNT(*) as total_cycles,
  ROUND(AVG(duration_seconds), 2) as avg_duration,
  ROUND(MIN(duration_seconds), 2) as fastest,
  ROUND(MAX(duration_seconds), 2) as slowest,
  SUM(kalshi_success) as total_kalshi,
  SUM(polymarket_success) as total_polymarket
FROM collection_logs
WHERE completed_at IS NOT NULL;
"
echo ""

echo "═══════════════════════════════════════════════════════════════════"
echo "✅ Database check complete!"
echo "═══════════════════════════════════════════════════════════════════"

