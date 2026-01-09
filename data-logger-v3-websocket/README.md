# Prediction Market Data Logger v3 - WebSocket

Clean, focused tool for collecting price data from Kalshi and Polymarket using WebSocket connections.

**⚠️ READ-ONLY:** This tool collects data. It does NOT execute trades.

**Version:** v3 - WebSocket  
**Data:** Fresh start - no historical data  
**Updated:** January 6, 2026 - Synced with latest v2.5-depth changes

---

## Quick Start

**You're ready to go!** Your system is configured with 20 NBA games.

```bash
# Start collecting data
python3 data_logger.py --hours 24

# After collection, analyze for arbitrage
python3 analysis/analyze_opportunities.py
```

**See `START_HERE.md` for detailed walkthrough.**

---

## What This Does

Collects price data from prediction markets to answer:
- Do arbitrage opportunities exist?
- How often do they occur?
- Are they profitable after fees?
- How long do they last?

**Purpose:** Determine if building a trading bot is worthwhile BEFORE investing time in execution logic.

---

## Project Structure

```
data-logger/
├── START_HERE.md             ← Read this first!
├── README.md                 ← You are here
├── FIXED_KALSHI_DISCOVERY.md ← How discovery works
│
├── config/
│   ├── settings.json         ← API credentials (configured ✓)
│   └── markets.json          ← 20 NBA games (configured ✓)
│
├── data/
│   └── market_data.db        ← Price data stored here
│
├── analysis/
│   ├── analyze_opportunities.py  ← Analyze collected data
│   └── README.md             ← Analysis guide
│
├── Core Scripts:
├── data_logger.py            ← Main collection script
├── discover_markets_improved.py  ← Find more markets
├── add_polymarket_ids.py     ← Add Polymarket IDs
├── db_setup.py               ← Database setup
├── kalshi_client.py          ← Kalshi API wrapper
├── polymarket_client.py      ← Polymarket API wrapper
└── test_kalshi_auth.py       ← Test credentials
```

---

## Your Current Setup

✅ **Credentials:** Kalshi API key configured  
✅ **Markets:** 20 NBA games from Kalshi  
✅ **Database:** SQLite database created  
✅ **Ready:** Just run `data_logger.py`

---

## Main Commands

### Data Collection

```bash
# Collect for 24 hours
python3 data_logger.py --hours 24

# Test run (1 hour)
python3 data_logger.py --hours 1

# Stop anytime with Ctrl+C
```

### Analysis

```bash
# Analyze collected data
python3 analysis/analyze_opportunities.py

# With wider time window
python3 analysis/analyze_opportunities.py --window 10
```

### Market Discovery

```bash
# Find NBA markets
python3 discover_markets_improved.py --sport NBA --save

# Find NHL markets
python3 discover_markets_improved.py --sport NHL --save

# Find NFL markets
python3 discover_markets_improved.py --sport NFL --save
```

### Add Polymarket

```bash
# Interactive - add Polymarket IDs
python3 add_polymarket_ids.py --interactive --input config/markets.json
```

---

## How It Works

### 1. Market Discovery

Uses correct Kalshi series tickers (found in your old bot):
- **NBA:** `KXNBAGAME`
- **NHL:** `KXNHLGAME`
- **NFL:** `KXNFLGAME`

Extracts team info from `yes_sub_title` field.

### 2. Data Collection

Every 30 seconds (configurable):
- Fetches prices from configured markets
- Stores in SQLite database
- Logs statistics
- Handles errors gracefully

### 3. Analysis

After collection:
- Finds time-matched prices (within 5-second window)
- Calculates arbitrage opportunities
- Accounts for fees (7% Kalshi + 2% Polymarket)
- Generates detailed report

---

## Understanding Arbitrage

### The Concept

Buy complementary outcomes where total cost < guaranteed payout.

**Example:**
- Kalshi: Portland YES = $0.55 (Portland wins)
- Polymarket: OKC YES = $0.42 (OKC wins)
- Total cost: $0.97
- Guaranteed payout: $1.00
- Profit before fees: $0.03

### The Formula

```
Total Cost = Kalshi Price + Polymarket Price
Gross Profit = $1.00 - Total Cost
Fees = (Kalshi Price × 0.07) + (Polymarket Price × 0.02)
Net Profit = Gross Profit - Fees
```

**Arbitrage exists when:** Total Cost < $1.00  
**Profitable when:** Net Profit > $0

### Important: YES Refers To

Each Kalshi market has `yes_refers_to` field:
```json
{
  "yes_refers_to": "Portland",
  "kalshi": {
    "markets": {
      "main": "KXNBAGAME-25DEC31POROKC-POR"
    }
  }
}
```

