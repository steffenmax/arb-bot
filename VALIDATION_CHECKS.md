# Validation Checks Before Trade Execution

## Overview

This document details **EVERY** validation check that occurs before your bot places a trade. Unlike many trading systems, your bot has **minimal validation** - there is **NO** dedicated `validate_opportunity()` function. Most checks happen within the arbitrage calculation itself.

---

## 1. Complete Code: Arbitrage Calculation (Primary Validation)

The main validation logic is embedded in `calculate_arbitrage()`:

```460:583:run_kalshi_polymarket_fixed.py
def calculate_arbitrage(self, kalshi: Dict, poly: Dict, sport: Sport) -> Optional[Dict]:
    """
    Calculate if there's an arbitrage opportunity.
    
    CRITICAL: Uses Kalshi's yes_team field to determine which team YES refers to,
    then matches it to the correct Polymarket outcome for proper hedging.
    """
    try:
        kalshi_yes = kalshi.get('yes_price', 0)
        kalshi_no = kalshi.get('no_price', 0)
        kalshi_yes_team = kalshi.get('yes_team', '').lower().strip()
        
        # Get Kalshi spread for quality check
        kalshi_spread = kalshi.get('spread', 0.10)  # Default to 10¢ if not available
        
        poly_outcomes = poly.get('outcomes', [])
        if len(poly_outcomes) < 2:
            return None
        
        poly_team_0 = poly_outcomes[0].get('outcome_name', '').lower().strip()
        poly_team_1 = poly_outcomes[1].get('outcome_name', '').lower().strip()
        poly_price_0 = float(poly_outcomes[0].get('price', 0))
        poly_price_1 = float(poly_outcomes[1].get('price', 0))
        
        # CRITICAL: Figure out which Poly outcome matches Kalshi YES team
        # Kalshi YES team should match one of the Poly outcomes
        aliases = self._get_team_aliases(kalshi_yes_team, sport)
        
        yes_matches_poly_0 = any(alias in poly_team_0 for alias in aliases) if aliases else False
        yes_matches_poly_1 = any(alias in poly_team_1 for alias in aliases) if aliases else False
        
        # Fallback: check if Kalshi yes_team contains any Poly team name
        if not yes_matches_poly_0 and not yes_matches_poly_1:
            # Try reverse match
            for alias in self._get_team_aliases(poly_team_0, sport):
                if alias in kalshi_yes_team:
                    yes_matches_poly_0 = True
                    break
            for alias in self._get_team_aliases(poly_team_1, sport):
                if alias in kalshi_yes_team:
                    yes_matches_poly_1 = True
                    break
        
        # Determine the correct pairing
        if yes_matches_poly_0:
            # Kalshi YES = Poly team 0 → Hedge: Kalshi YES + Poly team 1
            # OR: Kalshi NO (= Poly team 1) + Poly team 0
            yes_opposite_poly_idx = 1
            no_opposite_poly_idx = 0
            kalshi_yes_team_name = poly_team_0.title()
            kalshi_no_team_name = poly_team_1.title()
        elif yes_matches_poly_1:
            # Kalshi YES = Poly team 1 → Hedge: Kalshi YES + Poly team 0
            # OR: Kalshi NO (= Poly team 0) + Poly team 1
            yes_opposite_poly_idx = 0
            no_opposite_poly_idx = 1
            kalshi_yes_team_name = poly_team_1.title()
            kalshi_no_team_name = poly_team_0.title()
        else:
            # Can't determine mapping - log warning
            logger.warning(f"  ⚠️ Cannot map Kalshi yes_team '{kalshi_yes_team}' to Poly teams: {poly_team_0}, {poly_team_1}")
            # Fallback to original assumption (may be wrong)
            yes_opposite_poly_idx = 1
            no_opposite_poly_idx = 0
            kalshi_yes_team_name = "Unknown"
            kalshi_no_team_name = "Unknown"
        
        poly_price_for_yes = poly_price_1 if yes_opposite_poly_idx == 1 else poly_price_0
        poly_price_for_no = poly_price_0 if no_opposite_poly_idx == 0 else poly_price_1
        poly_team_for_yes = poly_outcomes[yes_opposite_poly_idx].get('outcome_name', '')
        poly_team_for_no = poly_outcomes[no_opposite_poly_idx].get('outcome_name', '')
        
        # Calculate arbitrage edges
        # Option 1: Buy Kalshi YES (bet on kalshi_yes_team) + Buy Poly opposite team
        total_cost_1 = kalshi_yes + poly_price_for_yes
        edge_1 = (1.0 - total_cost_1) * 100 if total_cost_1 < 1.0 else 0
        
        # Option 2: Buy Kalshi NO (bet on kalshi_no_team) + Buy Poly opposite team  
        total_cost_2 = kalshi_no + poly_price_for_no
        edge_2 = (1.0 - total_cost_2) * 100 if total_cost_2 < 1.0 else 0
        
        # SPREAD FILTER: Skip opportunities where Kalshi spread is too wide
        # Wide spreads (>15¢) often mean the price we see won't be executable
        MAX_ACCEPTABLE_SPREAD = 0.15
        if kalshi_spread > MAX_ACCEPTABLE_SPREAD:
            logger.debug(f"  ⏭️ Skipping due to wide Kalshi spread: {kalshi_spread:.2f}")
            return None
        
        if edge_1 >= MIN_EDGE_PERCENTAGE and edge_1 >= edge_2:
            return {
                'edge': edge_1,
                'kalshi_market': kalshi,
                'poly_market': poly,
                'sport': sport,
                'kalshi_side': 'yes',
                'kalshi_team': kalshi_yes_team_name,
                'kalshi_price': kalshi_yes,
                'poly_outcome_index': yes_opposite_poly_idx,
                'poly_team': poly_team_for_yes,
                'poly_price': poly_price_for_yes,
                'spread': kalshi_spread,
            }
        elif edge_2 >= MIN_EDGE_PERCENTAGE:
            return {
                'edge': edge_2,
                'kalshi_market': kalshi,
                'poly_market': poly,
                'sport': sport,
                'kalshi_side': 'no',
                'kalshi_team': kalshi_no_team_name,
                'kalshi_price': kalshi_no,
                'poly_outcome_index': no_opposite_poly_idx,
                'poly_team': poly_team_for_no,
                'poly_price': poly_price_for_no,
                'spread': kalshi_spread,
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Error calculating arbitrage: {e}")
        import traceback
        traceback.print_exc()
        return None
```

