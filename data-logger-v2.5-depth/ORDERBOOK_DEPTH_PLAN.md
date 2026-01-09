# 🎯 Orderbook Depth Development Plan - v2.5-depth

## 📊 Current Status

### ✅ Completed
- Enhanced Kalshi client with `get_market_orderbook()` and `calculate_vwap()`
- 14 active NFL games configured
- Project structure ready

### 🚧 To Implement
1. Polymarket CLOB orderbook integration
2. Database schema for orderbook storage
3. Enhanced data logger with depth collection
4. Depth-aware arbitrage analyzer
5. Real-time monitor with liquidity metrics

---

## 🔬 Phase 1: Research & Test APIs

### Kalshi Orderbook API
**Status**: ✅ Code written, needs testing with live markets

**Endpoint**: `GET /markets/{ticker}/orderbook?depth={levels}`

**What we get**:
```python
{
  'ticker': 'KXNFLGAME-26JAN04BALPIT-PIT',
  'yes_bids': [(0.620, 500, 3), (0.615, 1000, 5), ...],  # (price, size, order_count)
  'yes_asks': [(0.625, 300, 2), (0.630, 800, 4), ...],
  'no_bids': [...],
  'no_asks': [...]
}
```

**VWAP Calculation**: ✅ Already implemented
```python
vwap, filled, remaining, slippage = client.calculate_vwap(
    orderbook['yes_asks'], 
    target_size=1000
)
```

**Next**: Test with live market when games start

---

### Polymarket CLOB Orderbook API
**Status**: ⏳ Needs implementation

**Endpoint**: `GET https://clob.polymarket.com/book?token_id={id}`

**Expected Response**:
```json
{
  "market": "token_id_here",
  "asset_id": "...",
  "bids": [
    {"price": "0.62", "size": "500.00"},
    {"price": "0.61", "size": "1000.00"}
  ],
  "asks": [
    {"price": "0.65", "size": "300.00"},
    {"price": "0.66", "size": "800.00"}
  ],
  "timestamp": 1234567890
}
```

**Challenge**: We need `token_id` for each outcome
- Currently using `/events/slug/{slug}` which returns prices but not token IDs
- Need to fetch token IDs from market details

**Next**: Implement token ID fetching and orderbook integration

---

## 🗄️ Phase 2: Database Schema

### New Table: `orderbook_snapshots`

```sql
CREATE TABLE orderbook_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,  -- Links to price_snapshots
    event_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    market_id TEXT NOT NULL,
    side TEXT NOT NULL,  -- 'yes' or 'no'
    order_type TEXT NOT NULL,  -- 'bid' or 'ask'
    level INTEGER NOT NULL,  -- 1 = best, 2 = second best, etc.
    price REAL NOT NULL,
    size REAL NOT NULL,
    order_count INTEGER,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (snapshot_id) REFERENCES price_snapshots(id)
);
```

**Benefits**:
- Store full orderbook ladder
- Query depth at any historical point
- Calculate historical VWAP
- Analyze liquidity evolution

---

## 📝 Phase 3: Enhanced Data Logger

### Current Flow (Top-of-Book Only)
```
Fetch Market Data → Extract Best Bid/Ask → Log to price_snapshots
```

### New Flow (With Depth)
```
Fetch Market Data → Extract Best Bid/Ask → Log to price_snapshots
                  ↓
              Fetch Orderbook → Parse Ladder → Log to orderbook_snapshots
```

### Implementation Strategy

**Option A: Parallel Collection** (Recommended)
- Fetch prices and orderbooks simultaneously
- Minimal impact on cycle time
- More data per cycle

**Option B: Sequential Collection**
- Fetch prices first, then orderbooks
- Simpler to implement
- Slightly slower cycles

**Trade-offs**:
- **Speed**: Parallel faster (~1-2 seconds saved per cycle)
- **Reliability**: Sequential easier to debug
- **Complexity**: Parallel requires more error handling