This tells you: **Kalshi YES = Portland wins**

For arbitrage, you'd pair this with:
- **Polymarket YES = OKC wins** (opposite team)

---

## Configuration

### API Credentials

**File:** `config/settings.json`

Already configured with your Kalshi API key. To change:
```json
{
  "kalshi": {
    "enabled": true,
    "api_key": "your-api-key",
    "private_key_path": "../kalshi_private_key.pem"
  },
  "collection": {
    "interval_seconds": 30
  }
}
```

### Markets

**File:** `config/markets.json`

Currently has 20 NBA games. Each market:
```json
{
  "event_id": "unique_id",
  "description": "Portland vs Oklahoma City",
  "sport": "NBA",
  "teams": {
    "yes_team": "Portland"
  },
  "kalshi": {
    "enabled": true,
    "markets": {
      "main": "KXNBAGAME-25DEC31POROKC-POR"
    },
    "yes_refers_to": "Portland"
  },
  "polymarket": {
    "enabled": false,
    "markets": {}
  }
}
```

---

## Adding Polymarket

Currently you only have Kalshi. To detect arbitrage, add Polymarket:

### Method 1: Interactive
```bash
python3 add_polymarket_ids.py --interactive --input config/markets.json
```

### Method 2: Manual

1. Go to https://polymarket.com
2. Search for your game
3. Find the condition ID
4. Add to `config/markets.json`:

```json
"polymarket": {
  "enabled": true,
  "markets": {
    "game": "CONDITION_ID_HERE"
  }
}
```

---

## Database

**Location:** `data/market_data.db`

**Tables:**
- `tracked_markets` - Which markets we're monitoring
- `price_snapshots` - All collected price data
- `arbitrage_opportunities` - Detected opportunities
- `collection_logs` - Health monitoring

**Query example:**
```bash
sqlite3 data/market_data.db "SELECT COUNT(*) FROM price_snapshots"
```

---

## Analysis

After collecting data:

```bash
python3 analysis/analyze_opportunities.py
```

**Output:**
- Overall statistics
- Per-market analysis
- Best opportunities found
- Timing analysis
- Profitability after fees

**See `analysis/README.md` for details.**

---

## Troubleshooting

### No markets configured
```bash
cat config/markets.json
# Should show 20 markets
```

### Authentication failed
```bash
python3 test_kalshi_auth.py
```

### Database error
```bash
python3 db_setup.py
```

### Want different markets
```bash
python3 discover_markets_improved.py --sport NBA --save
cp markets_discovered_improved.json config/markets.json
```

---

## Key Files

### Core Scripts
- `data_logger.py` - Main data collection
- `discover_markets_improved.py` - Find markets via API
- `add_polymarket_ids.py` - Add Polymarket IDs
- `db_setup.py` - Database schema
- `kalshi_client.py` - Kalshi API wrapper
- `polymarket_client.py` - Polymarket API wrapper

### Configuration
- `config/settings.json` - API credentials
- `config/markets.json` - Markets to track

### Documentation
- `START_HERE.md` - Quick start guide
- `FIXED_KALSHI_DISCOVERY.md` - How discovery works
- `analysis/README.md` - Analysis guide

---

## What's Next?

### 1. Start Collecting (Now)
```bash
python3 data_logger.py --hours 24
```

### 2. Add Polymarket (Optional)
```bash
python3 add_polymarket_ids.py --interactive --input config/markets.json
```

### 3. Analyze Results (After 24 hours)
```bash
python3 analysis/analyze_opportunities.py
```

### 4. Make Decision

Based on analysis results:
- **No opportunities?** Markets are efficient, don't build bot
- **Opportunities but unprofitable?** Fees too high
- **Profitable opportunities?** Consider building execution system

---

## Security

- ✅ `config/settings.json` in `.gitignore`
- ✅ `*.db` files in `.gitignore`
- ✅ API keys protected
- ✅ No credentials in code

**Never commit credentials to git!**

---

## Support

**Documentation:**
- `START_HERE.md` - Quick start
- `FIXED_KALSHI_DISCOVERY.md` - Discovery details
- `analysis/README.md` - Analysis guide
- `config/README.md` - Configuration help

**All scripts have `--help` option.**

---

## Summary

✅ **Ready to use** - 20 NBA games configured  
✅ **Credentials set** - Kalshi API working  
✅ **Database created** - SQLite ready  
✅ **Just run** - `python3 data_logger.py --hours 24`

**See `START_HERE.md` for step-by-step walkthrough.**

---

**TL;DR:** Run `python3 data_logger.py --hours 24` to start collecting data from 20 NBA games. Analyze after 24 hours to see if arbitrage opportunities exist.
