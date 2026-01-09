# Arbitrage Bot Architecture Documentation

**Generated:** December 29, 2025  
**Purpose:** Complete system architecture analysis for cross-market sports arbitrage detection and execution

---

## Table of Contents
1. [High-Level Overview](#high-level-overview)
2. [Data Flow Analysis](#data-flow-analysis)
3. [Decision Logic](#decision-logic)
4. [Execution Path](#execution-path)
5. [Error-Prone Areas](#error-prone-areas)
6. [Critical Issues & Recommendations](#critical-issues--recommendations)

---

## 1. High-Level Overview

### Main Entry Point
**Primary:** `run_kalshi_polymarket_fixed.py` (Line 823-824)
- Production bot optimized for Kalshi vs Polymarket arbitrage
- Includes deduplication, fill verification, and sport-aware matching

**Alternative:** `run_bot.py` (Line 349-355)
- General-purpose bot with multi-platform support
- Less mature, basic matching only

### Core Modules

| Module | Purpose | Key Components |
|--------|---------|----------------|
| `src/data_sources/kalshi_client.py` | Kalshi API client | Market fetching, orderbook, authentication |
| `src/polymarket_client.py` | Polymarket API client (read-only) | Sports events, market data |
| `src/executors/kalshi_executor.py` | Kalshi trade execution | Order placement, fill monitoring |
| `src/executors/polymarket_executor.py` | Polymarket trade execution | CLOB client, order creation |
| `src/cross_market_detector.py` | Cross-platform matching | Team normalization, arb calculation |
| `src/arbitrage_detector.py` | Generic arbitrage detection | Edge calculation, stake optimization |
| `src/smart_matcher.py` | Fuzzy event matching | Team similarity, moneyline filtering |
| `src/database.py` | Persistence layer | Opportunity logging, trade records |
| `config/settings.py` | Configuration | Trading limits, API endpoints |

### System Flowchart

```
┌─────────────────────────────────────────────────────────────────┐
│                     ARBITRAGE BOT MAIN LOOP                     │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. DATA ACQUISITION (scan_for_opportunities)                   │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                   │
│  ┌──────────────────┐              ┌──────────────────┐        │
│  │  Kalshi Client   │              │ Polymarket Client│        │
│  │  (kalshi_client) │              │ (polymarket_     │        │
│  │                  │              │  client)         │        │
│  └────────┬─────────┘              └─────────┬────────┘        │
│           │                                   │                 │
│           │ GET /markets?                     │ GET /events?    │
│           │ series=KXNFLGAME                  │ tag_id=450      │
│           │ status=open                       │ (NFL)           │
│           │                                   │                 │
│           ▼                                   ▼                 │
│  ┌─────────────────────────────────────────────────────┐       │
│  │   Raw Market Data                                   │       │
│  │   • Kalshi: 200+ tickers (YES/NO pairs)            │       │
│  │   • Polymarket: 30-100 events with embedded markets│       │
│  └─────────────────────────────────────────────────────┘       │
└───────────────────────────────────┬─────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. DATA TRANSFORMATION                                          │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                   │
│  Kalshi Processing (get_sports_markets):                        │
│  • Fetch orderbook depth for each ticker (parallel)            │
│  • Extract: yes_price, no_price, spread, liquidity             │
│  • Calculate: yes_ask from no_bid (binary complement)          │
│  • Parse yes_team field (critical for matching)                │
│  • Deduplicate: KXNFLGAME-25DEC28-TEN vs -NO → 1 game         │
│                                                                   │
│  Polymarket Processing (get_polymarket_markets):                │
│  • Filter events by date pattern in slug                        │
│  • Parse outcomes and outcomePrices from JSON                   │
│  • Extract clobTokenIds for trading                            │
│  • Store: condition_id, token_ids, prices                      │
│                                                                   │
│  Output Format:                                                  │
│  {                                                               │
│    'ticker': 'KXNFLGAME-25DEC28-TEN',                          │
│    'title': 'Tennessee @ New Orleans Winner?',                 │
│    'yes_team': 'Tennessee',  ◄── CRITICAL for matching         │
│    'yes_price': 0.48,                                           │
│    'no_price': 0.54,                                            │
│    'spread': 0.06                                               │
│  }                                                               │
└───────────────────────────────────┬─────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. EVENT MATCHING (match_markets)                              │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                   │
│  For each Kalshi market:                                        │
│  1. Extract sport from ticker (NFL/NBA/NHL)                     │
│  2. Parse date (25DEC28 format)                                 │
│  3. Get team aliases from TEAM_MAPPINGS                         │
│                                                                   │
│  For each Polymarket market:                                    │
│  1. Check if sport matches                                      │
│  2. Check if BOTH Polymarket teams appear in Kalshi title      │
│     (uses _get_team_aliases for fuzzy matching)                │
│  3. If match found, store game_id to prevent duplicates        │
│                                                                   │
│  Output: List of matched pairs with game_id                     │
└───────────────────────────────────┬─────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. ARBITRAGE DETECTION (calculate_arbitrage)                   │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                   │
│  For each matched pair:                                         │
│                                                                   │
│  CRITICAL TEAM MAPPING:                                         │
│  • Use Kalshi yes_team to determine which Poly outcome matches │
│  • Example: yes_team="Tennessee"                                │
│    → Find which Poly outcome contains "Tennessee"              │
│    → Hedge = Kalshi YES + Poly OPPOSITE team                   │
│                                                                   │
│  Calculate Two Strategies:                                      │
│  Strategy 1: Kalshi YES + Poly opposite                        │
│    edge_1 = (1.0 - (kalshi_yes + poly_opposite)) * 100        │
│                                                                   │
│  Strategy 2: Kalshi NO + Poly opposite                         │
│    edge_2 = (1.0 - (kalshi_no + poly_opposite)) * 100         │
│                                                                   │
│  Filters Applied:                                               │
│  • edge >= MIN_EDGE_PERCENTAGE (default 5%)                     │
│  • kalshi_spread <= 0.15 (reject wide spreads)                 │
│                                                                   │
│  Output: Best opportunity (if any) with execution details       │
└───────────────────────────────────┬─────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. TRADE DECISION                                              │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                   │
│  IF opportunity found:                                           │
│    • Check if game_id already in executed_games set            │
│    • If new game:                                               │
│      → Calculate stakes (MAX_STAKE_PER_TRADE / 2 per leg)      │
│      → Add game_id to executed_games                           │
│      → Proceed to execution                                     │
│    • If already traded:                                         │
│      → Skip (prevents duplicate trades)                         │
│                                                                   │
│  IF PAPER_TRADING_MODE = true:                                  │
│    • Log opportunity                                            │
│    • Send Discord notification                                  │
│    • Continue scanning                                          │
│                                                                   │
│  IF PAPER_TRADING_MODE = false:                                 │
│    • Execute trade (see section 5)                             │
└───────────────────────────────────┬─────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  6. TRADE EXECUTION (execute_trade)                             │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                   │
│  Parallel Execution:                                            │
│                                                                   │
│  ┌─────────────────────┐         ┌─────────────────────┐       │
│  │  KALSHI LEG         │         │  POLYMARKET LEG     │       │
│  ├─────────────────────┤         ├─────────────────────┤       │
│  │ 1. Calculate price: │         │ 1. Fetch current    │       │
│  │    price = expected │         │    best_ask from    │       │
│  │    + 0.15 (cross    │         │    orderbook        │       │
│  │    spread)          │         │ 2. Add 0.01 (aggr.) │       │
│  │ 2. POST /orders     │         │ 3. Create order via │       │
│  │    {ticker, side,   │         │    ClobClient       │       │
│  │     qty, price}     │         │ 4. Post to CLOB API │       │
│  │ 3. Wait for fill    │         │ 5. Wait for fill    │       │
│  │    (5s timeout)     │         │    (5s timeout)     │       │
│  │ 4. Poll GET /orders │         │ 6. Poll get_order() │       │
│  │    /order_id        │         │                     │       │
│  │    every 0.3s       │         │                     │       │
│  └─────────────────────┘         └─────────────────────┘       │
│           │                                 │                   │
│           └────────────┬────────────────────┘                   │
│                        ▼                                        │
│              Check Fill Status:                                 │
│              • Both filled? → Success ✓                         │
│              • One filled? → Partial ⚠️  (hedge needed)         │
│              • Neither? → Failed ✗                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Flow Analysis

### External API Calls

#### Kalshi API (`src/data_sources/kalshi_client.py`)

| Endpoint | Method | Purpose | Rate Limit | Auth |
|----------|--------|---------|------------|------|
| `/markets` | GET | Fetch markets by series | 18/min | RSA signature |
| `/markets/{ticker}/orderbook` | GET | Get bid/ask prices | 18/min | RSA signature |
| `/markets/{ticker}` | GET | Get single market details | 18/min | RSA signature |
| `/portfolio/orders` | POST | Place order | 18/min | RSA signature |
| `/portfolio/orders/{id}` | GET | Check order status | 18/min | RSA signature |
| `/portfolio/orders/{id}` | DELETE | Cancel order | 18/min | RSA signature |
| `/portfolio/balance` | GET | Check balance | 18/min | RSA signature |

**Key Data Retrieved:**
```python
{
    'markets': [
        {
            'ticker': 'KXNFLGAME-25DEC28NOTEN-TEN',
            'title': 'Tennessee @ New Orleans Winner?',
            'subtitle': '...',
            'yes_sub_title': 'Tennessee',  # CRITICAL: Which team YES refers to
            'status': 'open',
            'close_time': '2025-12-28T18:00:00Z',
            'volume': 12500,
            'yes_bid': 0.47,  # Best bid price for YES
            'yes_ask': 0.48,  # Best ask price for YES (estimated from NO bid)
            'no_bid': 0.52,
            'no_ask': 0.53
        }
    ]
}
```

**Data Transformation:**
- Line 424-525 (`get_sports_markets`): Fetches markets with parallel orderbook queries
- Line 337-422 (`get_orderbook_full`): Parses orderbook depth, calculates spreads
- Line 376-414: **CRITICAL** - Derives YES ask from NO bid (binary complement)

#### Polymarket API (`src/polymarket_client.py`)

| Endpoint | Method | Purpose | Rate Limit | Auth |
|----------|--------|---------|------------|------|
| `/events` | GET | Fetch sport events | 25/min | None |
| `/events/slug/{slug}` | GET | Get event details | 25/min | None |
| `/markets/{id}` | GET | Get market details | 25/min | None |

**Key Data Retrieved:**
```python
{
    'events': [
        {
            'slug': 'tennessee-titans-new-orleans-saints-2025-12-28',
            'title': 'Tennessee Titans vs. New Orleans Saints',
            'markets': [
                {
                    'conditionId': '0x1234...',
                    'question': 'Tennessee Titans vs. New Orleans Saints',
                    'outcomes': ['Tennessee Titans', 'New Orleans Saints'],
                    'outcomePrices': ['0.46', '0.55'],
                    'clobTokenIds': ['123456789', '987654321']  # For trading
                }
            ]
        }
    ]
}
```

**Data Transformation:**
- Line 308-391 (`get_polymarket_markets` in run_kalshi_polymarket_fixed.py): Fetches and parses events
- Line 333-385: Filters for date patterns, extracts markets with moneyline odds
- Line 365-382: Parses JSON strings for outcomes and prices

### Data Format Between Steps

#### Step 1→2: Raw API Response → Normalized Market Data

**Before (Kalshi raw):**
```python
{
    'orderbook': {
        'yes': [[47, 100], [46, 200]],  # [price_cents, quantity]
        'no': [[53, 150], [54, 180]]
    }
}
```

**After (Normalized):**
```python
{
    'ticker': 'KXNFLGAME-25DEC28-TEN',
    'yes_price': 0.48,  # Derived from orderbook
    'no_price': 0.54,
    'spread': 0.06,
    'yes_team': 'Tennessee',  # Parsed from yes_sub_title
    'yes_depth_usd': 4700.0
}
```

#### Step 2→3: Normalized Markets → Matched Pairs

```python
{
    'kalshi': {...},  # Market data from above
    'polymarket': {
        'condition_id': '0x1234...',
        'outcomes': [
            {'outcome_name': 'Tennessee Titans', 'price': 0.46, 'token_id': '123456'},
            {'outcome_name': 'New Orleans Saints', 'price': 0.55, 'token_id': '987654'}
        ]
    },
    'sport': Sport.NFL,
    'game_id': 'KXNFLGAME-25DEC28NOTEN'  # Base ticker (deduped)
}
```

#### Step 3→4: Matched Pairs → Arbitrage Opportunity

```python
{
    'edge': 7.2,  # Percentage
    'kalshi_market': {...},
    'poly_market': {...},
    'kalshi_side': 'yes',  # Which side to bet
    'kalshi_team': 'Tennessee',
    'kalshi_price': 0.48,
    'poly_outcome_index': 1,  # New Orleans (opposite team)
    'poly_team': 'New Orleans Saints',
    'poly_price': 0.55,
    'spread': 0.06,
    'game_id': 'KXNFLGAME-25DEC28NOTEN'
}
```

---

## 3. Decision Logic

### Arbitrage Detection Logic (`run_kalshi_polymarket_fixed.py:460-583`)

**Location:** `calculate_arbitrage()` function

#### Step 1: Team Mapping (Lines 470-530)
**CRITICAL SECTION** - This determines correct hedging

```python
# Extract which team Kalshi YES refers to
kalshi_yes_team = kalshi.get('yes_team', '').lower()  # e.g., "Tennessee"

# Get Polymarket outcomes
poly_team_0 = poly_outcomes[0]['outcome_name']  # "Tennessee Titans"
poly_team_1 = poly_outcomes[1]['outcome_name']  # "New Orleans Saints"

# MATCH YES TEAM TO POLYMARKET OUTCOME
aliases = self._get_team_aliases(kalshi_yes_team, sport)
yes_matches_poly_0 = any(alias in poly_team_0 for alias in aliases)
yes_matches_poly_1 = any(alias in poly_team_1 for alias in aliases)

# Determine correct pairing
if yes_matches_poly_0:
    # Kalshi YES = Poly team 0 → Hedge with Poly team 1
    yes_opposite_poly_idx = 1
    no_opposite_poly_idx = 0
elif yes_matches_poly_1:
    # Kalshi YES = Poly team 1 → Hedge with Poly team 0
    yes_opposite_poly_idx = 0
    no_opposite_poly_idx = 1
else:
    # Cannot determine mapping - WARNING
    logger.warning(f"Cannot map Kalshi yes_team '{kalshi_yes_team}' to Poly teams")
```

**Why This Is Critical:**
- Kalshi markets are binary: YES or NO
- YES might refer to Team A winning OR Team B winning
- `yes_team` field tells us which team YES refers to
- Without correct mapping, you'd bet on SAME team twice (no hedge!)

#### Step 2: Calculate Edges (Lines 532-575)

```python
# Strategy 1: Buy Kalshi YES + Buy Poly opposite team
total_cost_1 = kalshi_yes + poly_price_for_yes
edge_1 = (1.0 - total_cost_1) * 100 if total_cost_1 < 1.0 else 0

# Strategy 2: Buy Kalshi NO + Buy Poly opposite team
total_cost_2 = kalshi_no + poly_price_for_no
edge_2 = (1.0 - total_cost_2) * 100 if total_cost_2 < 1.0 else 0
```

**Example:**
- Kalshi: YES (Tennessee) = 0.48, NO = 0.54
- Polymarket: Tennessee = 0.46, New Orleans = 0.55
- Strategy 1: Kalshi YES (0.48) + Poly New Orleans (0.55) = 1.03 (no arb)
- Strategy 2: Kalshi NO (0.54) + Poly Tennessee (0.46) = 1.00 (no arb)

But if prices were:
- Kalshi: YES = 0.42, NO = 0.60
- Poly: Tennessee = 0.40, New Orleans = 0.55
- Strategy 1: 0.42 + 0.55 = 0.97 → 3% edge ✓

#### Step 3: Spread Filter (Lines 541-546)

```python
MAX_ACCEPTABLE_SPREAD = 0.15
if kalshi_spread > MAX_ACCEPTABLE_SPREAD:
    logger.debug(f"Skipping due to wide Kalshi spread: {kalshi_spread:.2f}")
    return None
```

**Purpose:** Wide spreads indicate low liquidity or stale prices. The price you see won't be executable.

#### Step 4: Validation Conditions

**Trade Signal Triggers:**
1. `edge >= MIN_EDGE_PERCENTAGE` (default 5%)
2. `kalshi_spread <= 0.15` (15 cents)
3. `game_id not in executed_games` (no duplicate trades)
4. Both markets still open
5. Valid team mapping found

---

## 4. Execution Path

### When Opportunity Detected (`run_kalshi_polymarket_fixed.py:585-673`)

#### Pre-Execution Checks
```python
game_id = opportunity['game_id']
if game_id in self.executed_games:
    logger.info(f"Skipping already traded: {game_id}")
    continue

# Mark as executed IMMEDIATELY (before actual execution)
self.executed_games.add(game_id)
```

**Purpose:** Prevent duplicate trades on same game (even if execution fails)

#### Execution Flow

##### Kalshi Leg (`src/executors/kalshi_executor.py:92-283`)

```python
# 1. AGGRESSIVE PRICING (Lines 604-606)
price_cents = min(int((opportunity['kalshi_price'] + 0.15) * 100), 95)
# Adds 15¢ to expected price to cross the spread

# 2. ORDER SUBMISSION (Line 135-136)
POST /portfolio/orders
{
    "ticker": "KXNFLGAME-25DEC28-TEN",
    "action": "buy",
    "side": "yes",
    "type": "limit",
    "count": 20,  # Quantity
    "yes_price": 60  # In cents
}

# 3. WAIT FOR FILL (Lines 160-231)
while time.time() - start_time < 5.0:
    status = get_order_status(order_id)
    
    if status.status == FILLED:
        return success
    elif status.filled_quantity > 0:
        # Partial fill - keep waiting
        continue
    
    time.sleep(0.3)

# 4. TIMEOUT HANDLING (Lines 202-231)
if filled_quantity >= quantity * 0.95:  # 95%+ filled
    return success (with partial flag)
else:
    return failure
```

##### Polymarket Leg (`src/executors/polymarket_executor.py:190-455`)

```python
# 1. FETCH CURRENT ASK (Lines 226-239)
# CRITICAL: Don't use stale expected_price
orderbook = self.get_orderbook(token_id)
if orderbook and orderbook.get('best_ask'):
    current_ask = orderbook['best_ask']
    order_price = min(current_ask + 0.01, 0.99)  # Aggressive
else:
    order_price = max_price  # Fallback

# 2. CONVERT SIZE (Lines 254-264)
size_in_tokens = size / order_price
if size_in_tokens < 5:
    size_in_tokens = 5.0  # Minimum

# 3. CREATE AND POST ORDER (Lines 266-290)
order_args = OrderArgs(
    token_id=token_id,
    price=order_price,
    size=size_in_tokens,
    side=BUY
)
signed_order = self.client.create_order(order_args)
response = self.client.post_order(signed_order, OrderType.GTC)

# 4. WAIT FOR FILL (Lines 342-412)
while time.time() - start_time < 5.0:
    status = self.get_order_status(order_id)
    
    if status.status == FILLED:
        return success
    
    time.sleep(0.3)
```

#### Result Evaluation (`run_kalshi_polymarket_fixed.py:656-673`)

```python
kalshi_filled = kalshi_result and kalshi_result.filled_quantity > 0
poly_filled = poly_result and poly_result.get('filled_size', 0) > 0

if kalshi_filled and poly_filled:
    logger.info("✅ BOTH LEGS FILLED!")
    return True
elif kalshi_filled or poly_filled:
    logger.warning("⚠️ PARTIAL EXECUTION - Manual hedge required!")
    return False
else:
    logger.error("❌ Neither leg filled")
    return False
```

### Trade Status Tracking

**In-Memory State:**
```python
self.executed_games = set()  # Tracks game_ids already traded
self.trades_executed = 0     # Counter
```

**Database Logging:**
- `ArbitrageLog` table: All detected opportunities
- `LiveTrade` table: Execution details, order IDs, fill status
- `PaperTrade` table: Simulated trades (when PAPER_TRADING_MODE=true)

---

## 5. Error-Prone Areas

### 🔴 CRITICAL: Team Mapping Bug
**Location:** `run_kalshi_polymarket_fixed.py:460-530`

**Issue:**
If `yes_team` field is empty or doesn't match Polymarket outcome names, the bot falls back to guessing:

```python
else:
    # Cannot determine mapping - log warning
    logger.warning(f"Cannot map Kalshi yes_team '{kalshi_yes_team}'")
    # Fallback to original assumption (may be wrong)
    yes_opposite_poly_idx = 1  # GUESS
    no_opposite_poly_idx = 0
    kalshi_yes_team_name = "Unknown"
```

**Impact:** Bot might bet on SAME team twice (no hedge) → guaranteed loss

**Occurrence Probability:** Medium - happens when:
- Kalshi doesn't populate `yes_sub_title` field
- Team names use different formats (e.g., "LA" vs "Los Angeles")
- New teams not in `TEAM_MAPPINGS` (Lines 84-185)

**Fix Required:** Reject opportunity if mapping fails (don't guess)

---

### 🟡 HIGH: Stale Price Execution
**Location:** `src/executors/polymarket_executor.py:190-240`

**Issue:**
Before v2.0 improvements, bot used `expected_odds` from initial scan:

```python
# OLD CODE (buggy):
order_price = expected_prob  # From 30-60 seconds ago

# FIXED CODE:
orderbook = self.get_orderbook(token_id)  # Fetch NOW
order_price = orderbook['best_ask'] + 0.01
```

**Impact:** Order placed at stale price won't fill, partial execution

**Current Status:** Fixed in v2.0 (Lines 226-239), but risk remains if:
- Orderbook fetch fails (falls back to `max_price`)
- Network delay between fetch and order submission

---

### 🟡 HIGH: Kalshi 4-Option vs Polymarket 2-Option
**Location:** Market matching logic

**The Problem:**
- Kalshi lists YES and NO as **separate tickers**:
  - `KXNFLGAME-25DEC28-TEN` (YES = Tennessee wins)
  - `KXNFLGAME-25DEC28-NO` (NO = Tennessee loses)
- Polymarket has ONE market with TWO outcomes

**Current Handling:** Deduplication in `run_kalshi_polymarket_fixed.py:398-406`

```python
seen_games = set()
for km in kalshi_markets:
    base = self._get_base_game_ticker(km.get('ticker', ''))  # Remove -TEN/-NO suffix
    if base not in seen_games:
        seen_games.add(base)
        unique_kalshi.append(km)
```

**Remaining Risk:**
If both YES and NO tickers have different prices that BOTH create arbitrage opportunities, the bot only considers ONE. It might miss the better strategy.

**Example:**
- Kalshi YES (Tennessee): 0.42
- Kalshi NO: 0.58
- Poly Tennessee: 0.40
- Poly New Orleans: 0.55

Strategy A: YES (0.42) + Poly NO (0.55) = 0.97 → 3% edge
Strategy B: NO (0.58) + Poly YES (0.40) = 0.98 → 2% edge

Bot only evaluates Strategy A (from first ticker seen).

---

### 🟡 MEDIUM: Fill Timeout Handling
**Location:** 
- `src/executors/kalshi_executor.py:160-231`
- `src/executors/polymarket_executor.py:342-412`

**Issue:**
Default timeout is 5 seconds. If order is SLOW to fill:

```python
fill_timeout = 5.0

# After timeout:
if filled_quantity >= quantity * 0.95:
    return success  # 95%+ = "good enough"
else:
    return failure  # But order might fill later!
```

**Impact:** 
- Order marked as "failed" but actually fills 10 seconds later
- Bot thinks it has unhedged position (partial execution)
- Manual intervention needed even though both sides eventually filled

**Occurrence:** More frequent during:
- High volatility (spread widening)
- Low liquidity markets
- Network congestion

---

### 🟡 MEDIUM: Spread Width Filter Bypass
**Location:** `run_kalshi_polymarket_fixed.py:541-546`

**Issue:**
Filter rejects spreads > 15 cents, but Polymarket spread not checked:

```python
MAX_ACCEPTABLE_SPREAD = 0.15
if kalshi_spread > MAX_ACCEPTABLE_SPREAD:
    return None

# But Polymarket spread NOT checked!
```

**Impact:**
Wide Polymarket spread → order won't fill → partial execution

**Current Mitigation:** Aggressive pricing (+1 cent) helps, but not guaranteed

---

### 🟢 LOW: Rate Limit Exhaustion
**Location:** `src/rate_limiter.py` (adaptive limiter)

**Issue:**
Bot makes parallel API calls:
- Kalshi: 20 parallel orderbook fetches
- Polymarket: 30 parallel event detail fetches

If rate limit hit:
```python
if hasattr(limiter, 'report_429'):
    limiter.report_429()  # Adaptive backoff
```

**Impact:** Scan takes longer, opportunities might be missed

**Current Mitigation:** Adaptive rate limiter adjusts speed based on 429 responses

---

### 🟢 LOW: Race Condition in `executed_games`
**Location:** `run_kalshi_polymarket_fixed.py:755-756`

**Issue:**
```python
self.executed_games.add(game_id)  # Not thread-safe
```

If bot runs multiple threads (not currently implemented), same game could be traded twice.

**Current Status:** Not an issue (single-threaded), but would break if parallelized

---

### 🔴 CRITICAL: Partial Execution Recovery
**Location:** `run_kalshi_polymarket_fixed.py:666-669`

**Issue:**
When only one leg fills, bot just logs a warning:

```python
elif kalshi_filled or poly_filled:
    logger.warning("⚠️ PARTIAL EXECUTION - Manual hedge required!")
    return False
```

**What's Missing:**
1. No automatic cancellation of unfilled leg
2. No hedge order placement
3. No alert with actionable instructions
4. Game marked as "executed" even though it's unhedged

**Impact:** Exposed position, potential loss exceeds calculated edge

**Recommended Fix:**
```python
# If Kalshi filled but Poly didn't:
if kalshi_filled and not poly_filled:
    # Option 1: Cancel Kalshi order (if still possible)
    kalshi_executor.cancel_order(kalshi_order_id)
    
    # Option 2: Place offsetting Kalshi order
    kalshi_executor.execute_order(ticker, opposite_side, quantity)
    
    # Option 3: Alert user with manual hedge instructions
    send_discord_alert(f"URGENT: Hedge {kalshi_team} on Polymarket manually!")
```

---

## 6. Critical Issues & Recommendations

### Issue 1: Inadequate Error Recovery
**Severity:** CRITICAL

**Problem:** No rollback mechanism for partial executions

**Recommendation:**
```python
def execute_trade_with_rollback(self, opportunity):
    kalshi_result = self.kalshi_executor.execute_order(...)
    
    if not kalshi_result.success:
        return False
    
    poly_result = self.polymarket_executor.execute_order(...)
    
    if not poly_result.success:
        # ROLLBACK: Try to cancel or offset Kalshi
        logger.error("Polymarket failed - attempting rollback")
        if kalshi_result.filled_quantity > 0:
            # Place offsetting order on Kalshi
            self.kalshi_executor.execute_order(
                ticker=opportunity['kalshi_market']['ticker'],
                side='no' if opportunity['kalshi_side'] == 'yes' else 'yes',
                quantity=kalshi_result.filled_quantity,
                price_cents=95  # Market order (high price to ensure fill)
            )
        return False
    
    return True
```

---

### Issue 2: Insufficient Validation Before Execution
**Severity:** HIGH

**Missing Checks:**
1. Balance verification (might not have enough funds)
2. Position limits (Polymarket has max position sizes)
3. Market liquidity (order size vs available depth)
4. Time to market close (avoid markets closing in < 10 min)

**Recommendation:**
```python
def validate_opportunity(self, opportunity):
    # Check balances
    kalshi_balance = self.kalshi_client.get_balance()
    poly_balance = self.polymarket_executor.client.get_balance()
    
    required_kalshi = stakes['stake_on_side_a']
    required_poly = stakes['stake_on_side_b']
    
    if kalshi_balance < required_kalshi or poly_balance < required_poly:
        logger.error(f"Insufficient balance: Need K${required_kalshi} P${required_poly}")
        return False
    
    # Check market close time
    close_time = opportunity['kalshi_market']['close_time']
    minutes_to_close = (close_time - datetime.now()).total_seconds() / 60
    
    if minutes_to_close < 10:
        logger.warning(f"Market closes in {minutes_to_close:.1f} min - skipping")
        return False
    
    # Check liquidity
    kalshi_depth = opportunity['kalshi_market']['yes_depth_usd']
    if kalshi_depth < required_kalshi * 2:
        logger.warning(f"Insufficient Kalshi liquidity: ${kalshi_depth} < ${required_kalshi * 2}")
        return False
    
    return True
```

---

### Issue 3: No Order Price Slippage Protection
**Severity:** MEDIUM

**Problem:** 
Aggressive pricing (+15¢ for Kalshi, +1¢ for Polymarket) ensures fill, but might overpay and eliminate edge.

**Example:**
- Expected edge: 5% ($50 profit on $1000 stake)
- Slippage: 3% ($30 loss due to worse prices)
- Net edge: 2% ($20 profit) - but wasn't calculated!

**Recommendation:**
```python
def calculate_slippage_adjusted_edge(self, opportunity, fill_prices):
    """
    Recalculate edge using ACTUAL fill prices (not expected)
    """
    actual_kalshi_price = fill_prices['kalshi']
    actual_poly_price = fill_prices['poly']
    
    actual_cost = actual_kalshi_price + actual_poly_price
    actual_edge = (1.0 - actual_cost) * 100
    
    if actual_edge < MIN_EDGE_PERCENTAGE:
        logger.warning(f"Slippage ate edge: expected {opportunity['edge']:.2f}%, actual {actual_edge:.2f}%")
        # Consider canceling if not filled yet
    
    return actual_edge
```

---

### Issue 4: Database Not Used for Execution Tracking
**Severity:** MEDIUM

**Problem:**
`executed_games` is in-memory only. If bot crashes and restarts:
- Loses track of which games were traded
- Might trade same game twice
- Can't reconstruct positions

**Recommendation:**
```python
# Before execution:
db.mark_game_as_executing(game_id, timestamp=now())

# After execution:
db.mark_game_as_executed(
    game_id=game_id,
    kalshi_order_id=kalshi_result.order_id,
    poly_order_id=poly_result.order_id,
    kalshi_filled=kalshi_result.filled_quantity,
    poly_filled=poly_result.filled_size,
    timestamp=now()
)

# On restart:
self.executed_games = set(db.get_executed_game_ids())
```

---

### Issue 5: No Monitoring of Filled Positions
**Severity:** HIGH

**Problem:**
After execution, bot forgets about the position. No tracking of:
- When markets settle
- What the actual profit/loss was
- Whether positions need closing before market close

**Recommendation:**
Create position monitoring daemon:
```python
class PositionMonitor:
    def check_positions(self):
        """
        Periodically check open positions and:
        1. Alert if market closing soon (< 1 hour)
        2. Calculate P&L based on current prices
        3. Suggest early exit if edge disappeared
        4. Settle positions after market resolves
        """
        positions = db.get_unsettled_positions()
        
        for pos in positions:
            market_close = pos.kalshi_market_close_time
            if datetime.now() > market_close:
                # Market should be settled
                self.settle_position(pos)
            elif (market_close - datetime.now()).seconds < 3600:
                # Closing in < 1 hour
                self.send_alert(f"Position in {pos.game_id} closing soon!")
```

---

### Recommended Architecture Improvements

1. **Add Execution Coordinator Layer**
   ```
   OpportunityDetector → ExecutionCoordinator → [KalshiExecutor, PolymarketExecutor]
   ```
   Coordinator handles: validation, rollback, partial execution recovery

2. **Implement State Machine for Trades**
   ```
   DETECTED → VALIDATED → EXECUTING → PARTIAL/FILLED → SETTLED
   ```
   Each state has specific recovery actions

3. **Add Real-Time Monitoring Dashboard**
   Track:
   - Open positions
   - P&L (mark-to-market)
   - Execution success rate
   - Fill rate vs partial execution rate

4. **Implement Circuit Breaker**
   Auto-pause bot if:
   - 3+ partial executions in a row
   - Total loss exceeds $X
   - API error rate > 20%

---

## Appendix: Key Files Reference

| File | Lines of Code | Primary Purpose |
|------|---------------|-----------------|
| `run_kalshi_polymarket_fixed.py` | 825 | Main production bot |
| `src/data_sources/kalshi_client.py` | 673 | Kalshi API client |
| `src/polymarket_client.py` | 397 | Polymarket API client |
| `src/executors/kalshi_executor.py` | 540 | Kalshi order execution |
| `src/executors/polymarket_executor.py` | 683 | Polymarket order execution |
| `src/cross_market_detector.py` | 485 | Cross-platform matching |
| `src/arbitrage_detector.py` | 368 | Generic arbitrage logic |
| `src/smart_matcher.py` | 321 | Fuzzy event matching |
| `src/database.py` | 288 | SQLAlchemy models |
| `config/settings.py` | 77 | Configuration |

**Total Codebase:** ~4,600 lines (excluding archived files)

---

**Document Status:** Complete  
**Last Updated:** December 29, 2025  
**Maintainer:** Architecture Analysis

