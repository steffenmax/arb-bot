#!/bin/bash
# View By Game - Shows all odds for each game grouped together

cd "$(dirname "$0")"

echo "======================================================================="
echo "ODDS BY GAME (Latest Snapshots)"
echo "======================================================================="
echo ""

sqlite3 data/market_data.db << 'EOF'
.mode column
.headers on
.width 22 10 18 8 10

WITH latest AS (
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
    SUBSTR(event_id, 14, 20) as game,
    platform,
    team,
    ROUND(yes_price, 3) as price,
    ROUND(volume, 0) as volume
FROM latest
WHERE rn = 1
ORDER BY event_id, platform, team;
EOF

echo ""
echo "======================================================================="
echo "EXPLANATION:"
echo "  Each game shows 4 rows:"
echo "    - 2 Kalshi rows (one per team, YES price = team wins)"
echo "    - 2 Polymarket rows (one per team, direct win probability)"
echo "  "
echo "  Team names:"
echo "    Kalshi uses city names (Boston, Utah, etc.)"
echo "    Polymarket uses team names (Celtics, Jazz, etc.)"
echo "======================================================================="

