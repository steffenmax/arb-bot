# Fee Model Corrections - Critical Updates

## ❌ OLD (INCORRECT) MODEL

### What the bot was showing:
```
Kalshi Fee: 7% of profits
Polymarket Fee: 2% of profits
Gas: ~$1.50 fixed

Example (6.38% gross edge):
Investment: $94
Gross Profit: $6.00
Kalshi Fee: $6.00 × 0.07 = $0.42
Poly Fee: $6.00 × 0.02 = $0.12
Gas: $1.50
Net Profit: $6.00 - $2.04 = $3.96 (4.21% ROI)
```

## ✅ NEW (CORRECT) MODEL

### Actual Fee Structures:

#### **Kalshi Fees**
**Formula**: `fee = ceil(0.07 × Q × P × (1-P))`

Where:
- Q = quantity of contracts
- P = price per contract ($0-$1)
- P(1-P) = variance term (peaks at 0.25 when P=0.5)

**Key insights**:
- NOT a percentage of profits
- Depends on price AND quantity
- Highest at mid-market (P=0.5): ~7% of notional
- Lower at extremes (P near 0 or 1)
- Rounded up to nearest cent per Kalshi's spec

**Maker vs Taker**:
- Taker orders (immediate match): 7% rate
- Maker orders (resting): 1.75% rate

Reference: [Kalshi Trading Fees](https://kalshi.com/fees)

#### **Polymarket Fees**
**For sports markets**: **0%** (zero)

Per Polymarket docs:
- "vast majority" of markets have no trading fees
- Sports moneylines are typically 0 bps maker/taker
- Exceptions exist (some 15-min crypto markets)

Reference: [Polymarket Documentation](https://docs.polymarket.com/)

#### **Gas Costs**
**Depends on integration**:
- **Relayer/Proxy wallet**: $0 (Polymarket pays gas)
- **EOA wallet**: ~$0.10-$0.50 (Polygon gas)

Reference: [Polymarket Gasless Trading](https://docs.polymarket.com/)

### Corrected Example (Denver/Philly 6.38% gross):

```
Buy 500 contracts @ $0.94 total = $470 investment

Kalshi Fee Calculation:
  Q = 500
  P = 0.24 (Denver)
  P(1-P) = 0.24 × 0.76 = 0.1824
  Raw fee = 0.07 × 500 × 0.1824 = 6.384
  Rounded up = $6.39

Polymarket Fee: $0.00 (sports markets)
Gas: $0.00 (assuming relayer)

Net Profit: $30.00 - $6.39 = $23.61
Net ROI: 5.02%
```

## 🔑 Key Differences Summary

| Aspect | Old Model | Correct Model |
|--------|-----------|---------------|
| **Kalshi Fee** | 7% of profit | `ceil(0.07 × Q × P × (1-P))` |
| **Poly Fee** | 2% of profit | 0% for sports |
| **Gas** | $1.50 fixed | $0 (relayer) or ~$0.10-$0.50 (EOA) |
| **Size Dependent?** | No | Yes (Kalshi fee scales with Q) |
| **Price Dependent?** | No | Yes (Kalshi fee varies with P) |

## 📊 Impact on Edge Detection

### Old threshold: Total < 1.0
Problem: Doesn't account for:
- Size-dependent Kalshi fees
- Price-dependent fee structure
- Optimal quantity selection

### New approach: Net profit calculation
```python
net_profit(Q) = Q × (1 - (P_k + P_p)) - ceil(0.07 × Q × P_k × (1-P_k))

Profitable when:
  net_profit(Q) > min_$ (e.g., $5)
  AND roi(Q) > min_roi (e.g., 2%)
```

## 💡 Improved Kalshi Price Logic

### Old method:
```
Track two separate markets:
- Market 1: "Denver to win" (YES/NO)
- Market 2: "Philadelphia to win" (YES/NO)
Cost(Denver) = Denver_YES_ASK
Cost(Philly) = Philly_YES_ASK
```

### Better method:
```
Use NO market as inverse:
Cost(Denver) = min(Denver_YES_ASK, Philly_NO_ASK)
Cost(Philly) = min(Philly_YES_ASK, Denver_NO_ASK)
```

**Why better?**:
- NO market pays $1 if that team loses (inverse exposure)
- Avoids missing arbs from stale/wide secondary markets
- More capital efficient

## 🎯 Real-World Example Comparison

### Scenario: Total cost = 0.94, Quantity = 100 contracts

| Price | Old Net ROI | Correct Net ROI | Difference |
|-------|-------------|-----------------|------------|
| P=0.10 | 4.21% | **5.72%** | +1.51% (fees lower at extremes) |
| P=0.24 | 4.21% | **5.02%** | +0.81% |
| P=0.50 | 4.21% | **2.32%** | **-1.89%** (fees highest at mid) |

**Key insight**: Opportunities at extreme prices (near 0 or 1) are MORE profitable than the old model suggested!

## ⚠️ Additional Considerations

### 1. Settlement Risk
Both platforms must resolve identically:
- Same game rules (OT, cancellation, etc.)
- Same result criteria
- Same timing

### 2. Competition
Displayed liquidity ≠ executable liquidity:
- Other bots competing
- Expect 10-30% fill rate in practice
- Size accordingly

### 3. Optimal Quantity
Use the calculator to find:
```python
best_Q = argmax(net_profit(Q))
subject to:
  - net_profit(Q) >= min_$
  - roi(Q) >= min_roi
  - Q <= available_liquidity
```

## 📁 Implementation

New calculator available in `arb_calculator.py`:
```python
from arb_calculator import ArbCalculator

calc = ArbCalculator(
    min_roi_pct=2.0,
    min_profit_usd=5.0,
    gas_cost_usd=0.0  # Relayer mode
)

result = calc.evaluate_arbitrage(
    kalshi_a_yes_ask=0.24,
    kalshi_a_no_ask=0.76,
    kalshi_b_yes_ask=0.76,
    kalshi_b_no_ask=0.24,
    poly_a_ask=0.31,
    poly_b_ask=0.70,
    max_quantity=500
)
```

---

**Bottom Line**: The old model **underestimated** Kalshi fees for mid-market prices and **overestimated** Polymarket fees. The new model is accurate and size-aware.