**Recommendation**: Start with **Sequential**, optimize to **Parallel** later

---

## 🎯 Phase 4: Depth-Aware Arbitrage Detection

### Current Logic (v2)
```python
# Simple: check if sum of best prices < 1.0
if (kalshi_yes_ask + poly_no_price) < 0.97:
    opportunity = True
    profit = 1.0 - (kalshi_yes_ask + poly_no_price)
```

**Problem**: Doesn't know if tradeable at size!

### New Logic (v2.5)
```python
# Advanced: check tradeable size and slippage
kalshi_vwap = calculate_vwap(kalshi_yes_asks, target_size=1000)
poly_vwap = calculate_vwap(poly_no_bids, target_size=1000)

if kalshi_vwap.filled == 1000 and poly_vwap.filled == 1000:
    total_cost = kalshi_vwap.vwap + poly_vwap.vwap
    if total_cost < 0.97:
        opportunity = True
        profit = 1.0 - total_cost
        max_size = min(kalshi_vwap.filled, poly_vwap.filled)
        slippage = kalshi_vwap.slippage + poly_vwap.slippage
```

**Benefits**:
- ✅ Know exact tradeable size
- ✅ Account for slippage
- ✅ Show realistic profit after execution
- ✅ Filter out phantom opportunities

---

## 🔍 Phase 5: Enhanced Real-Time Monitor

### Current Display
```
⚡ ARBITRAGE: Panthers vs Buccaneers
   Profit: 11.5%
   Duration: 14 seconds
```

### New Display (With Depth)
```
⚡ ARBITRAGE: Ravens vs Steelers
   Profit (Best): 8.5%
   Profit (VWAP @$500): 6.2%
   
   Tradeable Size:
   - $100: 8.3% profit ✅
   - $500: 6.2% profit ✅
   - $1000: 3.1% profit ✅
   - $2000: Insufficient liquidity ❌
   
   Slippage: 2.3%
   Duration: 12 seconds
   
   Execution Plan:
   1. Buy Ravens YES @ Kalshi: $0.385 VWAP (500 contracts)
   2. Buy Steelers YES @ Poly: $0.608 VWAP (500 contracts)
   Total: $0.993 → $7 profit on $500
```

---

## 📋 Implementation Checklist

### Step 1: Polymarket Token ID Integration
- [ ] Add method to fetch token IDs from event details
- [ ] Store token IDs in market configuration
- [ ] Test token ID retrieval for NFL games

### Step 2: Polymarket CLOB Orderbook
- [ ] Add `get_orderbook(token_id)` to polymarket_client.py
- [ ] Parse CLOB response format
- [ ] Add VWAP calculation for Polymarket
- [ ] Test with live market

### Step 3: Database Schema
- [ ] Create `orderbook_snapshots` table
- [ ] Add methods to `db_setup.py`
- [ ] Test inserting orderbook data
- [ ] Add indexes for performance

### Step 4: Enhanced Data Logger
- [ ] Add orderbook fetching to collection cycle
- [ ] Implement sequential collection first
- [ ] Add error handling for orderbook failures
- [ ] Test with 14 NFL games

### Step 5: Depth-Aware Analysis
- [ ] Create `analyze_with_depth.py`
- [ ] Implement VWAP-based arbitrage detection
- [ ] Add tradeable size calculation
- [ ] Generate liquidity reports

### Step 6: Real-Time Monitor v2
- [ ] Update `realtime_arb_monitor.py` with depth
- [ ] Add tiered profit display ($100, $500, $1K, $2K)
- [ ] Show slippage impact
- [ ] Add execution plan suggestions

---

## 🎯 Next Immediate Steps

1. **Test Kalshi Orderbook** with a live NFL game (when they start)
2. **Implement Polymarket token ID fetching**
3. **Implement Polymarket CLOB orderbook integration**
4. **Create database schema**
5. **Test end-to-end with 1-2 games**

---

**Ready to proceed?** Let's start with **Polymarket token ID and CLOB integration**!

