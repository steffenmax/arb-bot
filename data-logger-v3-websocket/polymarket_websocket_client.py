"""
Polymarket WebSocket Client for Real-Time Orderbook Streaming

Maintains persistent WebSocket connection to Polymarket CLOB for L2 orderbook updates.
Handles reconnection, orderbook snapshots, and price updates.

WebSocket endpoint: wss://ws-subscriptions-clob.polymarket.com
"""

import asyncio
import json
import time
import websockets
import ssl
from datetime import datetime
from typing import Dict, List, Tuple, Callable, Optional
import threading
from collections import defaultdict


class PolymarketWebSocketClient:
    """WebSocket client for Polymarket CLOB real-time orderbook streaming"""
    
    def __init__(self, on_orderbook_update: Optional[Callable] = None):
        """
        Initialize Polymarket WebSocket client
        
        Args:
            on_orderbook_update: Callback function(token_id, side, orderbook) when orderbook updates
        """
        self.ws_url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        self.websocket = None
        self.subscribed_tokens = set()
        self.on_orderbook_update = on_orderbook_update or (lambda *args: None)
        
        # Event-driven callback (async) - called after orderbook updates for arb detection
        self.on_update_async: Optional[Callable] = None
        
        # L2 orderbooks: {token_id: {'bids': [(price, size), ...], 'asks': [(price, size), ...]}}
        self.orderbooks = {}
        self.last_update = {}  # {token_id: timestamp}
        self.lock = threading.RLock()
        
        # Token ID to market info mapping (for debugging)
        self.token_info = {}  # {token_id: {'condition_id': ..., 'outcome': ...}}
        
        # Connection state
        self.connected = False
        self.running = False
        self.reconnect_delay = 1.0  # Start with 1 second
        self.max_reconnect_delay = 60.0
        
        # Statistics
        self.message_count = 0
        self.reconnect_count = 0
        
        print("✓ Polymarket WebSocket client initialized")
    
    async def seed_orderbooks_via_rest(self, token_ids: List[str]):
        """
        Pre-populate orderbooks via REST API before WebSocket updates
        Ensures immediate price availability for dashboard
        
        Args:
            token_ids: List of token ID strings to fetch
        """
        import aiohttp
        import ssl
        
        print(f"\n🌱 Seeding Polymarket orderbooks via REST for {len(token_ids)} tokens...")
        
        seeded_count = 0
        empty_count = 0
        error_count = 0
        
        # Create SSL context that doesn't verify certs (for macOS compatibility)
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        
        # Use aiohttp for async REST calls
        async with aiohttp.ClientSession(connector=connector) as session:
            for token_id in token_ids:
                token_str = str(token_id)  # Ensure string
                
                try:
                    url = f"https://clob.polymarket.com/book?token_id={token_str}"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                        if response.status != 200:
                            error_count += 1
                            continue
                        
                        data = await response.json()
                        bids_raw = data.get('bids', [])
                        asks_raw = data.get('asks', [])
                        
                        # Parse and normalize
                        bids = []
                        asks = []
                        
                        for bid in bids_raw:
                            if isinstance(bid, dict):
                                price = float(bid.get('price', 0))
                                size = float(bid.get('size', 0))
                                if price > 0 and size > 0:
                                    bids.append((price, size))
                        
                        for ask in asks_raw:
                            if isinstance(ask, dict):
                                price = float(ask.get('price', 0))
                                size = float(ask.get('size', 0))
                                if price > 0 and size > 0:
                                    asks.append((price, size))
                        
                        # Sort
                        bids.sort(reverse=True, key=lambda x: x[0])
                        asks.sort(key=lambda x: x[0])
                        
                        # Store in orderbooks
                        with self.lock:
                            self.orderbooks[token_str] = {
                                'bids': bids,
                                'asks': asks
                            }
                            self.last_update[token_str] = time.time()
                        
                        if bids or asks:
                            best_bid = bids[0][0] if bids else None
                            best_ask = asks[0][0] if asks else None
                            print(f"  ✓ SEEDED {token_str[:20]}... bid=${best_bid} ask=${best_ask}")
                            seeded_count += 1
                            
                            # CRITICAL: Notify callback so orderbook_manager gets the data
                            self.on_orderbook_update(token_str, 'both', {
                                'bids': bids,
                                'asks': asks
                            })
                        else:
                            empty_count += 1
                
                except asyncio.TimeoutError:
                    print(f"  ✗ Timeout fetching {token_str[:20]}...")
                    error_count += 1
                except Exception as e:
                    print(f"  ✗ Error fetching {token_str[:20]}...: {e}")
                    error_count += 1
        
        print(f"✓ Seeding complete: {seeded_count} valid, {empty_count} empty, {error_count} errors")
    
    async def refresh_orderbooks_via_rest(self, token_ids: List[str] = None, quiet: bool = True):
        """
        Refresh orderbooks via REST to update timestamps even if prices unchanged.
        This prevents valid-but-inactive markets from being marked stale.
        
        Args:
            token_ids: List of token IDs to refresh. If None, refreshes all subscribed tokens.
            quiet: If True, minimal output (for background refresh)
        """
        import aiohttp
        import ssl
        
        # Use subscribed tokens if not specified
        if token_ids is None:
            token_ids = list(self.subscribed_tokens)
        
        if not token_ids:
            return 0
        
        if not quiet:
            print(f"🔄 Refreshing {len(token_ids)} Polymarket orderbooks via REST...")
        
        refreshed_count = 0
        
        # Create SSL context
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            for token_id in token_ids:
                token_str = str(token_id)
                
                try:
                    url = f"https://clob.polymarket.com/book?token_id={token_str}"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                        if response.status != 200:
                            continue
                        
                        data = await response.json()
                        bids_raw = data.get('bids', [])
                        asks_raw = data.get('asks', [])
                        
                        # Parse
                        bids = [(float(b['price']), float(b['size'])) for b in bids_raw 
                                if isinstance(b, dict) and float(b.get('price', 0)) > 0 and float(b.get('size', 0)) > 0]
                        asks = [(float(a['price']), float(a['size'])) for a in asks_raw 
                                if isinstance(a, dict) and float(a.get('price', 0)) > 0 and float(a.get('size', 0)) > 0]
                        
                        bids.sort(reverse=True, key=lambda x: x[0])
                        asks.sort(key=lambda x: x[0])
                        
                        # Update orderbook and CRITICALLY update last_update timestamp
                        with self.lock:
                            self.orderbooks[token_str] = {'bids': bids, 'asks': asks}
                            self.last_update[token_str] = time.time()  # <-- Refreshes staleness
                        
                        if bids or asks:
                            refreshed_count += 1
                            # Notify callback
                            self.on_orderbook_update(token_str, 'both', {'bids': bids, 'asks': asks})
                
                except Exception:
                    pass  # Silent failure for background refresh
        
        if not quiet:
            print(f"✓ Refreshed {refreshed_count}/{len(token_ids)} Polymarket orderbooks")
        
        return refreshed_count
    
    async def connect(self):
        """Establish WebSocket connection"""
        try:
            print(f"Connecting to Polymarket WebSocket: {self.ws_url}")
            
            # Create SSL context that doesn't verify certificates (for development)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            self.websocket = await websockets.connect(
                self.ws_url,
                ping_interval=None,  # We'll handle PING manually
                ping_timeout=10,
                ssl=ssl_context
            )
            
            self.connected = True
            self.reconnect_delay = 1.0  # Reset delay on successful connection
            print("✓ Connected to Polymarket WebSocket")
            
            # CRITICAL: Send initial subscription with all token IDs
            # Polymarket requires: {"assets_ids": [...], "type": "market"}
            if self.subscribed_tokens:
                await self._send_initial_subscription()
            
            return True
            
        except Exception as e:
            print(f"✗ Failed to connect to Polymarket WebSocket: {e}")
            self.connected = False
            return False
    
    async def _send_initial_subscription(self):
        """Send initial subscription for all tokens (Polymarket format)"""
        try:
            # Polymarket market channel subscription format
            subscribe_msg = {
                "assets_ids": list(self.subscribed_tokens),
                "type": "market"
            }
            
            await self.websocket.send(json.dumps(subscribe_msg))
            print(f"  ✓ [Polymarket] Sent initial subscription for {len(self.subscribed_tokens)} tokens")
            
        except Exception as e:
            print(f"✗ Failed to send initial subscription: {e}")
    
    async def _resubscribe_all(self):
        """Resubscribe to all previously subscribed tokens after reconnection"""
        print(f"Resubscribing to {len(self.subscribed_tokens)} markets...")
        await self._send_initial_subscription()
    
    async def subscribe_orderbook(self, token_id: str, market_info: Optional[Dict] = None):
        """
        Subscribe to orderbook updates for a specific token
        
        Polymarket uses batch subscription on connect, so this just queues the token.
        
        Args:
            token_id: Token ID (e.g., "0x123...")
            market_info: Optional dict with condition_id and outcome for debugging
        """
        outcome = market_info.get('outcome', token_id[:10]) if market_info else token_id[:10]
        
        # Add to subscribed set (will be sent on next connection/reconnection)
        self.subscribed_tokens.add(token_id)
        
        if market_info:
            self.token_info[token_id] = market_info
        
        print(f"  [Polymarket] Sending subscription for: {outcome}")
        print(f"  [Polymarket] Token ID: {token_id}")
        
        # If already connected, send dynamic subscribe
        if self.connected and self.websocket:
            try:
                subscribe_msg = {
                    "assets_ids": [token_id],
                    "operation": "subscribe"
                }
                await self.websocket.send(json.dumps(subscribe_msg))
                print(f"  ✓ Subscription request sent: {outcome}")
            except Exception as e:
                print(f"✗ Failed to send subscribe for {token_id[:10]}: {e}")
        else:
            print(f"  ✓ Subscription request sent: {outcome}")
    
    async def unsubscribe_orderbook(self, token_id: str):
        """Unsubscribe from orderbook updates"""
        if not self.connected:
            return
        
        try:
            unsubscribe_msg = {
                "type": "unsubscribe",
                "channel": "book",
                "market": token_id
            }
            
            await self.websocket.send(json.dumps(unsubscribe_msg))
            self.subscribed_tokens.discard(token_id)
            
            # Remove orderbook data
            with self.lock:
                if token_id in self.orderbooks:
                    del self.orderbooks[token_id]
                if token_id in self.last_update:
                    del self.last_update[token_id]
                if token_id in self.token_info:
                    del self.token_info[token_id]
            
            print(f"  Unsubscribed from: {token_id[:10]}")
            
        except Exception as e:
            print(f"✗ Failed to unsubscribe from {token_id[:10]}: {e}")
    
    async def _handle_message(self, message: str):
        """Handle incoming WebSocket message"""
        try:
            # Handle PONG responses to our PING
            if message == "PONG":
                return
            
            # Try to parse as JSON
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                # Not valid JSON - silently ignore
                return
            
            # CRITICAL: Polymarket sends integers (timestamps/heartbeats)
            # Filter these out IMMEDIATELY before any .get() calls
            if not isinstance(data, (dict, list)):
                return  # Silently ignore non-dict/non-list messages
            
            # Handle list (initial batch of book snapshots)
            if isinstance(data, list):
                for book in data:
                    if isinstance(book, dict):
                        await self._handle_book_update(book)
                return
            
            # From this point forward, data is GUARANTEED to be a dict
            self.message_count += 1
            
            # Extract message type and asset ID
            event_type = data.get('event_type', '')
            asset_id = data.get('asset_id') or data.get('market')
            
            # Route message based on type
            if event_type == 'book':
                await self._handle_book_update(data)
                
            elif event_type == 'price_change':
                # Polymarket sends price_change for incremental updates
                await self._handle_price_change(data)
                
            elif 'bids' in data or 'asks' in data:
                if asset_id:
                    await self._handle_book_update(data)
            
            # Silently ignore other message types (trade, ticker, last_trade_price, etc.)
                    
        except Exception as e:
            import traceback
            print(f"✗ Error handling Polymarket message: {e}")
            print(f"   Message type: {type(message)}, length: {len(str(message))}")
            traceback.print_exc()
    
    async def _handle_book_update(self, data: Dict):
        """Handle orderbook update (snapshot or delta)"""
        # Extract token_id (may be 'asset_id' or 'market')
        token_id = data.get('asset_id') or data.get('market')
        if not token_id:
            return
        
        bids = data.get('bids', [])
        asks = data.get('asks', [])
        
        # Convert to internal format: [(price, size), ...]
        # Polymarket format: [{"price": "0.52", "size": "100"}, ...]
        bid_levels = []
        ask_levels = []
        
        for bid in bids:
            if isinstance(bid, dict):
                price = float(bid.get('price', 0))
                size = float(bid.get('size', 0))
            elif isinstance(bid, (list, tuple)) and len(bid) >= 2:
                price = float(bid[0])
                size = float(bid[1])
            else:
                continue
            
            if price > 0 and size > 0:
                bid_levels.append((price, size))
        
        for ask in asks:
            if isinstance(ask, dict):
                price = float(ask.get('price', 0))
                size = float(ask.get('size', 0))
            elif isinstance(ask, (list, tuple)) and len(ask) >= 2:
                price = float(ask[0])
                size = float(ask[1])
            else:
                continue
            
            if price > 0 and size > 0:
                ask_levels.append((price, size))
        
        # Sort: bids descending (highest first), asks ascending (lowest first)
        bid_levels.sort(reverse=True, key=lambda x: x[0])
        ask_levels.sort(key=lambda x: x[0])
        
        with self.lock:
            self.orderbooks[token_id] = {
                'bids': bid_levels,
                'asks': ask_levels
            }
            self.last_update[token_id] = time.time()
        
        # Notify synchronous callback
        self.on_orderbook_update(token_id, 'both', {
            'bids': bid_levels,
            'asks': ask_levels
        })
        
        # Trigger async callback for event-driven arb detection
        if self.on_update_async:
            try:
                asyncio.create_task(self.on_update_async('polymarket', token_id, self.orderbooks[token_id]))
            except Exception:
                pass  # Don't crash on callback errors
    
    async def _handle_price_change(self, data: Dict):
        """Handle price_change incremental update from Polymarket
        
        Format:
        {
            "event_type": "price_change",
            "asset_id": "...",
            "price": "0.52",
            "side": "BUY",  # BUY = bid, SELL = ask
            "size": "100"   # New total size at this price
        }
        """
        token_id = data.get('asset_id') or data.get('market')
        if not token_id:
            return
        
        price = float(data.get('price', 0))
        size = float(data.get('size', 0))
        side = data.get('side', '').upper()
        
        if price <= 0:
            return
        
        with self.lock:
            if token_id not in self.orderbooks:
                # No orderbook yet - skip
                return
            
            # Map BUY/SELL to bids/asks
            if side == 'BUY':
                levels = self.orderbooks[token_id]['bids']
                key = 'bids'
            elif side == 'SELL':
                levels = self.orderbooks[token_id]['asks']
                key = 'asks'
            else:
                return
            
            # Find and update or remove the level
            found_idx = None
            for i, (p, s) in enumerate(levels):
                if abs(p - price) < 0.0001:  # Fuzzy match
                    found_idx = i
                    break
            
            if size <= 0:
                # Remove level
                if found_idx is not None:
                    del levels[found_idx]
            else:
                if found_idx is not None:
                    # Update existing level
                    levels[found_idx] = (price, size)
                else:
                    # Insert new level
                    levels.append((price, size))
                    # Re-sort
                    if key == 'bids':
                        levels.sort(reverse=True, key=lambda x: x[0])
                    else:
                        levels.sort(key=lambda x: x[0])
            
            self.last_update[token_id] = time.time()
        
        # Notify synchronous callback with updated side
        self.on_orderbook_update(token_id, key, {
            key: self.orderbooks[token_id][key]
        })
        
        # Trigger async callback for event-driven arb detection
        if self.on_update_async:
            try:
                asyncio.create_task(self.on_update_async('polymarket', token_id, self.orderbooks[token_id]))
            except Exception:
                pass  # Don't crash on callback errors
    
    async def _receive_loop(self):
        """Main receive loop for WebSocket messages"""
        while self.running:
            try:
                if not self.connected or not self.websocket:
                    await asyncio.sleep(1)
                    continue
                
                message = await asyncio.wait_for(
                    self.websocket.recv(),
                    timeout=30.0
                )
                
                await self._handle_message(message)
                
            except asyncio.TimeoutError:
                # No message received in 30s - check if connection alive
                if self.connected:
                    try:
                        await self.websocket.ping()
                    except:
                        print("⚠️  WebSocket ping failed - reconnecting...")
                        self.connected = False
                        
            except websockets.exceptions.ConnectionClosed:
                print("⚠️  WebSocket connection closed - reconnecting...")
                self.connected = False
                
            except Exception as e:
                print(f"✗ Error in receive loop: {e}")
                await asyncio.sleep(1)
    
    async def _reconnect_loop(self):
        """Handle automatic reconnection with exponential backoff"""
        while self.running:
            if not self.connected:
                print(f"Attempting reconnection (attempt #{self.reconnect_count + 1})...")
                
                success = await self.connect()
                
                if success:
                    print("✓ Reconnected successfully")
                    self.reconnect_count += 1
                else:
                    # Exponential backoff
                    await asyncio.sleep(self.reconnect_delay)
                    self.reconnect_delay = min(
                        self.reconnect_delay * 2,
                        self.max_reconnect_delay
                    )
            else:
                await asyncio.sleep(5)  # Check connection status every 5s
    
    async def _ping_loop(self):
        """
        Send PING keepalive every 10 seconds
        
        CRITICAL: Polymarket expects the literal string "PING" (not JSON)
        """
        while self.running:
            await asyncio.sleep(10)  # PING every 10 seconds
            
            if self.connected and self.websocket:
                try:
                    # Send literal "PING" string (NOT JSON)
                    await self.websocket.send("PING")
                except Exception as e:
                    # PING failed - connection likely dead
                    print(f"⚠️  PING failed: {e}")
                    self.connected = False
    
    async def start(self):
        """Start WebSocket client (connect and begin receiving)"""
        if self.running:
            print("⚠️  Already running")
            return
        
        self.running = True
        
        # Initial connection
        await self.connect()
        
        # Start receive, reconnect, and PING loops
        receive_task = asyncio.create_task(self._receive_loop())
        reconnect_task = asyncio.create_task(self._reconnect_loop())
        ping_task = asyncio.create_task(self._ping_loop())
        
        print("✓ Polymarket WebSocket client started")
        
        # Wait for tasks
        await asyncio.gather(receive_task, reconnect_task, ping_task)
    
    async def stop(self):
        """Stop WebSocket client"""
        print("Stopping Polymarket WebSocket client...")
        self.running = False
        
        if self.websocket and self.connected:
            try:
                await self.websocket.close()
            except:
                pass
        
        self.connected = False
        print("✓ Stopped")
    
    def get_orderbook(self, token_id: str, side: str = 'both') -> Dict:
        """
        Get current orderbook for a token
        
        Args:
            token_id: Token ID
            side: 'bids', 'asks', or 'both'
        
        Returns:
            Dict with bids/asks as list of (price, size) tuples
        """
        with self.lock:
            if token_id not in self.orderbooks:
                return {'bids': [], 'asks': []}
            
            book = self.orderbooks[token_id]
            
            if side == 'bids':
                return {'bids': book['bids'].copy()}
            elif side == 'asks':
                return {'asks': book['asks'].copy()}
            else:  # 'both'
                return {
                    'bids': book['bids'].copy(),
                    'asks': book['asks'].copy()
                }
    
    def get_staleness_ms(self, token_id: str) -> float:
        """Get milliseconds since last orderbook update"""
        with self.lock:
            if token_id not in self.last_update:
                return float('inf')
            
            return (time.time() - self.last_update[token_id]) * 1000
    
    def get_stats(self) -> Dict:
        """Get client statistics"""
        return {
            'connected': self.connected,
            'subscribed_markets': len(self.subscribed_tokens),
            'messages_received': self.message_count,
            'reconnect_count': self.reconnect_count,
            'orderbooks_cached': len(self.orderbooks)
        }


