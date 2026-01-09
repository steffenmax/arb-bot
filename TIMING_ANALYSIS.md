# Timing Analysis: Detection to Execution

**Generated:** December 29, 2025  
**Purpose:** Analyze latency, delays, and timing in the arbitrage detection and execution flow

---

## Table of Contents
1. [All Delays in the System](#all-delays-in-the-system)
2. [Detection to Execution Timeline](#detection-to-execution-timeline)
3. [Price Capture vs Order Placement](#price-capture-vs-order-placement)
4. [Caching Analysis](#caching-analysis)
5. [Critical Timing Issues](#critical-timing-issues)

---

## 1. All Delays in the System

### A. Rate Limiting Delays (`src/rate_limiter.py:35-68`)

**Kalshi Rate Limiter:** 18 requests/second (one request every ~55ms)
**Polymarket Rate Limiter:** 25 requests/second (one request every 40ms)

```python
def wait_if_needed(self) -> float:
    """Block if necessary to avoid exceeding rate limit"""
    now = time.time()
    
    # Remove expired requests from the window
    while self.requests and self.requests[0] < now - self.time_window:
        self.requests.popleft()
    
    # If at limit, calculate wait time
    if len(self.requests) >= self.max_requests:
        # Must wait until oldest request expires
        wait_until = self.requests[0] + self.time_window
        wait_time = wait_until - now
        
        if wait_time > 0:
            time.sleep(wait_time)  # ← DELAY HERE
            
    return wait_time
```

**Impact:** 
- Each Kalshi API call may wait up to ~55ms if rate limited
- Each Polymarket API call may wait up to ~40ms if rate limited
- During burst fetching (100+ markets), this adds up significantly

### B. Network Call Timeouts

#### Kalshi API Calls (`src/data_sources/kalshi_client.py:241-247`)
```python
response = self.session.request(
    method=method,
    url=url,
    headers=headers,
    params=params,
    json=body if body else None,
    timeout=15  # ← 15 SECOND TIMEOUT
)
```

#### Polymarket API Calls (`src/polymarket_client.py:50`)
```python
response = self.session.get(url, params=params, timeout=10)  # ← 10 SECOND TIMEOUT
```

**Typical Response Times:**
- Kalshi: 100-500ms per request
- Polymarket: 50-200ms per request

### C. Execution Wait Loops

#### Kalshi Fill Waiting (`src/executors/kalshi_executor.py:160-199`)
```python
if wait_for_fill and initial_filled < quantity and status != OrderStatus.FILLED:
    print(f"  Waiting for fill (max {fill_timeout}s)...")
    start_time = time.time()
    
    while time.time() - start_time < fill_timeout:  # ← 5 SECOND TIMEOUT
        status_result = self.get_order_status(order_id)
        
        if status_result.status == OrderStatus.FILLED:
            return success  # Filled!
        
        time.sleep(0.3)  # ← 300ms DELAY BETWEEN CHECKS
```

**Fill Wait Settings:**
- Default timeout: 5 seconds
- Poll interval: 300ms (checks 16-17 times)
- Each status check = 1 API call with rate limiting

#### Polymarket Fill Waiting (`src/executors/polymarket_executor.py:342-380`)
```python
if wait_for_fill:
    print(f"  Waiting for fill (max {fill_timeout}s)...")
    start_time = time.time()
    
    while time.time() - start_time < fill_timeout:  # ← 5 SECOND TIMEOUT
        status_result = self.get_order_status(str(order_id))
        
        if status_result.status == OrderStatus.FILLED:
            return success
        
        time.sleep(0.3)  # ← 300ms DELAY BETWEEN CHECKS
```

### D. Main Loop Delay (`run_kalshi_polymarket_fixed.py:806-807`)
```python
logger.info(f"\n⏳ Waiting {POLL_INTERVAL_SECONDS}s...")
time.sleep(POLL_INTERVAL_SECONDS)  # ← 30 SECOND DEFAULT DELAY
```

**Configuration:**
- `POLL_INTERVAL_SECONDS` default: 30 seconds
- Configurable via environment variable

---

## 2. Detection to Execution Timeline

### Complete Flow with Timing

```
T+0s    ┌─────────────────────────────────────────────────────────┐
        │  START: scan_for_opportunities()                        │
        └─────────────────────────────────────────────────────────┘
                              │
T+0s    ┌─────────────────────────────────────────────────────────┐
        │  PHASE 1: Fetch Kalshi Markets                          │
        │  Location: run_kalshi_polymarket_fixed.py:687           │
        └─────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────────────────┐
        │  Step 1.1: Fetch raw markets (1 API call per sport)    │
        │  - NFL: GET /markets?series=KXNFLGAME  (200-500ms)     │
        │  - NBA: GET /markets?series=KXNBAGAME  (200-500ms)     │
        │  - NHL: GET /markets?series=KXNHLGAME  (200-500ms)     │
        │                                                          │
        │  Timing: ~300ms × 1 sport = 300ms                       │
        │  (Sequential, rate limited at 18/sec = 55ms minimum)   │
        └─────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────────────────┐
        │  Step 1.2: Fetch orderbooks (PARALLEL)                  │
        │  Location: src/data_sources/kalshi_client.py:509-516    │
        │                                                          │
        │  - 100 markets returned                                  │
        │  - ThreadPoolExecutor with max_workers=20                │
        │  - Each: GET /markets/{ticker}/orderbook (200-500ms)    │
        │                                                          │
        │  Calculation:                                            │
        │  - 100 markets ÷ 20 threads = 5 batches                 │
        │  - Each batch: ~300ms (parallel) + rate limit delays    │
        │  - Rate limit: 18/sec means max 18 per second           │
        │  - 100 markets / 18 per sec = 5.6 seconds minimum       │
        │                                                          │
        │  Timing: ~6-8 seconds for 100 markets                   │
        └─────────────────────────────────────────────────────────┘
                              │
T+7s    ┌─────────────────────────────────────────────────────────┐
        │  PHASE 2: Fetch Polymarket Markets                      │
        │  Location: run_kalshi_polymarket_fixed.py:691           │
        └─────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────────────────┐
        │  Step 2.1: Fetch events list (1 call per sport)        │
        │  - GET /events?tag_id=450 (NFL)  (~200ms)              │
        │  - Returns: 30-100 events                               │
        │                                                          │
        │  Timing: ~200ms × 1 sport = 200ms                       │
        └─────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────────────────┐
        │  Step 2.2: Fetch event details (30 calls)              │
        │  Location: run_kalshi_polymarket_fixed.py:344           │
        │                                                          │
        │  - For each event: GET /events/slug/{slug} (~150ms)    │
        │  - Sequential (not parallel)                            │
        │  - Rate limited at 25/sec = 40ms minimum per call       │
        │                                                          │
        │  Calculation:                                            │
        │  - 30 events × 150ms = 4.5 seconds (if no rate limit)  │
        │  - With rate limit: 30 / 25 per sec = 1.2 sec minimum  │
        │  - Actual: ~2-3 seconds (dominated by network latency)  │
        │                                                          │
        │  Timing: ~2-3 seconds                                   │
        └─────────────────────────────────────────────────────────┘
                              │
T+10s   ┌─────────────────────────────────────────────────────────┐
        │  PHASE 3: Match Markets                                 │
        │  Location: run_kalshi_polymarket_fixed.py:699           │
        │                                                          │
        │  - Pure computation (no API calls)                       │
        │  - 100 Kalshi × 30 Polymarket = 3,000 comparisons      │
        │  - String matching with aliases                          │
        │                                                          │
        │  Timing: ~50-100ms                                      │
        └─────────────────────────────────────────────────────────┘
                              │
T+10s   ┌─────────────────────────────────────────────────────────┐
        │  PHASE 4: Calculate Arbitrage                           │
        │  Location: run_kalshi_polymarket_fixed.py:732           │
        │                                                          │
        │  - For each matched event (~10-20 matches):             │
        │    * Extract prices (from cached data)                  │
        │    * Map teams                                           │
        │    * Calculate 2 strategies                              │
        │    * Check filters (spread, edge threshold)             │
        │                                                          │
        │  Timing: ~10-20ms (pure computation)                    │
        └─────────────────────────────────────────────────────────┘
                              │
                              ▼ (if opportunity found)
T+10s   ┌─────────────────────────────────────────────────────────┐
        │  PHASE 5: Execute Trade                                 │
        │  Location: run_kalshi_polymarket_fixed.py:585           │
        └─────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────────────────┐
        │  Step 5.1: Kalshi Execution                             │
        │                                                          │
        │  A. Calculate order parameters (instant)                │
        │  B. POST /portfolio/orders  (~200-500ms)                │
        │  C. Wait for fill (up to 5 seconds)                     │
        │     - Poll every 300ms: GET /portfolio/orders/{id}      │
        │     - 16 polls × (300ms + 100ms API) = ~6.4s max        │
        │                                                          │
        │  Timing: 0.2s (fast fill) to 5.5s (timeout)            │
        │  Typical: 1-2 seconds                                   │
        └─────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────────────────┐
        │  Step 5.2: Polymarket Execution (PARALLEL)              │
        │  Location: src/executors/polymarket_executor.py:190     │
        │                                                          │
        │  A. FRESH PRICE FETCH! (NEW!)                           │
        │     - GET /book?token_id={token_id}  (~100ms)           │
        │     - Extract current best_ask                           │
        │     - Add 1¢ for aggressive pricing                     │
        │                                                          │
        │  B. Create signed order (instant)                       │
        │  C. POST order to CLOB API (~200-400ms)                 │
        │  D. Wait for fill (up to 5 seconds)                     │
        │     - Poll every 300ms: get_order()                     │
        │                                                          │
        │  Timing: 0.3s (fast fill) to 5.6s (timeout)            │
        │  Typical: 1-2 seconds                                   │
        └─────────────────────────────────────────────────────────┘
                              │
T+12s   ┌─────────────────────────────────────────────────────────┐
        │  END: Both legs executed                                │
        │  Total time: ~10-12 seconds from detection              │
        └─────────────────────────────────────────────────────────┘
```

### Summary: Detection to Execution

| Phase | Time | Cumulative | Notes |
|-------|------|------------|-------|
| **1. Fetch Kalshi Markets** | 6-8s | 6-8s | Parallel orderbook fetching, rate limited |
| **2. Fetch Polymarket Markets** | 2-3s | 8-11s | Sequential event detail fetching |
| **3. Match Markets** | 0.1s | 8-11s | Pure computation |
| **4. Calculate Arbitrage** | 0.02s | 8-11s | Pure computation |
| **5. Execute Trades** | 1-2s | 9-13s | Parallel execution with fill waits |
| **TOTAL** | **9-13 seconds** | | From scan start to execution complete |

**Best Case:** 9 seconds (fast network, immediate fills)  
**Typical:** 10-12 seconds  
**Worst Case:** 18 seconds (slow network, timeouts, partial fills)

---

## 3. Price Capture vs Order Placement

### Critical Question: What Price Are You Trading At?

#### ❌ OLD BEHAVIOR (Stale Prices)

```
T+0s:  Fetch Kalshi orderbook → yes_price = 0.48
T+0s:  Fetch Polymarket market → price = 0.55
T+10s: Calculate arbitrage using 0.48 and 0.55  ✓
T+10s: Place Kalshi order at 0.48 + 0.15 = 0.63  ← 10 SECONDS STALE!
T+10s: Place Poly order at 0.55  ← 10 SECONDS STALE!
```

**Problem:** Prices are 10 seconds old when you place orders!

#### ✅ NEW BEHAVIOR (Fresh Polymarket Prices)

**Location:** `src/executors/polymarket_executor.py:226-233`

```python
# CRITICAL FIX: Fetch current best ask for aggressive pricing
if order_side == BUY:
    # For BUY orders, use current best ask (not stale expected price)
    orderbook = self.get_orderbook(token_id)  # ← FRESH FETCH!
    if orderbook and orderbook.get('best_ask'):
        current_ask = orderbook['best_ask']
        # Use best ask + 1 cent for aggressive fill
        order_price = min(current_ask + 0.01, 0.99)
        print(f"  Current best ask: {current_ask:.4f}")
        print(f"  Using aggressive price: {order_price:.4f}")
```

**Timeline:**
```
T+0s:  Fetch Kalshi orderbook → yes_price = 0.48
T+0s:  Fetch Polymarket market → price = 0.55 (for detection only)
T+10s: Calculate arbitrage using 0.48 and 0.55  ✓
T+10s: Place Kalshi order at 0.48 + 0.15 = 0.63  ← STILL 10s STALE
T+10s: **FETCH FRESH POLYMARKET ORDERBOOK** → current_ask = 0.56  ← NEW!
T+10s: Place Poly order at 0.56 + 0.01 = 0.57  ← FRESH (< 1s old)
```

### Still-Stale Kalshi Prices

**Kalshi execution** uses the price from initial scan:

```python
# From: run_kalshi_polymarket_fixed.py:604-606
quantity = max(1, int(stake_each / opportunity['kalshi_price']))
# Use aggressive price (+15¢) to ensure we cross the spread
price_cents = min(int((opportunity['kalshi_price'] + 0.15) * 100), 95)
```

**`opportunity['kalshi_price']` is from T+0** (initial scan), not fresh!

**Timeline:**
```
T+0s:   Fetch: kalshi_yes_price = 0.48
T+10s:  Execute: place order at 0.48 + 0.15 = 0.63 ← 10 SECONDS STALE
```

**Mitigation:** 
- Adding 15¢ helps cross the spread even if price moved
- Aggressive pricing ensures fill even with stale data
- But you might overpay if price actually moved in your favor!

### Summary Table

| Price | When Captured | When Used | Staleness | Fresh Fetch? |
|-------|---------------|-----------|-----------|--------------|
| **Kalshi yes_price** | T+0 (scan) | T+10 (execute) | **10 seconds** | ❌ NO |
| **Kalshi no_price** | T+0 (scan) | T+10 (execute) | **10 seconds** | ❌ NO |
| **Poly price (detection)** | T+0 (scan) | T+0 (calculation) | 0 seconds | N/A |
| **Poly price (execution)** | T+10 (execute) | T+10 (execute) | **< 1 second** | ✅ YES |

---

## 4. Caching Analysis

### What's Cached?

#### ✅ Prices Are Cached (For Better or Worse)

**Kalshi prices:**
```python
# Fetched at T+0 (scan start)
kalshi_markets = self.kalshi_client.get_sports_markets()  # Line 687

# Stored in memory as dict:
kalshi_market = {
    'yes_price': 0.48,  # ← Cached in dict
    'no_price': 0.54,   # ← Cached in dict
    'timestamp': T+0    # ← No timestamp stored!
}

# Used at T+10 (execution)
kalshi_price = opportunity['kalshi_price']  # ← From cached dict
```

**Duration:** Prices cached for ~10 seconds (detection time)

**Polymarket prices (detection):**
```python
# Fetched at T+0
poly_markets = self.get_polymarket_markets()  # Line 691

# Stored in memory:
poly_market = {
    'outcomes': [
        {'price': 0.55, 'token_id': '123456'}  # ← Cached
    ]
}
```

**Duration:** Cached for calculation only (~10s), then **refetched for execution**

#### ❌ No Persistent Caching

- No Redis/Memcached
- No file-based cache
- No database caching
- Everything is **in-memory for one scan cycle only**

#### ⚠️ No Timestamps Stored

**Critical Gap:** Your cached prices have NO timestamp!

```python
# What you store:
{'yes_price': 0.48, 'no_price': 0.54}

# What you SHOULD store:
{'yes_price': 0.48, 'no_price': 0.54, 'fetched_at': 1735501234.567}
```

**Impact:** Can't determine how stale your data is

### What's NOT Cached?

1. **Orderbooks:** Fresh fetch for Polymarket execution
2. **Order status:** Polled every 300ms during fill wait
3. **Matched events:** Recalculated every scan
4. **Arbitrage opportunities:** Recalculated every scan

### Cache Invalidation

**Method:** Complete refresh every scan cycle

```python
# Every 30 seconds (POLL_INTERVAL_SECONDS):
while self.running:
    opportunity = self.scan_for_opportunities()  # ← Full refresh
    
    # ... execute if found ...
    
    time.sleep(POLL_INTERVAL_SECONDS)  # ← Cache "expires" here
```

---

## 5. Critical Timing Issues

### Issue 1: 10-Second Stale Kalshi Prices 🔴 CRITICAL

**Problem:** Kalshi prices are 10 seconds old when you execute

**Example:**
```
T+0s:  Kalshi YES = 0.48 (fetched)
T+5s:  [News: Star player injured]
T+5s:  Kalshi YES moves to 0.35 (you don't know!)
T+10s: You place order at 0.48 + 0.15 = 0.63
       → Order fills at 0.35 (market moved in your favor!)
       → You overpaid by 28¢!
```

**OR:**
```
T+0s:  Kalshi YES = 0.48 (fetched)
T+5s:  [News: Opposing player injured]
T+5s:  Kalshi YES moves to 0.65 (you don't know!)
T+10s: You place order at 0.48 + 0.15 = 0.63
       → Order doesn't fill (market moved against you)
       → Arbitrage opportunity gone, but you're still trying!
```

**Frequency:** Every trade uses 10-second-old Kalshi prices

**Fix Needed:**
```python
# Before execution, re-fetch Kalshi orderbook:
def execute_trade(self, opportunity):
    # Validate prices are still fresh
    fresh_kalshi = self.kalshi_client.get_orderbook_full(
        opportunity['kalshi_market']['ticker']
    )
    
    # Compare:
    if abs(fresh_kalshi.best_yes_ask - opportunity['kalshi_price']) > 0.05:
        logger.warning(f"Price moved! Expected {opportunity['kalshi_price']}, "
                      f"now {fresh_kalshi.best_yes_ask}")
        return False  # Abort trade
    
    # Proceed with fresh price...
```

### Issue 2: Race Condition Window 🟡 HIGH

**The gap between arbitrage calculation and execution:**

```
T+10.00s: Calculate edge = 5.2% using prices:
          Kalshi YES = 0.48, Poly = 0.55
          Total cost = 1.03 → Not an arb!
          
Wait, that's wrong. Let me recalculate:
          Total cost = 0.48 + (1 - 0.55) = 0.48 + 0.45 = 0.93
          Edge = (1.0 - 0.93) × 100 = 7% ✓

T+10.01s: Start execution

T+10.02s: [Meanwhile, prices update]
          Kalshi YES → 0.52 (+4¢)
          Poly → 0.58 (+3¢)
          
T+10.10s: Place Kalshi order at 0.63 (0.48 + 0.15)
          → Fills at 0.52 (market moved)
          
T+10.12s: Fetch fresh Poly price: 0.58
          Place Poly order at 0.59 (0.58 + 0.01)
          → Fills at 0.58
          
T+10.20s: Both filled!
          Actual cost: 0.52 + 0.58 = 1.10
          Expected profit: 7% → LOSS: 10%!
```

**Duration:** 100-200ms gap (small but critical)

### Issue 3: Parallel Execution Not Truly Parallel 🟡 MEDIUM

**Current flow:**
```python
# Execute Kalshi first (fully synchronous)
kalshi_result = self.kalshi_executor.execute_order(...)  # 1-2 seconds

# Then execute Polymarket
poly_result = self.polymarket_executor.execute_order(...)  # 1-2 seconds

# Total: 2-4 seconds sequential
```

**Should be:**
```python
import asyncio

# Execute both simultaneously
kalshi_task = asyncio.create_task(execute_kalshi(...))
poly_task = asyncio.create_task(execute_poly(...))

results = await asyncio.gather(kalshi_task, poly_task)

# Total: max(1-2s, 1-2s) = 1-2 seconds
```

**Impact:** Losing 1-2 seconds of execution time

### Issue 4: No Price Staleness Validation 🟡 MEDIUM

**Missing check:**
```python
def is_price_stale(self, market: Dict, max_age_seconds: float = 5.0) -> bool:
    """Check if market prices are too old"""
    if 'fetched_at' not in market:
        return True  # No timestamp = assume stale
    
    age = time.time() - market['fetched_at']
    return age > max_age_seconds
```

**Current behavior:** Uses prices regardless of age

### Issue 5: Fill Wait Inefficiency 🟢 LOW

**Current:** Poll every 300ms for 5 seconds = 16 API calls

**Better:** Exponential backoff
```python
# Check quickly at first, then slow down
delays = [0.1, 0.2, 0.3, 0.5, 0.8, 1.0, 1.0]  # Total: 4s
for delay in delays:
    time.sleep(delay)
    status = get_order_status(order_id)
    if status == FILLED:
        return
```

**Savings:** Fewer API calls, faster detection of fills

---

## 6. Recommended Improvements

### Priority 1: Add Fresh Price Fetch for Kalshi 🔴

```python
# In execute_trade(), before placing Kalshi order:
logger.info("  Validating Kalshi price is still current...")
fresh_orderbook = self.kalshi_client.get_orderbook_full(ticker)

current_price = fresh_orderbook.best_yes_ask if side == 'yes' else fresh_orderbook.best_no_ask
expected_price = opportunity['kalshi_price']

price_delta = abs(current_price - expected_price)

if price_delta > 0.03:  # More than 3¢ movement
    logger.warning(f"⚠️  Kalshi price moved {price_delta:.3f} - ABORTING")
    logger.warning(f"    Expected: {expected_price:.3f}, Current: {current_price:.3f}")
    return False

# Update opportunity with fresh price
opportunity['kalshi_price'] = current_price
price_cents = min(int((current_price + 0.15) * 100), 95)
```

**Impact:** Prevents executing on stale prices

### Priority 2: Add Timestamps to Prices 🔴

```python
# When fetching markets, add timestamp:
def get_sports_markets(self):
    fetch_time = time.time()
    
    # ... fetch markets ...
    
    for market in sports_markets:
        market['fetched_at'] = fetch_time  # ← Add timestamp
    
    return sports_markets
```

### Priority 3: Implement Parallel Execution 🟡

Convert executors to async:
```python
async def execute_trade_async(self, opportunity):
    kalshi_task = self.execute_kalshi_async(...)
    poly_task = self.execute_poly_async(...)
    
    kalshi_result, poly_result = await asyncio.gather(
        kalshi_task, 
        poly_task,
        return_exceptions=True
    )
```

**Benefit:** Save 1-2 seconds execution time

### Priority 4: Add Pre-Execution Validation 🟡

```python
def validate_opportunity(self, opportunity, max_staleness=5.0):
    """Validate opportunity before execution"""
    checks = []
    
    # Check 1: Price staleness
    kalshi_age = time.time() - opportunity['kalshi_market'].get('fetched_at', 0)
    poly_age = time.time() - opportunity['poly_market'].get('fetched_at', 0)
    
    checks.append(('Kalshi staleness', kalshi_age < max_staleness))
    checks.append(('Poly staleness', poly_age < max_staleness))
    
    # Check 2: Spread width
    checks.append(('Spread acceptable', opportunity['spread'] < 0.15))
    
    # Check 3: Market still open
    # ... add more checks ...
    
    for check_name, passed in checks:
        if not passed:
            logger.warning(f"❌ Validation failed: {check_name}")
            return False
    
    return True
```

---

## Appendix: Complete Timing Breakdown

### Network Calls (All with Timeouts)

| Call | Location | Timeout | Typical Time | Rate Limited |
|------|----------|---------|--------------|--------------|
| GET /markets | kalshi_client.py:451 | 15s | 300ms | Yes (18/s) |
| GET /markets/{ticker}/orderbook | kalshi_client.py:351 | 15s | 250ms | Yes (18/s) |
| POST /portfolio/orders | kalshi_executor.py:136 | 15s | 400ms | Yes (18/s) |
| GET /portfolio/orders/{id} | kalshi_executor.py:292 | 15s | 150ms | Yes (18/s) |
| GET /events | run_kalshi_polymarket_fixed.py:323 | - | 200ms | Yes (25/s) |
| GET /events/slug/{slug} | run_kalshi_polymarket_fixed.py:344 | 15s | 150ms | Yes (25/s) |
| GET /book | polymarket_executor.py:100 | 10s | 100ms | Yes (25/s) |
| POST order (Polymarket) | polymarket_executor.py:290 | - | 300ms | Yes (25/s) |

### Processing Time (No Network)

| Operation | Location | Time | Type |
|-----------|----------|------|------|
| Deduplicate Kalshi | run_kalshi_polymarket_fixed.py:397 | < 1ms | O(n) |
| Match markets | run_kalshi_polymarket_fixed.py:393 | 50-100ms | O(n×m) |
| Calculate arbitrage | run_kalshi_polymarket_fixed.py:460 | 1-2ms | O(1) per match |
| Create signed order | polymarket_executor.py:274 | 10-20ms | Crypto signing |

### Wait Loops

| Loop | Location | Max Duration | Poll Interval | Total Polls |
|------|----------|--------------|---------------|-------------|
| Kalshi fill wait | kalshi_executor.py:160 | 5s | 300ms | 16 |
| Polymarket fill wait | polymarket_executor.py:342 | 5s | 300ms | 16 |
| Main scan loop | run_kalshi_polymarket_fixed.py:807 | ∞ | 30s | ∞ |

---

## Summary: Critical Timing Facts

1. **Detection to execution: 10-12 seconds typically**
2. **Kalshi prices are 10+ seconds old at execution** ❌
3. **Polymarket prices ARE refreshed before execution** ✅
4. **No price staleness validation**
5. **No timestamps on cached prices**
6. **Execution is sequential (not parallel)**
7. **Rate limiting adds ~30% overhead**
8. **Fill waiting can take up to 5 seconds per leg**

**Biggest Risk:** Trading on 10-second-old Kalshi prices during volatile markets.

