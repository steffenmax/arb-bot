# Configuration Guide

This folder contains configuration files for the data logger.

## ⚠️ Security Warning

**NEVER commit `settings.json` to git!** It contains your API credentials. The `.gitignore` file should already protect it, but be careful.

## Files

### `settings.json` - API Credentials and System Settings

**✅ Already Configured!** Your Kalshi credentials have been automatically migrated from your old bot.

Contains:
- **Kalshi API key**: Migrated from your `.env` file
- **Kalshi private key path**: Points to your existing `kalshi_private_key.pem`
- **Collection settings**: How often to collect data (default: 30 seconds)
- **Database path**: Where to store the SQLite database

**To verify setup:**
```bash
cd ..
python3 test_kalshi_auth.py
```

If you need to change settings:
1. Open `settings.json`
2. Adjust collection interval if desired (30-60 seconds recommended)
3. Update database path if you want it elsewhere

### `markets.json` - Markets to Track

Defines which specific markets to monitor.

**⚡ Quick Setup with Auto-Discovery:**

Instead of manually finding market IDs, use the automated finder:

```bash
cd ..
python3 find_markets.py --sport NBA --save
python3 find_markets.py --sport NHL --save
```

This will:
1. Search Kalshi API for active NBA/NHL markets
2. Display all found markets grouped by game
3. Save to `markets_discovered.json`
4. You can then review and copy into `markets.json`

**Manual Structure (if needed):**
```json
{
  "event_id": "unique_identifier",
  "description": "Human readable name",
  "sport": "NBA",
  "event_date": "2025-01-15T19:30:00Z",
  "kalshi": {
    "enabled": true,
    "markets": {
      "team_a_yes": "KALSHI_TICKER",
      "team_b_yes": "KALSHI_TICKER"
    }
  },
  "polymarket": {
    "enabled": true,
    "markets": {
      "team_a": "POLYMARKET_CONDITION_ID",
      "team_b": "POLYMARKET_CONDITION_ID"
    }
  }
}
```

## Finding Market IDs

### ⚡ Automated Method (Recommended)

Use the market finder script:

```bash
cd ..  # Go to data-logger directory

# Find NBA markets
python3 find_markets.py --sport NBA --save

# Find NHL markets  
python3 find_markets.py --sport NHL --save

# Custom limit
python3 find_markets.py --sport NBA --limit 100 --save
```

**Output:** `markets_discovered.json` - Ready to copy into `markets.json`

**Benefits:**
- Automatically finds all active markets
- Groups by game/event
- Shows volume, status, close time
- Pre-formatted JSON structure
- No manual searching needed

### Manual Methods

**Kalshi - Method 1: Through Website**
1. Go to https://kalshi.com
2. Search for your event (e.g., "Lakers Celtics")
3. Click on the market you want
4. The ticker is displayed on the page (format: `EVENT-DATE-THRESHOLD`)
   - Example: `HIGHNY-25JAN01-B32.5`

**Kalshi - Method 2: Through API**
```python
from kalshi_client import KalshiClient

client = KalshiClient(
    api_key="your_key",
    private_key_path="../kalshi_private_key.pem"
)

# Search for markets
markets = client.search_markets(query="Lakers")
for market in markets:
    print(f"{market['ticker']}: {market['title']}")
```

**Polymarket Markets:**

**Method 1: Through Website**
1. Go to https://polymarket.com
2. Search for your event
3. Click on the market
4. The condition ID is in the URL or you can find it in the page source
   - Format: Usually a long hex string starting with `0x`

**Method 2: Through API**
```python
from polymarket_client import PolymarketClient

client = PolymarketClient()

# Search for markets
markets = client.search_markets(query="Lakers Celtics")
for market in markets:
    print(f"{market.get('condition_id')}: {market.get('question')}")
```

**Method 3: Browser DevTools**
1. Open the market page on Polymarket
2. Open browser DevTools (F12)
3. Go to Network tab
4. Look for API calls - condition IDs are in the responses

## Important Notes

### Arbitrage Setup

For arbitrage detection to work, you need to track **complementary outcomes**:

✅ **Correct:**
- Kalshi: Lakers to WIN
- Polymarket: Celtics to WIN (opposite team)

OR

- Kalshi: Lakers YES
- Polymarket: Lakers NO (opposite outcome)

❌ **Incorrect:**
- Kalshi: Lakers YES
- Polymarket: Lakers YES (same outcome - no arbitrage possible)

### Event Matching

Make sure the event IDs are unique and descriptive. Use a consistent naming pattern:

- `{team_a}_{team_b}_{date}` (e.g., `lakers_celtics_2025_01_15`)
- `{sport}_{teams}_{date}` (e.g., `nba_lal_bos_20250115`)

### Disabling Markets

To temporarily stop tracking a market without deleting it:
```json
"kalshi": {
  "enabled": false,
  ...
}
```

Or disable the entire market by setting both to false.

## Example: Adding a New Market

1. Find the event you want to track
2. Get the Kalshi ticker(s)
3. Get the Polymarket condition ID(s)
4. Add to `markets.json`:

```json
{
  "event_id": "bucks_heat_2025_01_18",
  "description": "Bucks vs Heat - January 18, 2025",
  "sport": "NBA",
  "event_date": "2025-01-18T19:00:00Z",
  "teams": {
    "team_a": "Bucks",
    "team_b": "Heat"
  },
  "kalshi": {
    "enabled": true,
    "markets": {
      "team_a_yes": "NBA-BUCKS-18JAN25-YES",
      "team_b_yes": "NBA-HEAT-18JAN25-YES"
    }
  },
  "polymarket": {
    "enabled": true,
    "markets": {
      "team_a": "0xabcd1234...",
      "team_b": "0xefgh5678..."
    }
  }
}
```

5. Save and restart the data logger

## Troubleshooting

**"Configuration file not found"**
- Make sure you're running the data logger from the `data-logger/` directory
- Or provide the full path: `--config /full/path/to/config/settings.json`

**"Authentication failed"**
- Double-check your Kalshi credentials in `settings.json`
- Make sure there are no extra spaces or quotes
- Verify your account works by logging into https://kalshi.com

**"No markets configured"**
- Make sure at least one market has `enabled: true`
- Check the JSON syntax is valid (use a JSON validator)

**Market IDs not working**
- Verify the market is still active/open
- Check for typos in the ticker/condition ID
- Use the API client test scripts to verify IDs