---

## 2. ALL Validation Conditions

### ✅ Check 1: Polymarket Outcome Count (Line 476-477)

```python
poly_outcomes = poly.get('outcomes', [])
if len(poly_outcomes) < 2:
    return None
```

**Purpose:** Ensure market has exactly 2 outcomes (binary market)  
**Rejects:** Markets with < 2 outcomes  
**Impact:** Prevents crashes on malformed data

---

### ✅ Check 2: Kalshi Spread Filter (Lines 541-546)

```python
MAX_ACCEPTABLE_SPREAD = 0.15
if kalshi_spread > MAX_ACCEPTABLE_SPREAD:
    logger.debug(f"  ⏭️ Skipping due to wide Kalshi spread: {kalshi_spread:.2f}")
    return None
```

**Purpose:** Reject markets with wide bid-ask spreads  
**Threshold:** 15 cents (0.15)  
**Reasoning:** Wide spreads = low liquidity or stale prices → execution will fail  

**Example from logs:**
```
Kalshi: YES(San Franci)=0.990 NO=0.990 [spread:0.97]
```
This would be **REJECTED** (97¢ spread >> 15¢ limit)

---

### ✅ Check 3: Minimum Edge Percentage (Lines 548, 562)

```python
MIN_EDGE_PERCENTAGE = float(os.getenv('MIN_EDGE_PERCENTAGE', '5.0'))

if edge_1 >= MIN_EDGE_PERCENTAGE and edge_1 >= edge_2:
    # Return opportunity
elif edge_2 >= MIN_EDGE_PERCENTAGE:
    # Return opportunity
```

**Configuration Location:** Lines 41-42

```41:42:run_kalshi_polymarket_fixed.py
MIN_EDGE_PERCENTAGE = float(os.getenv('MIN_EDGE_PERCENTAGE', '5.0'))
MAX_STAKE_PER_TRADE = float(os.getenv('MAX_STAKE_PER_TRADE', '10'))
```

