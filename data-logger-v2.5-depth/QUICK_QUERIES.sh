#!/bin/bash
# Quick Database Queries - Copy/Paste Ready
# Navigate to: data-logger-v1.5

DB="data/market_data.db"

echo "=== QUICK DATABASE QUERIES ==="
echo ""
echo "1. LATEST PRICES WITH TEAM NAMES"
echo "   sqlite3 $DB \""
echo "   SELECT datetime(timestamp), platform, market_side, ROUND(yes_price,3), ROUND(volume,0)"
echo "   FROM price_snapshots ORDER BY timestamp DESC LIMIT 20;\""
echo ""

echo "2. COMPARE PLATFORMS (with team names)"
echo "   sqlite3 -column -header $DB \""
echo "   SELECT "
echo "     k.market_side as kalshi_team,"
echo "     ROUND(k.yes_price, 3) as k_price,"
echo "     p.market_side as poly_team,"
echo "     ROUND(p.yes_price, 3) as p_price,"
echo "     ROUND(ABS(k.yes_price - p.yes_price), 3) as diff"
echo "   FROM price_snapshots k"
echo "   LEFT JOIN price_snapshots p ON k.event_id = p.event_id"
echo "   WHERE k.platform = 'kalshi' AND p.platform = 'polymarket'"
echo "     AND k.timestamp > datetime('now', '-5 minutes')"
echo "   ORDER BY k.timestamp DESC LIMIT 20;\""
echo ""

echo "3. FIND ARBITRAGE (price diff > 5%)"
echo "   sqlite3 -column -header $DB \""
echo "   SELECT "
echo "     k.market_side as kalshi_team,"
echo "     ROUND(k.yes_price, 3) as k_price,"
echo "     p.market_side as poly_team,"
echo "     ROUND(p.yes_price, 3) as p_price,"
echo "     ROUND(ABS(k.yes_price - p.yes_price), 3) as diff"
echo "   FROM price_snapshots k"
echo "   JOIN price_snapshots p ON k.event_id = p.event_id"
echo "   WHERE k.platform = 'kalshi' AND p.platform = 'polymarket'"
echo "     AND k.timestamp > datetime('now', '-5 minutes')"
echo "     AND ABS(k.yes_price - p.yes_price) > 0.05"
echo "   ORDER BY ABS(k.yes_price - p.yes_price) DESC;\""
echo ""

echo "4. COLLECTION STATUS"
echo "   sqlite3 $DB \""
echo "   SELECT platform, COUNT(*) as snapshots, MAX(datetime(timestamp)) as latest"
echo "   FROM price_snapshots GROUP BY platform;\""
echo ""

echo "5. TEAM NAME MAPPING"
echo "   sqlite3 -column -header $DB \""
echo "   SELECT DISTINCT k.market_side as kalshi, p.market_side as polymarket"
echo "   FROM price_snapshots k"
echo "   JOIN price_snapshots p ON k.event_id = p.event_id"
echo "   WHERE k.platform = 'kalshi' AND p.platform = 'polymarket'"
echo "   ORDER BY k.market_side;\""
echo ""

echo "=== RUN THESE DIRECTLY ==="
echo ""

# You can also run this script: bash QUICK_QUERIES.sh

