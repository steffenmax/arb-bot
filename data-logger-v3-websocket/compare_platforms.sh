#!/bin/bash
# Compare Platforms - Shows Kalshi vs Polymarket odds side-by-side

cd "$(dirname "$0")"

echo "======================================================================="
echo "KALSHI VS POLYMARKET COMPARISON (Latest Snapshots)"
echo "======================================================================="
echo ""

sqlite3 data/market_data.db << 'EOF'
.mode column
.headers on
.width 25 15 8 15 8 8

WITH latest_snapshots AS (
    SELECT 
        event_id,
        platform,
        market_side as team,
        yes_price,
        volume,
        timestamp,
        ROW_NUMBER() OVER (PARTITION BY event_id, platform, market_side ORDER BY timestamp DESC) as rn
    FROM price_snapshots
    WHERE timestamp > datetime('now', '-10 minutes')
)
SELECT 
    SUBSTR(k.event_id, 14, 12) as game,
    k.team as kalshi_team,
    ROUND(k.yes_price, 3) as k_price,
    p.team as poly_team,
    ROUND(p.yes_price, 3) as p_price,
    ROUND(ABS(k.yes_price - p.yes_price), 3) as diff
FROM latest_snapshots k
LEFT JOIN latest_snapshots p 
    ON k.event_id = p.event_id 
    AND p.platform = 'polymarket'
    AND p.rn = 1
WHERE k.platform = 'kalshi'
    AND k.rn = 1
ORDER BY diff DESC
LIMIT 20;
EOF

echo ""
echo "======================================================================="
echo "NOTES:"
echo "  - 'diff' = Price difference between platforms (arbitrage opportunity)"
echo "  - Higher diff = bigger potential arbitrage"
echo "  - Team names may differ (e.g., 'Boston' vs 'Celtics')"
echo "======================================================================="