**Purpose:** Only execute trades with meaningful profit  
**Default Threshold:** 5.0% edge  
**Calculation:**  
- `edge = (1.0 - total_cost) * 100`
- Example: If Kalshi YES = 0.48 and Poly opposite = 0.46, total cost = 0.94 → edge = 6%

---

### ✅ Check 4: Total Cost Must Be < 1.0 (Lines 534-539)

```python
total_cost_1 = kalshi_yes + poly_price_for_yes
edge_1 = (1.0 - total_cost_1) * 100 if total_cost_1 < 1.0 else 0

total_cost_2 = kalshi_no + poly_price_for_no
edge_2 = (1.0 - total_cost_2) * 100 if total_cost_2 < 1.0 else 0
```

**Purpose:** Ensure arbitrage is mathematically valid  
**Rejects:** Any opportunity where prices sum to ≥ 1.0 (no edge possible)

---

### ✅ Check 5: Already Executed Filter (Lines 736-738)

```735:738:run_kalshi_polymarket_fixed.py
# Skip games we've already traded
if game_id in self.executed_games:
    logger.info(f"  ⏭️  Skipping already traded: {game_id}")
    continue
```

**Purpose:** Prevent trading the same game multiple times  
**Implementation:** In-memory set `self.executed_games`  
**Impact:** Once a game is traded (or trade attempted), it's never retried

---

### ⚠️ Check 6: Team Mapping Validation (Lines 518-525) - **WEAK**

```python
else:
    # Can't determine mapping - log warning
    logger.warning(f"  ⚠️ Cannot map Kalshi yes_team '{kalshi_yes_team}' to Poly teams: {poly_team_0}, {poly_team_1}")
    # Fallback to original assumption (may be wrong)
    yes_opposite_poly_idx = 1
    no_opposite_poly_idx = 0
    kalshi_yes_team_name = "Unknown"
    kalshi_no_team_name = "Unknown"
```

**Purpose:** Ensure correct hedging (Lakers YES + Celtics)  
**Problem:** When mapping fails, it **CONTINUES ANYWAY** with a guess  
**Result:** Could bet on same team twice → guaranteed loss  

**Example from logs:**
```
⚠️ Cannot map Kalshi yes_team 'buffalo' to Poly teams: patriots, jets
```
**Action Taken:** Continues with fallback (DANGEROUS!)

---

## 3. What Is **NOT** Checked

### ❌ No Balance Verification

**Not Checked:**
- Whether you have enough funds on Kalshi
- Whether you have enough funds on Polymarket
- Whether USDC approval is sufficient

**Why It Matters:** Order will fail at execution time, leaving you with partial hedge

**Where Balance *Could* Be Checked:**

```python
# These functions exist but are NOT called before trading:
kalshi_client.get_balance()  # Line 612 in kalshi_client.py
polymarket_executor.client.get_balance_allowance()  # py_clob_client library
```

---

### ❌ No Liquidity/Depth Check

**Not Checked:**
- Order book depth at your target price
- Whether your stake is larger than available liquidity

**Available Data (But Unused):**

```486:504:src/data_sources/kalshi_client.py
return {
    'ticker': ticker,
    'title': title,
    'subtitle': market.get('subtitle', ''),
    'category': market.get('category', 'Sports'),
    'series': market.get('series'),
    'yes_team': yes_team,  # The team that YES refers to
    'yes_price': yes_ask,
    'no_price': no_ask,
    'yes_bid': orderbook.best_yes_bid,
    'no_bid': orderbook.best_no_bid,
    'yes_ask': yes_ask,
    'no_ask': no_ask,
    'spread': orderbook.yes_spread,
    'yes_depth_usd': orderbook.yes_bid_depth_usd,  # ← Available but not checked!
    'no_depth_usd': orderbook.no_bid_depth_usd,    # ← Available but not checked!
    'close_time': market.get('close_time'),
    'volume': market.get('volume', 0),
}
```

**Risk:** You might try to buy $5 worth when only $2 is available at that price

---

### ❌ No Time-to-Close Check

**Not Checked:**
- How soon the market closes
- Whether there's enough time to execute both legs

**Available Data (But Unused):**
- `close_time` field in Kalshi market data (line 502)

**Risk:** Market could close before you complete both sides of hedge

---

### ❌ No Polymarket Spread Check

**Kalshi spread IS checked (line 544), but Polymarket spread is NOT**