# Test/Example usage
async def test_client():
    """Test the Polymarket WebSocket client"""
    
    def on_update(token_id, side, orderbook):
        """Callback for orderbook updates"""
        print(f"\n[UPDATE] {token_id[:10]}... - {side}")
        if 'bids' in orderbook and orderbook['bids']:
            print(f"  Best bid: ${orderbook['bids'][0][0]:.4f} x {orderbook['bids'][0][1]:.2f}")
        if 'asks' in orderbook and orderbook['asks']:
            print(f"  Best ask: ${orderbook['asks'][0][0]:.4f} x {orderbook['asks'][0][1]:.2f}")
    
    client = PolymarketWebSocketClient(on_orderbook_update=on_update)
    
    # Start client
    start_task = asyncio.create_task(client.start())
    
    # Wait for connection
    await asyncio.sleep(2)
    
    # Subscribe to a test market (need actual token_id)
    # Example: test_token_id = "0x..."
    # await client.subscribe_orderbook(test_token_id)
    
    print("\nNote: Replace with actual token_id to test")
    print("To get token_ids, use polymarket_client.py get_token_ids_from_slug()")
    
    # Run for 30 seconds
    await asyncio.sleep(30)
    
    # Print stats
    print("\n" + "="*60)
    print("Stats:", client.get_stats())
    print("="*60)
    
    # Stop
    await client.stop()


if __name__ == "__main__":
    asyncio.run(test_client())

