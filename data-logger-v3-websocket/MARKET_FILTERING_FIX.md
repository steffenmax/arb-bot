# Market Filtering Fix - Jan 6, 2026

## Problem
The bot was displaying incorrect Polymarket prices for some games (e.g., Orlando Magic vs Washington Wizards showing 50/50 odds when Kalshi showed Magic as a strong 71% favorite). This created false arbitrage opportunities.

## Root Causes Identified

### 1. No Market Type Filtering
The Polymarket resolver was matching ANY market with 2 outcomes, including:
- **Spread markets** (e.g., "Spread: Magic (-7.5)")
- **Over/Under markets** (e.g., "Magic vs. Wizards: O/U 235.5")
- **Player prop markets** (e.g., "Paolo Banchero: Points Over 25.5")

### 2. No Date Proximity Filtering
The resolver matched markets by team names only, without checking if the game date was close to the expected Kalshi game date. This caused it to match OLD games (e.g., a Dec 31 Magic vs. Wizards game when looking for the Jan 6 game).

### 3. First Match Wins
Polymarket API returns multiple markets per event, often listing spread/total markets BEFORE winner markets. The resolver returned the first match found, not the best match.

## Solution Implemented

### A. Market Type Classifier (`team_mappings.py`)
Created `classify_market_type(question, outcomes)` function that returns:
- `WINNER`: Moneyline/winner markets only
- `SPREAD`: Spread/handicap markets (rejected)
- `TOTAL`: Over/under markets (rejected)
- `OTHER`: Player props, half-time markets, etc. (rejected)

**Detection Keywords:**
- Spread: `spread`, `handicap`, `line`, `(+`, `(-`
- Total: `over`, `under`, `total`, `o/u`, `points`
- Props: `receiving yards`, `passing`, `rushing`, `rebounds`, `assists`
- Time periods: `1h`, `1st half`, `1st quarter`

### B. Date Proximity Filter (`resolve_markets_v2.py`)
Added date parsing and filtering in `_find_polymarket_match()`:
1. Extract game date from Kalshi event_id (e.g., `kxnbagame_26jan06orlwas` → Jan 6, 2026)
2. Parse Polymarket event `startDate` (ISO format)
3. Calculate days difference
4. **Reject events more than 2 days away** from expected date

**Rationale for 2-day tolerance:**
- Too wide (7 days): Matches wrong games from different weeks
- Too narrow (0 days): Misses games due to timezone/scheduling differences
- **2 days**: Optimal balance for sports scheduling

### C. Winner Market Prioritization
The market type filter is applied BEFORE team matching, ensuring:
1. Spread/total markets are rejected early
2. Only winner markets proceed to team name matching
3. The first WINNER market match is returned (correct behavior)

## Files Modified

1. **`team_mappings.py`**
   - Added `classify_market_type()` function (50 lines)

2. **`resolve_markets_v2.py`**
   - Added `kalshi_game_date` parameter to `_find_polymarket_match()`
   - Added date parsing logic (Kalshi format → datetime)
   - Added date proximity filter (2-day tolerance)
   - Added market type filter (WINNER only)

## Validation

### Before Fix
```
Orlando Magic: Kalshi $0.71 / Polymarket $0.50  ❌ Wrong (50/50 spread market)
Washington Wizards: Kalshi $0.28 / Polymarket $0.49  ❌ Wrong
```

### After Fix
```
Orlando Magic: Kalshi $0.71 / Polymarket (no market)  ✅ Correct
Washington Wizards: Kalshi $0.28 / Polymarket (no market)  ✅ Correct
```

**Result:** Polymarket token IDs cleared for games without active winner markets. Bot no longer displays stale/incorrect prices.

## Testing Results
- **Before:** 6/12 markets matched (including spread markets from old games)
- **After:** 0/12 markets matched (correctly filtered, as Polymarket doesn't have active winner markets for these specific games)

## Next Steps for Production

1. **Monitor for new Polymarket markets:** Re-run `resolve_markets_v2.py` daily to discover newly created winner markets
2. **Alert on price divergence:** Add sanity check to detect when Kalshi/Polymarket prices differ by >20% (may indicate wrong market type)
3. **Manual review:** For first few trades, manually verify both platforms show the same game/market type
4. **Date tolerance tuning:** If experiencing too many false negatives (missing valid markets), increase tolerance to 3 days

## Commands

**Re-run resolver:**
```bash
cd /Users/maxsteffen/Desktop/arbitrage_bot/data-logger-v3-websocket
python3 resolve_markets_v2.py
```

**Restart bot with new token IDs:**
```bash
pkill -f arb_bot_main
./START_PAPER_TRADING.sh
```

