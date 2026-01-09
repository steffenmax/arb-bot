# Storage Management Guide

## 📊 Current Situation (as of audit)

**Total space used**: 5.1 GB

### Breakdown:
- **data-logger-v2.5-depth**: 3.1 GB (active, needed)
  - `market_data.db`: 3.1 GB
  - 2 million price snapshots
  - 12 million orderbook snapshots
  - Growing at ~440 MB/day
  
- **old-bot**: 1.2 GB (**can be deleted**)
  - Old log files from December
  - No longer needed
  
- **data-logger-v1, v1.5, v2**: 844 MB total (**can be deleted**)
  - Old database versions
  - You're on v2.5-depth now

## 🚀 Quick Cleanup (Save ~2 GB)

Run the automated cleanup script:

```bash
cd data-logger-v2.5-depth
./cleanup_storage.sh
```

This will safely delete:
- ✅ `old-bot/` folder (1.2 GB)
- ✅ `data-logger-v1/` (2.2 MB)
- ✅ `data-logger-v1.5/` (421 MB)
- ✅ `data-logger-v2/` (421 MB)
- ✅ Old `arbitrage.db` in root (1.8 MB)

**Your current v2.5-depth data is NOT touched!**

## 🔄 Automatic Database Cleanup (Ongoing)

The dashboard now automatically cleans old market data:

### What Gets Cleaned
- **Price snapshots** older than 7 days
- **Orderbook snapshots** older than 7 days
- Runs every time you start the dashboard

### What's Kept Forever
- ✅ **Arbitrage opportunities** (valuable trading data!)
- ✅ Recent market data (last 7 days)
- ✅ Config files and scripts

### When It Runs
```bash
./START_DASHBOARD.sh
```

You'll see:
```
✓ Removed 1,500,000 old price snapshots, 10,000,000 old orderbook snapshots
```

This frees up ~2-3 GB of space automatically!

## 📈 Expected Storage Usage

### With 7-Day Retention
- **Steady state**: ~1.5-2 GB (after initial cleanup)
- **Growth**: Plateaus at 7 days of data
- **No manual intervention needed**

### Database Growth Pattern
| Days | Price Snapshots | Orderbook Snapshots | Estimated Size |
|------|-----------------|---------------------|----------------|
| 1 day | ~280k | ~1.7M | ~450 MB |
| 3 days | ~840k | ~5.2M | ~1.3 GB |
| 7 days | ~2M | ~12M | ~3.1 GB |
| After cleanup | ~280k | ~1.7M | ~450 MB |

### Why Is Orderbook Data So Large?

Each orderbook snapshot stores:
- Multiple price levels (up to 100 per side)
- Size at each price level
- For both Yes and No markets
- For multiple markets simultaneously
- Every few seconds

**12 million orderbook snapshots** = detailed depth data for precise arbitrage detection.

## 🛠️ Manual Database Cleanup

If you want to manually clean the database without starting the dashboard:

```bash
cd data-logger-v2.5-depth

# Clean data older than 7 days
sqlite3 data/market_data.db "DELETE FROM price_snapshots WHERE timestamp < datetime('now', '-7 days')"
sqlite3 data/market_data.db "DELETE FROM orderbook_snapshots WHERE timestamp < datetime('now', '-7 days')"

# Reclaim disk space
sqlite3 data/market_data.db "VACUUM"
```

## 🎯 Optimization Tips

### 1. Adjust Retention Period
If you don't need 7 days of data, reduce it in `live_dashboard.py`:

```python
def cleanup_old_market_data(retention_days=7):  # Change this
```

**Options**:
- `1` day → ~450 MB
- `3` days → ~1.3 GB
- `7` days → ~3.1 GB (default)

### 2. Reduce Collection Frequency
Edit `data_logger_depth.py` to collect less often:

```python
COLLECTION_INTERVAL = 2  # seconds (currently collecting every 2 sec)
```

Change to `5` or `10` seconds to reduce data volume by 2-5x.

### 3. Collect Fewer Markets
Edit `config/markets.json` to track only the games you care about most.

## 📁 What NOT to Delete

**Keep these**:
- ✅ `data-logger-v2.5-depth/` - Your active bot
- ✅ `data/market_data.db` - Current database (but clean old data)
- ✅ `data/arb_opportunities.csv` - Your trading opportunities log
- ✅ `config/markets.json` - Market configuration
- ✅ All Python scripts and shell scripts

**Safe to delete**:
- ❌ `old-bot/` - Old logs
- ❌ `data-logger-v1/`, `v1.5/`, `v2/` - Old versions
- ❌ Log files in `logs/` older than a few days
- ❌ `__pycache__/` folders (regenerated automatically)

## 🔍 Monitor Storage

Check current usage:
```bash
# Total usage
du -sh /Users/maxsteffen/Desktop/arbitrage_bot

# By folder
du -h -d 1 /Users/maxsteffen/Desktop/arbitrage_bot | sort -rh

# Database size
du -sh data-logger-v2.5-depth/data/market_data.db

# Database stats
sqlite3 data-logger-v2.5-depth/data/market_data.db "SELECT 
  (SELECT COUNT(*) FROM price_snapshots) as prices,
  (SELECT COUNT(*) FROM orderbook_snapshots) as orderbooks"
```

## ⚡ Quick Actions

### Free up space NOW:
```bash
cd data-logger-v2.5-depth
./cleanup_storage.sh
./START_DASHBOARD.sh  # Cleans old DB data
```

### Check what's using space:
```bash
cd /Users/maxsteffen/Desktop/arbitrage_bot
du -h -d 1 . | sort -rh
```

### Emergency full cleanup (nuclear option):
```bash
# Back up arbitrage opportunities first!
cp data-logger-v2.5-depth/data/arb_opportunities.csv ~/Desktop/arb_backup.csv

# Delete entire database and start fresh
rm data-logger-v2.5-depth/data/market_data.db
cd data-logger-v2.5-depth
python3 db_setup.py
```

---

**Summary**: Run `./cleanup_storage.sh` once to save ~2 GB, then the dashboard auto-cleans old data every time it starts. Your arbitrage opportunities are kept forever! 🎉

