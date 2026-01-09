"""
Kalshi WebSocket Client for Real-Time Orderbook Streaming

Maintains persistent WebSocket connection to Kalshi for L2 orderbook updates.
Handles reconnection, orderbook snapshots, and delta updates.

WebSocket endpoint: wss://api.elections.kalshi.com/trade-api/ws/v2
"""

import asyncio
import json
import time
import websockets
import ssl
import base64
from datetime import datetime
from typing import Dict, List, Tuple, Callable, Optional
import threading
from collections import defaultdict
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend


class KalshiWebSocketClient:
    """WebSocket client for Kalshi real-time orderbook streaming"""
    
    def __init__(self, api_key: str, private_key_path: str, on_orderbook_update: Optional[Callable] = None):
        """
        Initialize Kalshi WebSocket client
        
        Args:
            api_key: Kalshi API key for authentication
            private_key_path: Path to RSA private key PEM file
            on_orderbook_update: Callback function(ticker, side, orderbook) when orderbook updates
        """
        self.api_key = api_key
        self.ws_url = "wss://api.elections.kalshi.com/trade-api/ws/v2"
        self.websocket = None
        self.subscribed_tickers = set()
        self.on_orderbook_update = on_orderbook_update or (lambda *args: None)
        
        # Event-driven callback (async) - called after orderbook updates for arb detection
        self.on_update_async: Optional[Callable] = None
        
        # Load private key for RSA signing
        private_key_file = Path(private_key_path)
        if not private_key_file.exists():
            raise FileNotFoundError(f"Private key not found: {private_key_path}")
        
        with open(private_key_file, 'rb') as f:
            self.private_key = serialization.load_pem_private_key(
                f.read(),
                password=None,
                backend=default_backend()
            )
        
        # L2 orderbooks: {ticker: {'bids': [(price, size), ...], 'asks': [(price, size), ...]}}
        self.orderbooks = {}
        self.last_update = {}  # {ticker: timestamp}
        self.lock = threading.RLock()
        
        # Connection state
        self.connected = False
        self.running = False
        self.reconnect_delay = 1.0  # Start with 1 second
        self.max_reconnect_delay = 60.0
        
        # Statistics
        self.message_count = 0
        self.reconnect_count = 0
        
        print("✓ Kalshi WebSocket client initialized")
    
    def _sign_message(self, method: str, path: str) -> tuple:
        """Sign WebSocket authentication message using RSA private key
        
        Args:
            method: HTTP method (must be uppercase, e.g. "GET")
            path: Exact path (e.g. "/trade-api/ws/v2")
        
        Returns:
            (timestamp_str, signature_base64)
        """
        # CRITICAL: Timestamp must be in milliseconds
        timestamp = str(int(time.time() * 1000))
        
        # CRITICAL: Message format is exactly: timestamp + method + path
        msg_string = timestamp + method + path
        
        # Debug logging (comment out in production)
        # print(f"  [DEBUG] Signing: timestamp={timestamp}, method={method}, path={path}")
        # print(f"  [DEBUG] Message string: {msg_string}")
        
        signature = self.private_key.sign(
            msg_string.encode('utf-8'),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH
            ),
            hashes.SHA256()
        )
        
        sig_b64 = base64.b64encode(signature).decode('utf-8')
        return timestamp, sig_b64
    
    async def connect(self):
        """Establish WebSocket connection with authentication in handshake"""
        try:
            print(f"Connecting to Kalshi WebSocket: {self.ws_url}")
            
            # Sign the authentication message
            # CRITICAL: Must use exact path "/trade-api/ws/v2" with milliseconds timestamp
            timestamp, signature = self._sign_message("GET", "/trade-api/ws/v2")
            
            # Add authentication headers to WebSocket handshake
            # Kalshi requires these headers on initial connection
            auth_headers = {
                "KALSHI-ACCESS-KEY": self.api_key,
                "KALSHI-ACCESS-SIGNATURE": signature,
                "KALSHI-ACCESS-TIMESTAMP": timestamp
            }
            
            print(f"  → Auth headers prepared (timestamp: {timestamp})")
            
            # Create SSL context
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # Connect with authentication headers in handshake
            self.websocket = await websockets.connect(
                self.ws_url,
                additional_headers=auth_headers,  # MUST be 'additional_headers' not 'extra_headers'
                ping_interval=20,
                ping_timeout=10,
                ssl=ssl_context
            )
            
            self.connected = True
            self.reconnect_delay = 1.0
            print("✓ Connected and authenticated with Kalshi WebSocket")
            
            # Resubscribe to all tickers
            if self.subscribed_tickers:
                await self._resubscribe_all()
            
            return True
            
        except Exception as e:
            print(f"✗ Failed to connect to Kalshi WebSocket: {e}")
            self.connected = False
            return False
    
    async def _resubscribe_all(self):
        """Resubscribe to all previously subscribed tickers after reconnection"""
        tickers = list(self.subscribed_tickers)
        if tickers:
            print(f"Resubscribing to {len(tickers)} markets...")
            await self.subscribe_batch(tickers)
    
    async def subscribe_orderbook(self, ticker: str):
        """
        Subscribe to orderbook updates for a specific market
        
        Args:
            ticker: Market ticker (e.g., "KXNFLGAME-25JAN04BALPIT-BAL")
        """
        if not self.connected:
            print(f"⚠️  Not connected - queuing subscription for {ticker}")
            self.subscribed_tickers.add(ticker)
            return
        
        # Just queue it - we'll send batch subscription
        self.subscribed_tickers.add(ticker)
    
    async def subscribe_batch(self, tickers: list):
        """
        Subscribe to multiple markets at once (more efficient)
        
        Args:
            tickers: List of market tickers to subscribe to
        """
        if not self.connected or not tickers:
            return
        
        try:
            # Correct Kalshi WebSocket format
            subscribe_msg = {
                "id": 1,
                "cmd": "subscribe",
                "params": {
                    "channels": ["orderbook_delta"],
                    "market_tickers": tickers
                }
            }
            
            print(f"  [Kalshi] Batch subscribing to {len(tickers)} markets...")
            await self.websocket.send(json.dumps(subscribe_msg))
            
            for ticker in tickers:
                self.subscribed_tickers.add(ticker)
            
            print(f"  ✓ Batch subscription sent for {len(tickers)} markets")
            
        except Exception as e:
            print(f"✗ Failed to batch subscribe: {e}")
    
    async def unsubscribe_orderbook(self, ticker: str):
        """Unsubscribe from orderbook updates"""
        if not self.connected:
            return
        
        try:
            unsubscribe_msg = {
                "type": "unsubscribe",
                "channel": "orderbook",
                "market_ticker": ticker
            }
            
            await self.websocket.send(json.dumps(unsubscribe_msg))
            self.subscribed_tickers.discard(ticker)
            
            # Remove orderbook data
            with self.lock:
                if ticker in self.orderbooks:
                    del self.orderbooks[ticker]
                if ticker in self.last_update:
                    del self.last_update[ticker]
            
            print(f"  Unsubscribed from: {ticker}")
            
        except Exception as e:
            print(f"✗ Failed to unsubscribe from {ticker}: {e}")
    
    async def refresh_orderbooks_via_rest(self, tickers: list = None, quiet: bool = True):
        """
        Refresh orderbooks via REST to update timestamps even if prices unchanged.
        This prevents valid-but-inactive markets from being marked stale.
        
        Args:
            tickers: List of tickers to refresh. If None, refreshes all subscribed tickers.
            quiet: If True, minimal output (for background refresh)
        """
        import aiohttp
        
        # Use subscribed tickers if not specified
        if tickers is None:
            tickers = list(self.subscribed_tickers)
        
        if not tickers:
            return 0
        
        if not quiet:
            print(f"🔄 Refreshing {len(tickers)} Kalshi orderbooks via REST...")
        
        refreshed_count = 0
        
        # Create SSL context
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            for ticker in tickers:
                try:
                    url = f"https://api.elections.kalshi.com/trade-api/v2/markets/{ticker}/orderbook"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status != 200:
                            continue
                        
                        data = await resp.json()
                        orderbook = data.get('orderbook', data)
                        
                        # Parse yes/no orderbook levels
                        yes_levels = orderbook.get('yes', [])
                        no_levels = orderbook.get('no', [])
                        
                        # Convert to bids/asks:
                        # - 'yes' bids = bids (someone wants to buy YES)
                        # - 'no' bids = asks (buy NO at X = sell YES at 1-X)
                        bids = []
                        asks = []
                        
                        if yes_levels:
                            for level in yes_levels:
                                if isinstance(level, list) and len(level) >= 2:
                                    price_cents, qty = level[0], level[1]
                                    price = float(price_cents) / 100.0
                                    bids.append((price, float(qty)))
                        
                        if no_levels:
                            for level in no_levels:
                                if isinstance(level, list) and len(level) >= 2:
                                    price_cents, qty = level[0], level[1]
                                    # Convert NO price to YES ask price
                                    ask_price = 1.0 - (float(price_cents) / 100.0)
                                    asks.append((ask_price, float(qty)))
                        
                        bids.sort(reverse=True, key=lambda x: x[0])
                        asks.sort(key=lambda x: x[0])
                        
                        # Update orderbook and CRITICALLY update last_update timestamp
                        with self.lock:
                            self.orderbooks[ticker] = {'bids': bids, 'asks': asks}
                            self.last_update[ticker] = time.time()  # <-- Refreshes staleness
                        
                        if bids or asks:
                            refreshed_count += 1
                            # Notify callback
                            self.on_orderbook_update(ticker, 'both', {'bids': bids, 'asks': asks})
                
                except Exception:
                    pass  # Silent failure for background refresh
        
        if not quiet:
            print(f"✓ Refreshed {refreshed_count}/{len(tickers)} Kalshi orderbooks")
        
        return refreshed_count
    
    async def _handle_message(self, message: str):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)
            
            # CRITICAL: Kalshi uses top-level "type" field (not nested "msg")
            # Message structure: {"type": "orderbook_snapshot", "msg": {...payload...}}
            msg_type = data.get('type', '')
            
            self.message_count += 1
            
            # 1) Housekeeping messages
            if msg_type in ('subscribed', 'unsubscribed'):
                # Subscription confirmations - silent success
                return
                
            if msg_type == 'error':
                # Log full error payload for debugging
                print(f"✗ [Kalshi ERROR]: {data}")
                return
            
            # 2) Orderbook messages    
            if msg_type == 'orderbook_snapshot':
                # Full orderbook snapshot
                await self._handle_snapshot(data)
                return
                
            elif msg_type == 'orderbook_delta':
                # Incremental orderbook update
                await self._handle_delta(data)
                return
                
            # 3) Unknown message type
            else:
                # Only log first few unknown types to avoid spam
                if self.message_count <= 5:
                    print(f"  [Kalshi] Unhandled message type: {msg_type}")
                    
        except json.JSONDecodeError:
            print(f"✗ Failed to parse message: {message[:100]}")
        except Exception as e:
            print(f"✗ Error handling message: {e}")
    
    async def _handle_snapshot(self, data: Dict):
        """Handle full orderbook snapshot
        
        Kalshi format:
        {
          'type': 'orderbook_snapshot',
          'sid': 1,
          'seq': 1,
          'msg': {
            'market_ticker': 'KXNBAGAME-26JAN06CLEIND-CLE',
            'yes': [[price_cents, quantity], ...],
            'no': [[price_cents, quantity], ...]
          }
        }
        """
        # Extract actual message payload
        msg = data.get('msg', data)
        ticker = msg.get('market_ticker')
        if not ticker:
            return
        
        # Use the convenient yes_dollars/no_dollars format (already in decimal)
        yes_levels = msg.get('yes_dollars', [])
        no_levels = msg.get('no_dollars', [])
        
        # If dollars format not available, use cents format
        if not yes_levels and 'yes' in msg:
            yes_cents = msg.get('yes', [])
            yes_levels = [[float(level[0])/100.0, level[1]] for level in yes_cents if len(level) >= 2]
        
        if not no_levels and 'no' in msg:
            no_cents = msg.get('no', [])
            no_levels = [[float(level[0])/100.0, level[1]] for level in no_cents if len(level) >= 2]
        
        # Convert to (price, size) tuples
        # YES levels are bids (buying YES)
        # Round prices to avoid floating point precision issues
        bids = [(round(float(level[0]), 4), float(level[1])) for level in yes_levels if len(level) >= 2]
        
        # NO levels are bids for NO contracts
        # To sell YES = to buy NO, so we need to invert NO bid prices to get YES ask prices
        # If someone bids $0.51 for NO, that's equivalent to offering YES at $(1.00 - 0.51) = $0.49
        no_bids = [(round(float(level[0]), 4), float(level[1])) for level in no_levels if len(level) >= 2]
        
        # Convert NO bids to YES asks by inverting prices
        # Round to avoid floating point precision issues
        asks = [(round(1.0 - price, 4), size) for price, size in no_bids]
        
        # Sort: bids descending (best first), asks ascending (best first)
        bids.sort(reverse=True, key=lambda x: x[0])
        asks.sort(key=lambda x: x[0])
        
        
        with self.lock:
            self.orderbooks[ticker] = {
                'bids': bids,
                'asks': asks
            }
            self.last_update[ticker] = time.time()
        
        # Print confirmation with best prices if available
        if bids and asks:
            print(f"  ✓ [Kalshi] {ticker}: {len(bids)} bids / {len(asks)} asks | Best: ${bids[0][0]:.2f} × {bids[0][1]} / ${asks[0][0]:.2f} × {asks[0][1]}")
        else:
            print(f"  ✓ [Kalshi] {ticker}: {len(bids)} bids / {len(asks)} asks")
        
        # Notify synchronous callback (for orderbook_manager)
        self.on_orderbook_update(ticker, 'both', {
            'bids': bids,
            'asks': asks
        })
        
        # Trigger async callback for event-driven arb detection
        if self.on_update_async:
            try:
                asyncio.create_task(self.on_update_async('kalshi', ticker, self.orderbooks[ticker]))
            except Exception:
                pass  # Don't crash on callback errors
    
    async def _handle_delta(self, data: Dict):
        """Handle incremental orderbook update
        
        Kalshi delta format:
        {
          'type': 'orderbook_delta',
          'sid': 1,
          'seq': 123,
          'msg': {
            'market_ticker': 'KXNBAGAME-...',
            'price': 55,           # Price in cents
            'delta': 100,          # Size CHANGE (positive = add, negative = remove)
            'side': 'yes'          # 'yes' or 'no'
          }
        }
        
        CRITICAL: 
        - 'delta' is a SIZE CHANGE, not the new total!
        - For side='no', price must be converted: YES ask = 1.0 - NO price
        """
        # Extract actual message payload  
        msg = data.get('msg', data)
        
        # Ensure msg is a dict
        if not isinstance(msg, dict):
            return
        
        ticker = msg.get('market_ticker')
        if not ticker or ticker not in self.orderbooks:
            # If we don't have the snapshot yet, ignore delta
            return
        
        # Extract side/price/delta directly from msg
        side = msg.get('side', '').lower()  # 'yes' or 'no'
        raw_price = float(msg.get('price', 0))
        
        
        # Price is in cents - convert to dollars
        # FIX: Kalshi sends prices as integers 1-99 for cents, so ANY value >= 1 means cents
        if raw_price >= 1:  # >= 1 means it's in cents (1 cent = $0.01, 99 cents = $0.99)
            raw_price = raw_price / 100.0
        
        # 'delta' is the size CHANGE (can be positive or negative!)
        delta_value = msg.get('delta', 0)
        if isinstance(delta_value, dict):
            # Fallback if delta is actually nested (shouldn't happen)
            delta_change = float(delta_value.get('size', 0))
        else:
            delta_change = float(delta_value)
        
        with self.lock:
            # Map yes/no to bids/asks with proper price conversion
            if side == 'yes':
                # YES bids: price stays the same
                levels = self.orderbooks[ticker]['bids']
                key = 'bids'
                price = round(raw_price, 4)  # Round for consistency
            elif side == 'no':
                # NO bids convert to YES asks: ask_price = 1.0 - no_price
                levels = self.orderbooks[ticker]['asks']
                key = 'asks'
                # Round to avoid floating point precision issues (e.g., 1.0-0.78 = 0.21999...)
                price = round(1.0 - raw_price, 4)
            else:
                return
            
            # Find existing level at this price
            found_idx = None
            for i, (p, s) in enumerate(levels):
                if abs(p - price) < 0.001:  # Fuzzy price match
                    found_idx = i
                    break
            
            if found_idx is not None:
                # Update existing level: ADD delta to current size
                old_price, old_size = levels[found_idx]
                new_size = old_size + delta_change
                
                if new_size <= 0:
                    # Remove level if size drops to 0 or below
                    del levels[found_idx]
                else:
                    levels[found_idx] = (price, new_size)
            else:
                # New level - only add if delta is positive
                if delta_change > 0:
                    levels.append((price, delta_change))
                    # Re-sort after insertion
                    if key == 'bids':
                        levels.sort(reverse=True, key=lambda x: x[0])
                    else:
                        levels.sort(key=lambda x: x[0])
            
            self.last_update[ticker] = time.time()
        
        # Notify synchronous callback
        self.on_orderbook_update(ticker, key, {
            key: self.orderbooks[ticker][key]
        })
        
        # Trigger async callback for event-driven arb detection
        if self.on_update_async:
            try:
                asyncio.create_task(self.on_update_async('kalshi', ticker, self.orderbooks[ticker]))
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
    
    async def start(self):
        """Start WebSocket client (connect and begin receiving)"""
        if self.running:
            print("⚠️  Already running")
            return
        
        self.running = True
        
        # Initial connection
        await self.connect()
        
        # Start receive and reconnect loops
        receive_task = asyncio.create_task(self._receive_loop())
        reconnect_task = asyncio.create_task(self._reconnect_loop())
        
        print("✓ Kalshi WebSocket client started")
        
        # Wait for tasks
        await asyncio.gather(receive_task, reconnect_task)
    
    async def stop(self):
        """Stop WebSocket client"""
        print("Stopping Kalshi WebSocket client...")
        self.running = False
        
        if self.websocket and self.connected:
            try:
                await self.websocket.close()
            except:
                pass
        
        self.connected = False
        print("✓ Stopped")
    
    def get_orderbook(self, ticker: str, side: str = 'both') -> Dict:
        """
        Get current orderbook for a ticker
        
        Args:
            ticker: Market ticker
            side: 'bids', 'asks', or 'both'
        
        Returns:
            Dict with bids/asks as list of (price, size) tuples
        """
        with self.lock:
            if ticker not in self.orderbooks:
                return {'bids': [], 'asks': []}
            
            book = self.orderbooks[ticker]
            
            if side == 'bids':
                return {'bids': book['bids'].copy()}
            elif side == 'asks':
                return {'asks': book['asks'].copy()}
            else:  # 'both'
                return {
                    'bids': book['bids'].copy(),
                    'asks': book['asks'].copy()
                }
    
    def get_staleness_ms(self, ticker: str) -> float:
        """Get milliseconds since last orderbook update"""
        with self.lock:
            if ticker not in self.last_update:
                return float('inf')
            
            return (time.time() - self.last_update[ticker]) * 1000
    
    def get_stats(self) -> Dict:
        """Get client statistics"""
        return {
            'connected': self.connected,
            'subscribed_markets': len(self.subscribed_tickers),
            'messages_received': self.message_count,
            'reconnect_count': self.reconnect_count,
            'orderbooks_cached': len(self.orderbooks)
        }


# Test/Example usage
async def test_client():
    """Test the Kalshi WebSocket client"""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    api_key = os.getenv('KALSHI_API_KEY')
    
    if not api_key:
        print("Error: KALSHI_API_KEY not found in environment")
        return
    
    def on_update(ticker, side, orderbook):
        """Callback for orderbook updates"""
        print(f"\n[UPDATE] {ticker} - {side}")
        if 'bids' in orderbook and orderbook['bids']:
            print(f"  Best bid: ${orderbook['bids'][0][0]:.4f} x {orderbook['bids'][0][1]}")
        if 'asks' in orderbook and orderbook['asks']:
            print(f"  Best ask: ${orderbook['asks'][0][0]:.4f} x {orderbook['asks'][0][1]}")
    
    client = KalshiWebSocketClient(api_key, on_orderbook_update=on_update)
    
    # Start client
    start_task = asyncio.create_task(client.start())
    
    # Wait for connection
    await asyncio.sleep(2)
    
    # Subscribe to a test market
    test_ticker = "KXNFLGAME-25JAN04BALPIT-BAL"
    await client.subscribe_orderbook(test_ticker)
    
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

