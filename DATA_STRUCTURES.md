# Actual Data Structures in Your Code

**Last Updated:** December 29, 2025  
**Purpose:** Document the EXACT data structures, classes, and dict formats used in your arbitrage bot

---

## 1. Kalshi Market Object (After API Fetch)

### Location: `src/data_sources/kalshi_client.py:486-504`

### Structure: Python `Dict` (NOT a class)

```python
{
    'ticker': str,              # 'KXNFLGAME-25DEC28NOTEN-TEN'
    'title': str,               # 'Tennessee @ New Orleans Winner?'
    'subtitle': str,            # 'Dec 28, 2025'
    'category': str,            # 'Sports'
    'series': str,              # 'KXNFLGAME'
    'yes_team': str,            # 'Tennessee' ← CRITICAL FIELD
    'yes_price': float,         # 0.48 (ask price for YES)
    'no_price': float,          # 0.54 (ask price for NO)
    'yes_bid': float,           # 0.46 (best bid for YES)
    'no_bid': float,            # 0.52 (best bid for NO)
    'yes_ask': float,           # 0.48 (best ask for YES)
    'no_ask': float,            # 0.54 (best ask for NO)
    'spread': float,            # 0.06 (bid-ask spread)
    'yes_depth_usd': float,     # 4700.0 (liquidity in USD)
    'no_depth_usd': float,      # 5200.0
    'close_time': str,          # '2025-12-28T23:00:00Z'
    'volume': int               # 12500
}
```

### Real Example from Your Code:

```python
# From: src/data_sources/kalshi_client.py:486-504
return {
    'ticker': ticker,                              # Line 487
    'title': title,                                # Line 488
    'subtitle': market.get('subtitle', ''),        # Line 489
    'category': market.get('category', 'Sports'),  # Line 490
    'series': market.get('series'),                # Line 491
    'yes_team': yes_team,  # ← From yes_sub_title  # Line 492
    'yes_price': yes_ask,                          # Line 493
    'no_price': no_ask,                            # Line 494
    'yes_bid': orderbook.best_yes_bid,             # Line 495
    'no_bid': orderbook.best_no_bid,               # Line 496
    'yes_ask': yes_ask,                            # Line 497
    'no_ask': no_ask,                              # Line 498
    'spread': orderbook.yes_spread,                # Line 499
    'yes_depth_usd': orderbook.yes_bid_depth_usd,  # Line 500
    'no_depth_usd': orderbook.no_bid_depth_usd,    # Line 501
    'close_time': market.get('close_time'),        # Line 502
    'volume': market.get('volume', 0),             # Line 503
}
```

### How It's Created:

1. **Fetch raw market data** from Kalshi API (`GET /markets`)
2. **Fetch orderbook** for each market (`GET /markets/{ticker}/orderbook`)
3. **Parse orderbook** into `OrderBookData` dataclass (Lines 38-422)
4. **Extract prices** from orderbook:
   - `yes_ask` = derived from orderbook (Line 478)
   - `no_ask` = derived from orderbook (Line 479)
   - `yes_team` = extracted from `yes_sub_title` field (Line 484)
5. **Return dict** with all fields (Lines 486-504)

### Raw Kalshi API Response Format:

**From API (not your code):**
```json
{
  "markets": [
    {
      "ticker": "KXNFLGAME-25DEC28NOTEN-TEN",
      "title": "Tennessee @ New Orleans Winner?",
      "yes_sub_title": "Tennessee",
      "subtitle": "December 28, 2025",
      "category": "Sports",
      "series": "KXNFLGAME",
      "status": "open",
      "close_time": "2025-12-28T23:00:00Z",
      "volume": 12500
    }
  ]
}
```

**Orderbook API Response:**
```json
{
  "orderbook": {
    "yes": [[47, 120], [46, 200]],  // [price_cents, quantity]
    "no": [[54, 100], [55, 180]]
  }
}
```

---

## 2. Polymarket Market Object (After API Fetch)

### Location: `run_kalshi_polymarket_fixed.py:372-382`

### Structure: Python `Dict` (NOT a class)

