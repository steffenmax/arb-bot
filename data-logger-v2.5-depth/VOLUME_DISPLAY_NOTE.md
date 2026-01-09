# Volume Display - Important Note

## What the "Volume" Column Shows

The volume column displays **Total Market Liquidity** for consistent metrics across both platforms:

### For Both Kalshi and Polymarket:
- **Total Market Liquidity** (in dollars)
- This is the TOTAL depth available in the market across all price levels
- Calculated by summing: (price × size) for all bid and ask levels
- More useful than just top-of-book volume for assessing tradeable depth
- Example: $9,877,682 in liquidity = very liquid market
- Displayed in thousands for readability (e.g., 98.7k)

## Why Not Top-of-Book Volume for Kalshi?

Kalshi's `/markets/{ticker}/orderbook` endpoint returns **cached/stale data**:
- Orderbook shows price of $0.46 (stale)
- Market endpoint shows price of $0.51 (accurate)
- Volume at stale price level is meaningless

The orderbook caching is likely intentional:
- Anti-courtsiding measure implemented in late 2025
- Prevents real-time arbitrage during live events
- Affects all users of the REST API

## Interpreting the Numbers

**High Liquidity (>$1M)**: Very deep market, can trade size
**Medium Liquidity ($100K-$1M)**: Decent depth, watch for slippage on large orders
**Low Liquidity (<$100K)**: Thin market, expect significant slippage

## Future Improvements

To get real-time orderbook data for Kalshi, would need to:
1. Implement WebSocket API connection
2. Subscribe to orderbook updates
3. Maintain live orderbook state
4. Significantly more complex implementation

For now, total market liquidity is the most accurate metric available via REST API.

## Current Status

✅ Prices: Accurate (using `/markets/{ticker}`)
✅ Liquidity: Accurate (total market depth)
❌ Top-of-book volume: Not available due to orderbook caching
⚠️  Orderbook depth: Available but stale (use for general reference only)

---

*Updated: January 6, 2026*

