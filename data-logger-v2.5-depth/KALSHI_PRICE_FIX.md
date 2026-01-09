# Kalshi Price Issue - CRITICAL FIX NEEDED

## Problem Identified

The data logger is using the **wrong Kalshi API endpoint** for prices:

### Current (WRONG):
- Endpoint: `/markets/{ticker}/orderbook`
- Returns: **Stale limit orders** from the orderbook
- Example: Shows Chicago at $0.37 when actual market price is $0.51

### Correct:  
- Endpoint: `/markets/{ticker}`
- Returns: **Current best bid/ask** (NBBO - National Best Bid/Offer)
- Example: Shows Chicago at $0.51 (matches Kalshi website)

## Verification

```bash
# Test showing the difference:
python3 -c "
from kalshi_client import KalshiClient
import json

with open('config/settings.json') as f:
    config = json.load(f)

kalshi = KalshiClient(config['kalshi']['api_key'], config['kalshi']['private_key_path'])

ticker = 'KXNFLGAME-26JAN10GBCHI-CHI'

# Wrong method (orderbook - returns 0.37)
orderbook = kalshi.get_market_orderbook(ticker)
print(f'Orderbook YES ask: {orderbook[\"yes_asks\"][0][0]}')

# Correct method (market - returns 0.51)  
market = kalshi.get_market(ticker)
print(f'Market YES ask: {market[\"yes_ask\"]}')

kalshi.close()
"
```

## Fix Required

Change `data_logger_depth.py` line 129 from:
```python
executor.submit(self.kalshi.get_market_orderbook, ticker, depth=10)
```

To:
```python
executor.submit(self.kalshi.get_market, ticker)
```

Or better yet, fetch BOTH:
1. Use `get_market()` for top-of-book snapshot prices
2. Use `get_market_orderbook()` for depth analysis

## Impact

- Dashboard will show correct prices matching Kalshi website
- Arbitrage calculations will be accurate
- Historical price data will be correct

## Status

**NEEDS FIX** - Data logger must be updated before it can collect accurate price data.

---

*Discovered: January 6, 2026 02:06 UTC*