```python
{
    'question': str,           # 'Tennessee Titans vs. New Orleans Saints'
    'condition_id': str,       # '0x1234567890abcdef...'
    'clob_token_ids': List[str],  # ['123456789', '987654321']
    'event_slug': str,         # 'tennessee-titans-new-orleans-saints-2025-12-28'
    'sport': str,              # 'nfl'
    'outcomes': [              # List with exactly 2 items
        {
            'outcome_name': str,  # 'Tennessee Titans'
            'price': float,       # 0.46
            'token_id': str       # '123456789'
        },
        {
            'outcome_name': str,  # 'New Orleans Saints'
            'price': float,       # 0.55
            'token_id': str       # '987654321'
        }
    ]
}
```

### Real Example from Your Code:

```python
# From: run_kalshi_polymarket_fixed.py:372-382
all_markets.append({
    'question': question,                           # Line 373
    'condition_id': market.get('conditionId'),      # Line 374
    'clob_token_ids': clob_token_ids,               # Line 375
    'event_slug': slug,                             # Line 376
    'sport': sport_name,                            # Line 377
    'outcomes': [
        {
            'outcome_name': outcomes[0],            # Line 379
            'price': float(outcome_prices[0]),      # Line 379
            'token_id': clob_token_ids[0] if len(clob_token_ids) > 0 else None
        },
        {
            'outcome_name': outcomes[1],            # Line 380
            'price': float(outcome_prices[1]),      # Line 380
            'token_id': clob_token_ids[1] if len(clob_token_ids) > 1 else None
        }
    ]
})
```

### How It's Created:

1. **Fetch events** from Polymarket API (`GET /events?tag_id=450`) (Line 323)
2. **Filter for game events** with date pattern in slug (Line 334)
3. **Fetch event details** for each event (`GET /events/slug/{slug}`) (Line 344)
4. **Parse markets** from event (Line 350)
5. **Parse JSON strings**:
   - `outcomes` from string to list (Line 356)
   - `outcomePrices` from string to list (Line 359)
   - `clobTokenIds` from string to list (Line 365)
6. **Build dict** with parsed data (Lines 372-382)

### Raw Polymarket API Response Format:

**From API (not your code):**
```json
{
  "slug": "tennessee-titans-new-orleans-saints-2025-12-28",
  "title": "Tennessee Titans vs. New Orleans Saints",
  "markets": [
    {
      "conditionId": "0x1234567890abcdef",
      "question": "Tennessee Titans vs. New Orleans Saints",
      "outcomes": "[\"Tennessee Titans\", \"New Orleans Saints\"]",
      "outcomePrices": "[\"0.46\", \"0.55\"]",
      "clobTokenIds": "[\"123456789\", \"987654321\"]"
    }
  ]
}
```

**Note:** Polymarket returns JSON strings (not arrays) for `outcomes`, `outcomePrices`, and `clobTokenIds`. Your code parses these with `json.loads()`.

---

## 3. Matched Event Object

### Location: `run_kalshi_polymarket_fixed.py:449-454`

### Structure: Python `Dict` (NOT a class)

```python
{
    'kalshi': Dict,        # Full Kalshi market object (from section 1)
    'polymarket': Dict,    # Full Polymarket market object (from section 2)
    'sport': Sport,        # Enum: Sport.NFL, Sport.NBA, or Sport.NHL
    'game_id': str         # Base game ticker: 'KXNFLGAME-25DEC28NOTEN'
}
```

### Real Example from Your Code:

```python
# From: run_kalshi_polymarket_fixed.py:449-454
matched.append({
    'kalshi': kalshi,                                   # Line 450
    'polymarket': poly,                                 # Line 451
    'sport': sport,                                     # Line 452
    'game_id': self._get_base_game_ticker(kalshi_ticker)  # Line 453
})
```

### Full Structure Expanded:

```python
{
    'kalshi': {
        'ticker': 'KXNFLGAME-25DEC28NOTEN-TEN',
        'title': 'Tennessee @ New Orleans Winner?',
        'yes_team': 'Tennessee',
        'yes_price': 0.48,
        'no_price': 0.54,
        'spread': 0.06,
        # ... (all other Kalshi fields)
    },
    'polymarket': {
        'question': 'Tennessee Titans vs. New Orleans Saints',
        'condition_id': '0x1234...',
        'sport': 'nfl',
        'outcomes': [
            {'outcome_name': 'Tennessee Titans', 'price': 0.46, 'token_id': '123456'},
            {'outcome_name': 'New Orleans Saints', 'price': 0.55, 'token_id': '987654'}
        ],
        # ... (all other Polymarket fields)
    },
    'sport': Sport.NFL,  # Enum value
    'game_id': 'KXNFLGAME-25DEC28NOTEN'  # Deduplicated base ticker
}
```

