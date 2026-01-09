# Edge Calculation Deep Dive

## 📊 Summary of Corrections

Your bot detected **43 arbitrage opportunities** during the Denver/Philadelphia game. With the **correct fee model**:

- **22 opportunities (51%)** were net profitable after real fees
- **21 opportunities (49%)** were break-even or unprofitable after fees
- **Total potential profit**: $242.69 (if all executed perfectly)
- **Average duration**: 10.5 seconds

## 🔍 How the Bot Currently Calculates Edge

### 1. **Data Collection** (`data_logger_depth.py`)

#### Kalshi (lines 219-234):
```python
# Fetches TWO markets per game:
Market 1: "Denver to win"
  - yes_ask = $0.24 (cost to buy Denver YES)
  - yes_bid = $0.20 (cost to sell Denver YES)
  - no_ask = $0.76 (cost to buy Denver NO = Philly wins)
  - no_bid = $0.72

Market 2: "Philadelphia to win"
  - yes_ask = $0.76 (cost to buy Philly YES)
  - yes_bid = $0.72
  - no_ask = $0.24 (cost to buy Philly NO = Denver wins)
  - no_bid = $0.20
```

**Current logic**: Uses only `yes_ask` from each market
**Better logic**: Use `min(yes_ask, opposite_no_ask)` for each side

#### Polymarket (lines 323-348):
```python
# Fetches ONE market with multiple token IDs:
Market: "Denver vs Philadelphia"
  Token 1 "Nuggets": best_ask = $0.31
  Token 2 "76ers": best_ask = $0.70
```

Each token has its own orderbook stored separately.

### 2. **Arbitrage Detection** (`live_dashboard.py` lines 242-289)

```python
def calculate_arbitrage(kalshi_data, poly_data, team_a, team_b):
    # Try BOTH combinations:
    
    # Combo 1: Kalshi Team A + Poly Team B
    total_1 = kalshi_a['ask'] + poly_b['ask']
    
    # Combo 2: Kalshi Team B + Poly Team A  
    total_2 = kalshi_b['ask'] + poly_a['ask']
    
    # Return lowest total
    return min(total_1, total_2)
```

**Current threshold**: Flags as "ARB" when `total < 1.0`

**Problem**: This is PRE-FEE profit. Doesn't account for:
- Size-dependent Kalshi fees
- Price-dependent fee structure  
- Optimal quantity selection

### 3. **Profit Calculation** (line 480)

```python
profit_pct = ((1.0 - total) / total) * 100
```

This shows **gross profit percentage** only.

## ✅ What Should Be Calculated

### Correct Fee Models

#### Kalshi Fee (per their API docs):
```
fee = ceil(0.07 × Q × P × (1-P))

Where:
  Q = quantity (number of contracts)
  P = price per contract
  P(1-P) = variance term (maximizes at P=0.5)
```

**Key insights**:
- Highest fees at mid-market (P ≈ 0.50): ~7% of notional
- Lower fees at extremes (P near 0 or 1): ~0-3% of notional
- **NOT** a percentage of profits

#### Polymarket Fee (for sports):
```
fee = 0  (zero)
```

Most sports markets have 0% trading fees.

#### Gas Costs:
```
gas = 0  (if using relayer/proxy wallet)
gas = $0.10-$0.50  (if using EOA wallet on Polygon)
```

### Net Profit Formula

```python
gross_profit = Q × (1 - (P_kalshi + P_poly))
kalshi_fee = ceil(0.07 × Q × P_kalshi × (1 - P_kalshi))
poly_fee = 0
gas = 0  (assuming relayer)

net_profit = gross_profit - kalshi_fee - poly_fee - gas
net_roi = (net_profit / (Q × (P_kalshi + P_poly))) × 100
```

## 📈 Real Examples from Your Data

### Example 1: Opportunity #13 (Best)

**Raw prices**:
- Kalshi: $0.050
- Polymarket: $0.680
- Gross total: $0.73
- Gross edge: 37%

**Old model said**:
- Profit: 37% (way too optimistic!)