```python
if kalshi_spread > MAX_ACCEPTABLE_SPREAD:
    return None

# But NO equivalent check for Polymarket!
```

**Risk:** Kalshi has tight spread (5¢) but Polymarket has 50¢ spread → order fails

---

### ❌ No Matching Confidence Score

**Not Checked:**
- How confident the fuzzy matching is
- Whether team names were an exact match vs. fallback

**Current Behavior:** Either matches or uses dangerous fallback (lines 518-525)

---

### ❌ No Fee/Slippage Calculation

**Not Included in Edge Calculation:**
- Kalshi trading fees
- Polymarket trading fees
- Gas fees (Polymarket)
- Slippage from aggressive orders

**Execution Adds Slippage (Lines 606, 640):**

```606:606:run_kalshi_polymarket_fixed.py
price_cents = min(int((opportunity['kalshi_price'] + 0.15) * 100), 95)
```

```640:640:run_kalshi_polymarket_fixed.py
max_price = min(opportunity['poly_price'] + 0.05, 0.99)
```

**Impact:** Detected 5% edge could become 2% after fees/slippage

---

## 4. Examples of Failed Validation

### Example 1: Wide Spread (Most Common)

**From logs:** `live_v2_20251228_171231.log`

```
Kalshi: YES(San Franci)=0.990 NO=0.990 [spread:0.97]
Poly:   Seahawks    =0.555  49ers       =0.445
```

**Apparent Edge:** 99¢ + 44.5¢ = 143.5¢ → **No edge**  
Wait, this doesn't show edge. Let me recalculate:
- Kalshi NO (Seahawks) = 0.990
- Poly Seahawks = 0.555
- Total = 1.545 → **No edge** (>1.0)

BUT if spread weren't so wide:
- True Kalshi NO might be ~0.52
- Poly Seahawks = 0.555
- Total = 1.075 → Still no edge

**Filter Applied:** Wide spread (0.97 > 0.15) → **REJECTED**

---

### Example 2: Team Mapping Failure

**From logs:**

```
⚠️ Cannot map Kalshi yes_team 'buffalo' to Poly teams: patriots, jets
```

**Problem:** Kalshi ticker says "buffalo" but Polymarket shows Patriots vs Jets (wrong game!)  
**Action:** Bot logs warning but **CONTINUES** with fallback  
**Result:** Would bet on wrong teams if edge calculation passed

---

### Example 3: Edge Too Low

**Hypothetical:**
```
Kalshi YES (Lakers) = 0.48
Poly No (Celtics) = 0.54
Total cost = 1.02
Edge = -2% (negative!)
```

**Filter Applied:** Edge < MIN_EDGE_PERCENTAGE → **REJECTED** (returns None)

---

### Example 4: Insufficient Outcomes

**Hypothetical:**
```python
poly_outcomes = []  # Empty or only 1 outcome
```

**Filter Applied:** `len(poly_outcomes) < 2` → **REJECTED**

---

## 5. Summary Table

| Check | Threshold | Location | Status |
|-------|-----------|----------|--------|
| **Polymarket outcome count** | Must be 2 | Line 476 | ✅ Implemented |
| **Kalshi spread** | ≤ 15¢ | Lines 541-546 | ✅ Implemented |
| **Minimum edge** | ≥ 5% (configurable) | Lines 548, 562 | ✅ Implemented |
| **Total cost** | < 1.0 | Lines 534-539 | ✅ Implemented |
| **Already executed** | Not in `executed_games` | Lines 736-738 | ✅ Implemented |
| **Team mapping** | Must match | Lines 518-525 | ⚠️ Weak (uses fallback) |
| **Kalshi balance** | Sufficient funds | N/A | ❌ Not checked |
| **Polymarket balance** | Sufficient funds | N/A | ❌ Not checked |
| **Liquidity/depth** | Stake ≤ available | N/A | ❌ Not checked |
| **Polymarket spread** | No limit | N/A | ❌ Not checked |
| **Time to close** | No minimum | N/A | ❌ Not checked |
| **Matching confidence** | No threshold | N/A | ❌ Not checked |
| **Fees/slippage** | Not factored in | N/A | ❌ Not checked |

---

## 6. Recommendations for Additional Validation

### Priority 1: Fix Team Mapping Fallback 🔴

**Current Code (Lines 518-525):** Continues with guess when mapping fails  
**Recommended Fix:** Return `None` instead