### How It's Created:

1. **Deduplication** of Kalshi markets (Lines 397-406)
2. **Iteration** through unique Kalshi markets (Line 411)
3. **Sport filtering** (Lines 430-433)
4. **Team matching** using aliases (Lines 444-447)
5. **Append to matched list** if both teams found (Lines 449-454)

---

## 4. Arbitrage Opportunity Object

### Location: `run_kalshi_polymarket_fixed.py:549-575`

### Structure: Python `Dict` (NOT a class)

**Note:** There IS an `ArbitrageOpportunity` class in `src/arbitrage_detector.py:14-48`, but it's NOT used in your production bot (`run_kalshi_polymarket_fixed.py`). Your production bot uses plain dicts.

```python
{
    'edge': float,                  # 7.2 (percentage)
    'kalshi_market': Dict,          # Full Kalshi market object
    'poly_market': Dict,            # Full Polymarket market object
    'sport': Sport,                 # Enum: Sport.NFL, Sport.NBA, Sport.NHL
    'kalshi_side': str,             # 'yes' or 'no'
    'kalshi_team': str,             # 'Tennessee' (team name)
    'kalshi_price': float,          # 0.48 (price to bet)
    'poly_outcome_index': int,      # 0 or 1 (which outcome to bet on)
    'poly_team': str,               # 'New Orleans Saints' (team name)
    'poly_price': float,            # 0.55 (price to bet)
    'spread': float,                # 0.06 (Kalshi spread)
    'game_id': str                  # 'KXNFLGAME-25DEC28NOTEN' (added later)
}
```

### Real Example from Your Code:

**Strategy 1 (Kalshi YES):**
```python
# From: run_kalshi_polymarket_fixed.py:549-561
return {
    'edge': edge_1,                               # Line 550
    'kalshi_market': kalshi,                      # Line 551
    'poly_market': poly,                          # Line 552
    'sport': sport,                               # Line 553
    'kalshi_side': 'yes',                         # Line 554
    'kalshi_team': kalshi_yes_team_name,          # Line 555
    'kalshi_price': kalshi_yes,                   # Line 556
    'poly_outcome_index': yes_opposite_poly_idx,  # Line 557
    'poly_team': poly_team_for_yes,               # Line 558
    'poly_price': poly_price_for_yes,             # Line 559
    'spread': kalshi_spread,                      # Line 560
}
```

**Strategy 2 (Kalshi NO):**
```python
# From: run_kalshi_polymarket_fixed.py:563-575
return {
    'edge': edge_2,                               # Line 564
    'kalshi_market': kalshi,                      # Line 565
    'poly_market': poly,                          # Line 566
    'sport': sport,                               # Line 567
    'kalshi_side': 'no',                          # Line 568
    'kalshi_team': kalshi_no_team_name,           # Line 569
    'kalshi_price': kalshi_no,                    # Line 570
    'poly_outcome_index': no_opposite_poly_idx,   # Line 571
    'poly_team': poly_team_for_no,                # Line 572
    'poly_price': poly_price_for_no,              # Line 573
    'spread': kalshi_spread,                      # Line 574
}
```

### Full Structure Expanded:

```python
{
    'edge': 7.2,
    'kalshi_market': {
        'ticker': 'KXNFLGAME-25DEC28NOTEN-TEN',
        'title': 'Tennessee @ New Orleans Winner?',
        'yes_team': 'Tennessee',
        'yes_price': 0.48,
        'no_price': 0.54,
        'spread': 0.06,
        # ... all Kalshi fields
    },
    'poly_market': {
        'question': 'Tennessee Titans vs. New Orleans Saints',
        'condition_id': '0x1234...',
        'outcomes': [
            {'outcome_name': 'Tennessee Titans', 'price': 0.46, 'token_id': '123456'},
            {'outcome_name': 'New Orleans Saints', 'price': 0.55, 'token_id': '987654'}
        ],
        # ... all Polymarket fields
    },
    'sport': Sport.NFL,
    'kalshi_side': 'no',              # Betting NO (against Tennessee)
    'kalshi_team': 'New Orleans',     # What NO represents
    'kalshi_price': 0.54,             # Price for NO
    'poly_outcome_index': 0,          # Index in outcomes list (Tennessee)
    'poly_team': 'Tennessee Titans',  # Opposite team on Polymarket
    'poly_price': 0.46,               # Price for Tennessee on Poly
    'spread': 0.06,
    'game_id': 'KXNFLGAME-25DEC28NOTEN'  # Added at line 743
}
```

