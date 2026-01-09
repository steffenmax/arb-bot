# Command Reference

Quick reference for all data logger commands.

---

## Essential Commands

### Start Data Collection
```bash
python3 data_logger.py --hours 24
```

### Stop Collection
```
Ctrl+C (stops gracefully)
```

### Analyze Data
```bash
python3 analysis/analyze_opportunities.py
```

---

## Market Discovery

### Find NBA Markets
```bash
python3 discover_markets_improved.py --sport NBA --save
cp markets_discovered_improved.json config/markets.json
```

### Find NHL Markets
```bash
python3 discover_markets_improved.py --sport NHL --save
cp markets_discovered_improved.json config/markets.json
```

### Find NFL Markets
```bash
python3 discover_markets_improved.py --sport NFL --save
cp markets_discovered_improved.json config/markets.json
```

---

## Polymarket Integration

### Add Polymarket IDs (Interactive)
```bash
python3 add_polymarket_ids.py --interactive --input config/markets.json
```

### Add from JSON File
```bash
python3 add_polymarket_ids.py --poly-ids polymarket_ids.json --input config/markets.json
```

---

## Testing & Verification

### Test Kalshi Authentication
```bash
python3 test_kalshi_auth.py
```

### Test Database Setup
```bash
python3 db_setup.py
```

### Check Data Collection Progress
```bash
sqlite3 data/market_data.db "SELECT COUNT(*) FROM price_snapshots"
```

### View Latest Prices
```bash
sqlite3 data/market_data.db "SELECT * FROM price_snapshots ORDER BY timestamp DESC LIMIT 10"
```

---

## Data Logger Options

### Basic
```bash
python3 data_logger.py --hours 24
```

### Custom Duration
```bash
python3 data_logger.py --hours 1    # 1 hour test
python3 data_logger.py --hours 48   # 2 days
python3 data_logger.py --hours 168  # 1 week
```

### Custom Config
```bash
python3 data_logger.py --hours 24 --config my_settings.json
python3 data_logger.py --hours 24 --markets my_markets.json
```

---

## Analysis Options

### Basic
```bash
python3 analysis/analyze_opportunities.py
```

### Wider Time Window
```bash
python3 analysis/analyze_opportunities.py --window 10
```

### Custom Database
```bash
python3 analysis/analyze_opportunities.py --db /path/to/database.db
```

---

## Database Queries

### Count Snapshots
```bash
sqlite3 data/market_data.db "SELECT COUNT(*) FROM price_snapshots"
```

### Count by Platform
```bash
sqlite3 data/market_data.db "SELECT platform, COUNT(*) FROM price_snapshots GROUP BY platform"
```

### Recent Prices
```bash
sqlite3 data/market_data.db "SELECT * FROM price_snapshots ORDER BY timestamp DESC LIMIT 20"
```

### Collection Stats
```bash
sqlite3 data/market_data.db "SELECT * FROM collection_logs ORDER BY started_at DESC LIMIT 5"
```

### View Markets
```bash
sqlite3 data/market_data.db "SELECT event_id, description FROM tracked_markets"
```

---

## File Operations

### View Current Markets
```bash
cat config/markets.json
```

### Count Markets
```bash
cat config/markets.json | grep event_id | wc -l
```

### Backup Database
```bash
cp data/market_data.db data/market_data_backup_$(date +%Y%m%d).db
```

### View Logs
```bash
ls -lh logs/
tail -f logs/data_logger.log  # If logging enabled
```

---

## Setup Commands

### Install Dependencies
```bash
pip3 install -r requirements.txt
```

### Run Setup Script
```bash
./setup.sh
```

### Create Fresh Database
```bash
rm data/market_data.db
python3 db_setup.py
```

---

## Discovery Options

### Basic Discovery
```bash
python3 discover_markets_improved.py --sport NBA
```

### Save Results
```bash
python3 discover_markets_improved.py --sport NBA --save
```

### Custom Output
```bash
python3 discover_markets_improved.py --sport NBA --save --output my_markets.json
```

---

## Workflow Examples

### Example 1: Fresh NBA Collection
```bash
python3 discover_markets_improved.py --sport NBA --save
cp markets_discovered_improved.json config/markets.json
python3 data_logger.py --hours 24
python3 analysis/analyze_opportunities.py
```

### Example 2: Add Polymarket to Existing
```bash
python3 add_polymarket_ids.py --interactive --input config/markets.json
python3 data_logger.py --hours 24
python3 analysis/analyze_opportunities.py
```

### Example 3: Multiple Sports
```bash
python3 discover_markets_improved.py --sport NBA --save --output nba.json
python3 discover_markets_improved.py --sport NHL --save --output nhl.json
# Manually merge nba.json and nhl.json into config/markets.json
python3 data_logger.py --hours 24
```

---

## Help Commands

### Show Help
```bash
python3 data_logger.py --help
python3 discover_markets_improved.py --help
python3 add_polymarket_ids.py --help
python3 analysis/analyze_opportunities.py --help
```

---

## Quick Checks

### Is Everything Working?
```bash
# Test auth
python3 test_kalshi_auth.py

# Check markets
cat config/markets.json | grep event_id | wc -l

# Check database
ls -lh data/market_data.db
```

### How Much Data Collected?
```bash
sqlite3 data/market_data.db "
  SELECT 
    COUNT(*) as snapshots,
    MIN(timestamp) as first,
    MAX(timestamp) as last
  FROM price_snapshots
"
```

---

## Common Issues

### "No markets configured"
```bash
# Make sure markets.json exists and has markets
cat config/markets.json
```

### "Authentication failed"
```bash
# Test credentials
python3 test_kalshi_auth.py
```

### "Database locked"
```bash
# Stop data logger first, then try again
```

### "Import error"
```bash
# Install dependencies
pip3 install -r requirements.txt
```

---

## Your Current Setup

- **Markets:** 20 NBA games
- **Platform:** Kalshi only (can add Polymarket)
- **Collection interval:** 30 seconds
- **Database:** SQLite at `data/market_data.db`

---

## Next Steps

1. **Now:** `python3 data_logger.py --hours 24`
2. **+24 hours:** `python3 analysis/analyze_opportunities.py`
3. **Then:** Decide based on results

---

**Your command:** `cd data-logger && python3 data_logger.py --hours 24`

🚀 Let's collect some data!