**Correct calculation (500 contracts)**:
```
Investment: 500 × $0.73 = $365
Payout: 500 × $1.00 = $500
Gross profit: $135

Kalshi fee:
  P(1-P) = 0.05 × 0.95 = 0.0475
  Fee = ceil(0.07 × 500 × 0.0475) = ceil(1.6625) = $1.67

Net profit: $135.00 - $1.67 = $133.33
Net ROI: 36.53%
```

**Duration**: 5.9 seconds (automated trading needed)

### Example 2: Opportunity #11 (6.38% gross - the one you saw)

**Raw prices**:
- Kalshi: $0.290
- Polymarket: $0.650
- Gross total: $0.94
- Gross edge: 6.38%

**Old model said**:
- Profit: 6.38%

**Correct calculation (500 contracts)**:
```
Investment: 500 × $0.94 = $470
Payout: 500 × $1.00 = $500
Gross profit: $30

Kalshi fee:
  P(1-P) = 0.29 × 0.71 = 0.2059
  Fee = ceil(0.07 × 500 × 0.2059) = ceil(7.2065) = $7.21

Net profit: $30.00 - $7.21 = $22.79
Net ROI: 4.85%
```

**Duration**: 4.9 seconds

**Verdict**: Still profitable, but 4.85% net vs 6.38% gross

### Example 3: Opportunity #40 (Marginal)

**Raw prices**:
- Kalshi: $0.510
- Polymarket: $0.480
- Gross total: $0.99
- Gross edge: 1.01%

**Old model said**:
- Profit: 1.01%

**Correct calculation (500 contracts)**:
```
Investment: 500 × $0.99 = $495
Payout: 500 × $1.00 = $500
Gross profit: $5

Kalshi fee:
  P(1-P) = 0.51 × 0.49 = 0.2499 (near maximum!)
  Fee = ceil(0.07 × 500 × 0.2499) = ceil(8.7465) = $8.75

Net profit: $5.00 - $8.75 = -$3.75
Net ROI: -0.76%
```

**Duration**: 5.8 seconds

**Verdict**: NOT profitable after fees! Would lose money.

## 🎯 Key Takeaways

### 1. **Kalshi Fees Dominate**
- For mid-market prices (P ≈ 0.5), Kalshi fees can eat 8-9% of notional
- For extreme prices (P < 0.2 or P > 0.8), fees are only 1-3%
- **Implication**: Opportunities at extreme prices are MORE valuable than mid-market

### 2. **Polymarket Is Fee-Free**
- 0% trading fees for sports markets
- Gas can be $0 if using relayer
- **Implication**: Polymarket side is "pure" price

### 3. **Size Matters**
- Optimal quantity varies by opportunity
- Larger trades have higher absolute fees but similar %
- Need to balance: profit vs liquidity vs competition

### 4. **The "Total < 1.0" Rule Is Wrong**
Should be:
```python
# Old (wrong)
if total < 1.0:
    flag_as_arb()

# Correct
net_profit = calculate_net_for_quantity(Q, prices)
if net_profit > min_$ and roi > min_roi:
    flag_as_arb()
```

## 🔧 Improvements Implemented

### New Tools:

1. **`arb_calculator.py`**
   - Accurate Kalshi fee formula
   - Polymarket 0% fees
   - Size-aware profit calculation
   - Optimal quantity finder

2. **`reanalyze_arb_opportunities.py`**
   - Re-analyzes logged opportunities
   - Shows old vs new model comparison
   - Identifies truly profitable trades

3. **`FEE_MODEL_CORRECTION.md`**
   - Complete documentation
   - Formula references
   - Real-world examples

## 📋 Next Steps (If You Want to Integrate)

### Option 1: Update Live Dashboard
Modify `live_dashboard.py` to use `ArbCalculator`:
- Calculate net profit for optimal quantity
- Display both gross and net ROI
- Only flag "ARB" when net profitable

### Option 2: Post-Processing Tool
Keep dashboard as-is (shows gross)
Run analyzer separately to identify truly profitable opportunities

### Option 3: Backtesting
Use `reanalyze_arb_opportunities.py` to:
- Understand historical profitability
- Calibrate minimum thresholds
- Validate strategy before live trading

---

**Bottom Line**: Your bot is correctly identifying price inefficiencies (43 opportunities detected), but only about half (22) were actually net profitable after real fees. The calculator now gives you accurate profit projections.

