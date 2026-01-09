# Data Query Guide - v1.5

Quick reference for viewing your collected market data with **clear team names**.

## Quick Queries (Use These!)

### 1. View Latest Odds (Best for Quick Check)
```bash
./view_latest_odds.sh
```

**Shows**: Last 5 minutes of data with team names clearly labeled
- Kalshi: "Boston (YES)" = price for Boston to win
- Polymarket: "Celtics" = direct win probability

**Example Output**:
```
time                 platform    team                 price     volume    
2025-12-30 18:26:11  kalshi      Boston (YES)         0.715     97549
2025-12-30 18:26:11  polymarket  Celtics              0.715     868951
```

### 2. Compare Platforms (Best for Arbitrage)
```bash
./compare_platforms.sh
```

**Shows**: Kalshi vs Polymarket side-by-side with price differences
- Highest `diff` = best arbitrage opportunity

**Example Output**:
```
game          kalshi_team  k_price  poly_team   p_price  diff
ec31dentor    Denver       0.290    Nuggets     0.265    0.025
```

### 3. View By Game (Best for Understanding Structure)
```bash
./view_by_game.sh
```

**Shows**: All 4 prices per game (2 Kalshi + 2 Polymarket)

**Example Output**:
```
game              platform    team          price    volume
ec30bosuta_bos    kalshi      Boston        0.715    97549
ec30bosuta_uta    kalshi      Utah          0.285    300700
ec30bosuta_uta    polymarket  Celtics       0.715    868951
ec30bosuta_uta    polymarket  Jazz          0.285    868951
```

---

## Understanding Team Names

### Why Different Names?

**Kalshi** uses **city names**:
- Boston, Utah, Golden State, Oklahoma City, etc.

**Polymarket** uses **team names**:
- Celtics, Jazz, Warriors, Thunder, etc.

### Mapping Guide

| Game | Kalshi | Polymarket |
|------|--------|------------|
| BOS vs UTA | Boston / Utah | Celtics / Jazz |
| GSW vs CHA | Golden State / Charlotte | Warriors / Hornets |
| OKC vs POR | Oklahoma City / Portland | Thunder / Trail Blazers |
| MIN vs ATL | Minnesota / Atlanta | Timberwolves / Hawks |
| DEN vs TOR | Denver / Toronto | Nuggets / Raptors |

---

## How Kalshi YES/NO Works

Kalshi has **2 separate markets per game**:

### Example: Boston vs Utah

**Market 1**: Boston market
- YES = Boston wins (0.715)
- NO = Boston loses (0.285)

**Market 2**: Utah market  
- YES = Utah wins (0.285)
- NO = Utah loses (0.715)

**Key Point**: The YES price for one team equals the NO price for the other team!

---

## Custom Queries

### Latest snapshot for a specific team:
```bash
sqlite3 data/market_data.db "
SELECT datetime(timestamp), platform, market_side, yes_price, volume
FROM price_snapshots
WHERE market_side LIKE '%Boston%' OR market_side LIKE '%Celtics%'
ORDER BY timestamp DESC
LIMIT 10;
"
```

### Count snapshots by platform:
```bash
sqlite3 data/market_data.db "
SELECT platform, COUNT(*) as total
FROM price_snapshots
GROUP BY platform;
"
```

### Price movements over time:
```bash
sqlite3 data/market_data.db "
SELECT 
    datetime(timestamp) as time,
    market_side as team,
    yes_price
FROM price_snapshots
WHERE market_side = 'Boston'
    AND timestamp > datetime('now', '-1 hour')
ORDER BY timestamp;
"
```

### Find biggest arbitrage opportunities:
```bash
sqlite3 data/market_data.db "
WITH latest AS (
    SELECT 
        event_id,
        platform,
        market_side,
        yes_price,
        ROW_NUMBER() OVER (PARTITION BY event_id, platform, market_side ORDER BY timestamp DESC) as rn
    FROM price_snapshots
)
SELECT 
    k.market_side as kalshi_team,
    k.yes_price as kalshi_price,
    p.market_side as poly_team,
    p.yes_price as poly_price,
    ABS(k.yes_price - p.yes_price) as difference
FROM latest k
JOIN latest p ON k.event_id = p.event_id
WHERE k.platform = 'kalshi'
    AND p.platform = 'polymarket'
    AND k.rn = 1
    AND p.rn = 1
ORDER BY difference DESC
LIMIT 10;
"
```

---

## Database Schema

### `price_snapshots` Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-increment ID |
| `event_id` | TEXT | Unique game identifier |
| `platform` | TEXT | "kalshi" or "polymarket" |
| `market_id` | TEXT | Platform-specific market ID |
| **`market_side`** | **TEXT** | **Team name (THIS IS WHAT YOU WANT!)** |
| `yes_price` | REAL | Price/probability |
| `no_price` | REAL | Inverse price (Kalshi only) |
| `yes_bid` | REAL | Best bid price |
| `yes_ask` | REAL | Best ask price |
| `volume` | REAL | Trading volume |
| `liquidity` | REAL | Market liquidity |
| `timestamp` | DATETIME | When collected |

**Key Column**: `market_side` contains the team name you want to see!

---

## Tips

1. **Use the scripts** - They're designed to show team names clearly
2. **Check volume** - Low volume = less reliable prices
3. **Compare timestamps** - Make sure data is recent
4. **Team names differ** - Boston = Celtics, Golden State = Warriors
5. **Kalshi YES price** - Is the probability that team wins

---

## Troubleshooting

### "No such file or directory"
Make sure you're in the `data-logger-v1.5` directory:
```bash
cd "/Users/maxsteffen/Library/Mobile Documents/com~apple~CloudDocs/arbitrage_bot/data-logger-v1.5"
```

### Scripts not executable
```bash
chmod +x *.sh
```

### No recent data
Check if bot is running:
```bash
ps aux | grep data_logger
```

### Want to see ALL data (not just recent)
Remove the timestamp filter in queries:
```sql
-- Change this:
WHERE timestamp > datetime('now', '-10 minutes')

-- To this:
WHERE 1=1
```

---

**Updated**: December 30, 2025  
**Version**: 1.5