### How It's Created:

1. **Extract prices** from matched event (Lines 468-470)
2. **Map teams** using `yes_team` field (Lines 470-530)
3. **Calculate two strategies** (Lines 534-539)
4. **Filter by spread** (Lines 543-546)
5. **Return best strategy** if edge >= threshold (Lines 548-575)

---

## 5. Price Fields Used in Arbitrage Calculation

### Location: `run_kalshi_polymarket_fixed.py:468-482`

### Exact Variable Names:

```python
# From Kalshi market dict:
kalshi_yes = kalshi.get('yes_price', 0)      # Line 468 - ASK price for YES
kalshi_no = kalshi.get('no_price', 0)        # Line 469 - ASK price for NO
kalshi_spread = kalshi.get('spread', 0.10)   # Line 473 - Bid-ask spread

# From Polymarket market dict:
poly_price_0 = float(poly_outcomes[0].get('price', 0))  # Line 481 - Team 0 price
poly_price_1 = float(poly_outcomes[1].get('price', 0))  # Line 482 - Team 1 price
```

### What These Actually Are:

| Variable | Source | Actual Meaning |
|----------|--------|----------------|
| `kalshi_yes` | `kalshi['yes_price']` | **Best ASK price** for YES (derived from orderbook) |
| `kalshi_no` | `kalshi['no_price']` | **Best ASK price** for NO (derived from orderbook) |
| `kalshi_spread` | `kalshi['spread']` | **Bid-ask spread** for YES (in decimal, e.g., 0.06 = 6¢) |
| `poly_price_0` | `poly['outcomes'][0]['price']` | **Current price** for outcome 0 (from API) |
| `poly_price_1` | `poly['outcomes'][1]['price']` | **Current price** for outcome 1 (from API) |

### Arbitrage Calculation Formula:

```python
# From: run_kalshi_polymarket_fixed.py:534-539

# Strategy 1: Buy Kalshi YES + Buy Poly opposite team
total_cost_1 = kalshi_yes + poly_price_for_yes     # Line 534
edge_1 = (1.0 - total_cost_1) * 100                # Line 535

# Strategy 2: Buy Kalshi NO + Buy Poly opposite team
total_cost_2 = kalshi_no + poly_price_for_no       # Line 538
edge_2 = (1.0 - total_cost_2) * 100                # Line 539
```

### Why ASK Prices (Not BID)?

**You're BUYING both positions**, so you pay the ASK price (the price sellers want).

- Kalshi: `yes_price` and `no_price` are ASK prices (Lines 493-494)
- Polymarket: `price` field is the mid-market or current offer price

### How Kalshi ASK Prices Are Derived:

From `src/data_sources/kalshi_client.py:376-414`:

```python
# YES ask is derived from NO bids (binary complement)
if no_bids:
    for bid in no_bids[:3]:
        ask_price = max(1.0 - bid.price + 0.01, 0.01)  # Line 393
        ask_price = min(ask_price, 0.99)               # Line 394
        yes_asks.append(OrderBookLevel(price=ask_price, quantity=bid.quantity))

# Then:
yes_ask = orderbook.best_yes_ask  # Line 478
no_ask = orderbook.best_no_ask    # Line 479
```

**Key Insight:** Kalshi's YES ask price is calculated as `1 - NO_bid + small_spread` because in a binary market, YES + NO ≈ 1.00.

---

## 6. ArbitrageOpportunity Class (Unused in Production)

### Location: `src/arbitrage_detector.py:14-48`

### Structure: Python Class (NOT used in production bot)

```python
class ArbitrageOpportunity:
    """Represents a detected arbitrage opportunity"""
    
    def __init__(
        self,
        event_id: str,
        event_description: str,
        side_a: Dict,           # {platform, team, odds_decimal, price}
        side_b: Dict,           # {platform, team, odds_decimal, price}
        edge_percentage: float,
        total_probability: float,
        timestamp: datetime = None
    ):
        self.event_id = event_id
        self.event_description = event_description
        self.side_a = side_a
        self.side_b = side_b
        self.edge_percentage = edge_percentage
        self.total_probability = total_probability
        self.timestamp = timestamp or datetime.utcnow()
```

