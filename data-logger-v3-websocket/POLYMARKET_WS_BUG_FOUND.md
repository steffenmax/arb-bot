## Polymarket WebSocket Issue - ROOT CAUSE IDENTIFIED

### The Bug:
The Polymarket WebSocket client is **trying to subscribe before tokens are queued**, resulting in an empty initial subscription.

### Current Flow (BROKEN):
1. `polymarket_ws.connect()` → sends `{"assets_ids": [], "type": "market"}` ❌
2. Bot calls `subscribe_orderbook(token1)` → queues token1, sends individual subscribe
3. Bot calls `subscribe_orderbook(token2)` → queues token2, sends individual subscribe
4. **Polymarket ignores all individual subscribes** because no initial batch was sent

### Correct Flow (per Polymarket docs):
1. Bot queues all tokens first
2. `polymarket_ws.connect()` → sends `{"assets_ids": [all tokens], "type": "market"}` ✅
3. Polymarket sends `event_type: "book"` snapshots for each token
4. Individual `{"assets_ids": [token], "operation": "subscribe"}` work for dynamic adds

### Fix Options:

**Option A: Subscribe before connecting** (quickest)
```python
# In arb_bot_main.py _subscribe_to_markets()
# Queue all Polymarket tokens BEFORE starting WebSocket
for market in self.markets:
    poly_tokens = market.get('poly_token_ids', {})
    for outcome, token_id in poly_tokens.items():
        # This just queues, doesn't send yet
        self.polymarket_ws.subscribed_tokens.add(token_id)

# NOW start WebSocket (will send batch subscription)
await self.polymarket_ws.connect()
```

**Option B: Add explicit batch_subscribe() method**
```python
# After queuing all tokens, call:
await self.polymarket_ws.send_batch_subscription()
```

### Recommendation:
Use **Option A** - it's cleaner and matches the intended design where all subscriptions are known upfront.


