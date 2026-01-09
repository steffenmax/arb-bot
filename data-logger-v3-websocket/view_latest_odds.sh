#!/bin/bash
# View Latest Odds - Shows current prices with team names clearly labeled

cd "$(dirname "$0")"

echo "======================================================================="
echo "LATEST MARKET ODDS (Last 5 Minutes)"
echo "======================================================================="
echo ""

sqlite3 data/market_data.db << 'EOF'
.mode column
.headers on
.width 19 10 20 10 10 8

SELECT 
    datetime(timestamp) as time,
    platform,
    CASE 
        WHEN platform = 'kalshi' THEN market_side || ' (YES)'
        ELSE market_side
    END as team,
    ROUND(yes_price, 3) as price,
    ROUND(volume, 0) as volume,
    SUBSTR(event_id, -3) as game_id
FROM price_snapshots
WHERE timestamp > datetime('now', '-5 minutes')
ORDER BY timestamp DESC, platform, event_id
LIMIT 40;
EOF

echo ""
echo "======================================================================="
echo "NOTES:"
echo "  - Kalshi: Shows 'Team (YES)' = price for this team to WIN"
echo "  - Polymarket: Shows direct team win probability"
echo "  - Game ID: Last 3 chars of event_id (team abbreviations)"
echo "======================================================================="

