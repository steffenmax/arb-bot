# Resolving Polymarket Token IDs

## Why This Is Needed

To subscribe to Polymarket WebSocket orderbooks, you need **clobTokenIds** for each market outcome. These are unique identifiers that Polymarket uses internally.

## How It Works

The `resolve_polymarket_tokens.py` script:

1. **Fetches** active markets from Polymarket CLOB API
2. **Fuzzy matches** them to your canonical events (based on team names + sport)
3. **Extracts** `clobTokenIds` for each outcome (e.g., Team A, Team B)
4. **Updates** `config/markets.json` with the token IDs

## Running the Resolver

```bash
cd /Users/maxsteffen/Desktop/arbitrage_bot/data-logger-v3-websocket
../venv/bin/python3 resolve_polymarket_tokens.py
```

## What You'll See

```
============================================================
POLYMARKET TOKEN ID RESOLVER
============================================================

Fetching active markets from Polymarket CLOB...
✓ Fetched 847 active markets

Matching 12 canonical events to Polymarket markets...

  ✓ Matched 'chicago vs green bay' → 'NFL: Chicago vs Green Bay' (score: 0.95)
    Token IDs: {'Chicago': '0xabc123...', 'Green Bay': '0xdef456...'}
  ✓ Matched 'cleveland vs indiana' → 'NBA: Cleveland vs Indiana' (score: 0.88)
    Token IDs: {'Cleveland': '0x789xyz...', 'Indiana': '0x012abc...'}
  ⚠️  No good match for 'carolina vs los angeles r' (best score: 0.42)

============================================================
Resolution complete: 10/12 markets
============================================================

✓ Token ID resolution complete!
```

## What Gets Updated

**Before** (`config/markets.json`):
```json
{
  "event_id": "kxnflgame_26jan10gbchi",
  "teams": {
    "team_a": "Chicago",
    "team_b": "Green Bay"
  },
  "polymarket": {
    "enabled": true,
    "markets": {
      "slug": "nfl-gb-chi-2026-01-10"
    }
  }
}
```

**After**:
```json
{
  "event_id": "kxnflgame_26jan10gbchi",
  "teams": {
    "team_a": "Chicago",
    "team_b": "Green Bay"
  },
  "poly_token_ids": {
    "Chicago": "0xabc123...",
    "Green Bay": "0xdef456..."
  },
  "poly_condition_id": "0x789...",
  "poly_question": "NFL: Chicago vs Green Bay",
  "polymarket": {
    "enabled": true,
    "markets": {
      "slug": "nfl-gb-chi-2026-01-10"
    }
  }
}
```

## Matching Algorithm

The fuzzy matcher scores each Polymarket market based on:

- **Team names in question** (0.4 points each)
- **Team names in outcomes** (0.3 points each)
- **Both teams present** (0.5 bonus)
- **String similarity** (0.3 × similarity ratio)

Only matches with **score > 0.5** are accepted.

## Manual Overrides

If the fuzzy matcher fails or gets it wrong, you can manually add token IDs:

```json
{
  "event_id": "my-event",
  "poly_token_ids": {
    "Team A": "0xYOUR_TOKEN_ID_HERE",
    "Team B": "0xYOUR_TOKEN_ID_HERE"
  },
  "poly_condition_id": "0xYOUR_CONDITION_ID"
}
```

**Finding Token IDs Manually**:
1. Go to https://polymarket.com
2. Find your market
3. Open browser DevTools → Network tab
4. Look for API calls to `/markets` or `/orderbook`
5. Copy the `clobTokenIds` from the response

## After Resolution

Once token IDs are resolved, run the bot:

```bash
./START_PAPER_TRADING.sh
```

You should now see:
```
Subscribing to markets...
  [Kalshi] Batch subscribing to 24 markets...
  ✓ Batch subscription sent for 24 markets
  [Polymarket] Sending subscription for: Chicago
  [Polymarket] Token ID: 0xabc123...
  ✓ Subscription request sent: Chicago
  [Polymarket] Sending subscription for: Green Bay
  [Polymarket] Token ID: 0xdef456...
  ✓ Subscription request sent: Green Bay
✓ Subscribed to 36 market feeds (12 events)
```

## Troubleshooting

### Issue: No matches found

**Cause**: Team names don't match Polymarket's naming

**Fix**: Check Polymarket.com to see how they name the teams, then update your `teams` in markets.json to match

### Issue: Wrong market matched

**Cause**: Fuzzy matcher picked the wrong sport or event

**Fix**: Make the match more specific:
- Ensure `sport` field is set correctly (NFL, NBA, etc.)
- Use full team names (not abbreviations)
- Add date information if markets are ambiguous

### Issue: Token IDs already resolved but still getting warning

**Cause**: The script doesn't overwrite existing token IDs

**Fix**: Either:
1. Delete `poly_token_ids` from markets.json and re-run
2. Or manually update the token IDs in markets.json

## API Endpoints Used

- **CLOB API**: `https://clob.polymarket.com/markets`
  - Returns active markets with clobTokenIds
  - No authentication required for public markets

- **Gamma API**: `https://gamma-api.polymarket.com` (alternative)
  - More detailed market information
  - Same token ID structure

## Backup

The script automatically creates a backup:
```
config/markets.json.backup
```

If something goes wrong, you can restore:
```bash
cp config/markets.json.backup config/markets.json
```

## Next Steps

After resolving token IDs:
1. ✅ Review the updated `config/markets.json`
2. ✅ Run `./START_PAPER_TRADING.sh`
3. ✅ Verify Polymarket subscriptions in bot output
4. ✅ Check dashboard for Polymarket orderbook data

---

**Ready to resolve?**

```bash
../venv/bin/python3 resolve_polymarket_tokens.py
```