```python
else:
    # Can't determine mapping - REJECT opportunity
    logger.warning(f"  ⚠️ Cannot map Kalshi yes_team '{kalshi_yes_team}' to Poly teams: {poly_team_0}, {poly_team_1}")
    return None  # Don't risk incorrect hedge!
```

---

### Priority 2: Add Balance Checks 🟡

```python
def validate_balance(self, opportunity: Dict) -> bool:
    """Check if sufficient balance before executing"""
    stake_each = MAX_STAKE_PER_TRADE / 2
    
    # Check Kalshi
    kalshi_balance = self.kalshi_client.get_balance()
    if kalshi_balance and kalshi_balance.get('total', 0) < stake_each:
        logger.warning(f"Insufficient Kalshi balance: ${kalshi_balance.get('total', 0):.2f} < ${stake_each}")
        return False
    
    # Check Polymarket
    if self.polymarket_executor:
        poly_balance = self.polymarket_executor.client.get_balance_allowance()
        if poly_balance and float(poly_balance.get('balance', 0)) < stake_each:
            logger.warning(f"Insufficient Polymarket balance: ${poly_balance.get('balance', 0):.2f} < ${stake_each}")
            return False
    
    return True
```

---

### Priority 3: Add Polymarket Spread Check 🟡

```python
# In calculate_arbitrage(), after line 546:
poly_spread = abs(poly_price_0 - poly_price_1)
if poly_spread > MAX_ACCEPTABLE_SPREAD:
    logger.debug(f"  ⏭️ Skipping due to wide Polymarket spread: {poly_spread:.2f}")
    return None
```

---

### Priority 4: Add Liquidity Check 🟢

```python
# In calculate_arbitrage(), use available depth data:
kalshi_side = 'yes' if edge_1 > edge_2 else 'no'
depth_field = 'yes_depth_usd' if kalshi_side == 'yes' else 'no_depth_usd'
available_depth = kalshi.get(depth_field, 0)

stake_each = MAX_STAKE_PER_TRADE / 2
if available_depth < stake_each:
    logger.debug(f"  ⏭️ Insufficient Kalshi liquidity: ${available_depth} < ${stake_each}")
    return None
```

---

### Priority 5: Add Time-to-Close Check 🟢

```python
from datetime import datetime, timedelta

# In calculate_arbitrage():
close_time_str = kalshi.get('close_time')
if close_time_str:
    close_time = datetime.fromisoformat(close_time_str.replace('Z', '+00:00'))
    time_remaining = close_time - datetime.now(timezone.utc)
    
    MIN_TIME_TO_CLOSE = timedelta(minutes=30)
    if time_remaining < MIN_TIME_TO_CLOSE:
        logger.debug(f"  ⏭️ Market closes too soon: {time_remaining.total_seconds()/60:.1f} min")
        return None
```

---

## 7. Configuration Variables

All thresholds are set at the top of `run_kalshi_polymarket_fixed.py`:

```41:46:run_kalshi_polymarket_fixed.py
MIN_EDGE_PERCENTAGE = float(os.getenv('MIN_EDGE_PERCENTAGE', '5.0'))
MAX_STAKE_PER_TRADE = float(os.getenv('MAX_STAKE_PER_TRADE', '10'))
POLL_INTERVAL_SECONDS = int(os.getenv('POLL_INTERVAL_SECONDS', '30'))
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', '')
DISCORD_NOTIFICATIONS = os.getenv('DISCORD_NOTIFICATIONS', 'true').lower() == 'true'
SELECTED_SPORTS = os.getenv('SELECTED_SPORTS', 'nfl').lower()
```

**Hardcoded Constants:**
- `MAX_ACCEPTABLE_SPREAD = 0.15` (line 543)

**To Change Thresholds:**
1. Set environment variables in `.env` file
2. Or edit default values in lines 41-46
3. For spread threshold, edit line 543 directly

---

## Conclusion

Your bot has **5 basic validation checks** but is **missing 8 critical safety checks**. The most dangerous issue is the team mapping fallback (lines 518-525) which could result in betting on the same team twice.

**Immediate Action Required:**
1. Fix team mapping fallback to reject instead of guess
2. Add balance checks before execution
3. Add Polymarket spread filter (currently only checks Kalshi)