**Note:** This class is defined in `arbitrage_detector.py` but **NOT used** in your production bot (`run_kalshi_polymarket_fixed.py`). Your production bot uses plain dicts instead (section 4 above).

---

## 7. OrderBookData Class (Used Internally)

### Location: `src/data_sources/kalshi_client.py:38-156`

### Structure: Python `@dataclass`

```python
@dataclass
class OrderBookData:
    """Parsed order book with depth analysis"""
    ticker: str
    yes_bids: List[OrderBookLevel]
    yes_asks: List[OrderBookLevel]
    no_bids: List[OrderBookLevel]
    no_asks: List[OrderBookLevel]
    
    @property
    def best_yes_bid(self) -> Optional[float]:
        return self.yes_bids[0].price if self.yes_bids else None
    
    @property
    def best_yes_ask(self) -> Optional[float]:
        if self.yes_asks:
            return self.yes_asks[0].price
        elif self.yes_bids:
            return min(self.yes_bids[0].price + 0.02, 0.99)
        return None
    
    @property
    def yes_spread(self) -> float:
        """Calculate YES bid-ask spread"""
        if self.best_yes_bid and self.best_yes_ask:
            return self.best_yes_ask - self.best_yes_bid
        return 0.02  # Default 2¢ spread
    
    # ... more properties
```

**Purpose:** Internal representation of orderbook data. Used to calculate prices in section 1, then discarded. Not stored in final market dict.

---

## 8. OrderResult Classes (Execution)

### Kalshi OrderResult: `src/executors/kalshi_executor.py:36-62`

```python
@dataclass
class OrderResult:
    """Structured order result"""
    success: bool           # True if order filled successfully
    order_id: Optional[str]
    status: OrderStatus     # Enum: PENDING, RESTING, FILLED, CANCELLED
    filled_quantity: int    # Number of contracts filled
    filled_price: float     # Price filled at
    remaining_quantity: int # Unfilled contracts
    error: Optional[str]
    error_type: Optional[str]
    timestamp: float
    raw_response: Optional[Dict]
    placed: bool = True     # True if order was submitted to exchange
```

### Polymarket OrderResult: `src/executors/polymarket_executor.py:39-63`

```python
@dataclass
class OrderResult:
    """Structured order result"""
    success: bool
    order_id: Optional[str]
    status: OrderStatus     # Enum: PENDING, LIVE, FILLED, CANCELLED
    filled_size: float      # Amount filled in USDC
    filled_price: float     # Price filled at
    remaining_size: float   # Unfilled amount
    error: Optional[str]
    error_type: Optional[str]
    timestamp: float
    raw_response: Optional[Dict]
```

---

## Summary Table

| Object | File | Lines | Type | Used In Production? |
|--------|------|-------|------|---------------------|
| Kalshi Market Dict | `src/data_sources/kalshi_client.py` | 486-504 | Dict | ✅ YES |
| Polymarket Market Dict | `run_kalshi_polymarket_fixed.py` | 372-382 | Dict | ✅ YES |
| Matched Event Dict | `run_kalshi_polymarket_fixed.py` | 449-454 | Dict | ✅ YES |
| Arbitrage Opportunity Dict | `run_kalshi_polymarket_fixed.py` | 549-575 | Dict | ✅ YES |
| ArbitrageOpportunity Class | `src/arbitrage_detector.py` | 14-48 | Class | ❌ NO (unused) |
| OrderBookData | `src/data_sources/kalshi_client.py` | 38-156 | @dataclass | ✅ YES (internal) |
| OrderResult (Kalshi) | `src/executors/kalshi_executor.py` | 36-62 | @dataclass | ✅ YES |
| OrderResult (Polymarket) | `src/executors/polymarket_executor.py` | 39-63 | @dataclass | ✅ YES |

---

## Key Takeaways

1. **Your production bot uses plain `Dict` objects** for markets and opportunities, NOT custom classes
2. **Price fields used for arbitrage:**
   - Kalshi: `yes_price` and `no_price` (both are **ASK prices**)
   - Polymarket: `outcomes[i]['price']` (current market price)
3. **Critical fields:**
   - `yes_team` in Kalshi dict - tells you which team YES refers to
   - `token_id` in Polymarket outcomes - required for trading
   - `game_id` - used to prevent duplicate trades
4. **The ArbitrageOpportunity class exists but is unused** - your bot uses dicts instead
5. **OrderResult dataclasses** are the only structured classes used in production (for execution tracking)

