"""
Kalshi HTTP Polling Fallback

When WebSocket connection fails, fall back to HTTP polling
for orderbook data. Less real-time but still functional.
"""

import asyncio
import time
from typing import Dict, Optional, Callable
from pathlib import Path
import os
import sys

# Add parent dir for imports
sys.path.append(str(Path(__file__).parent.parent))
from src.data_sources.kalshi_client import KalshiClient


class KalshiPollingFallback:
    """HTTP polling fallback when WebSocket unavailable"""
    
    def __init__(self, api_key: str, private_key_path: str, 
                 on_orderbook_update: Optional[Callable] = None):
        """
        Initialize Kalshi polling fallback
        
        Args:
            api_key: Kalshi API key
            private_key_path: Path to private key file
            on_orderbook_update: Callback(ticker, side, orderbook)
        """
        self.api_key = api_key
        self.private_key_path = private_key_path
        self.on_orderbook_update = on_orderbook_update or (lambda *args: None)
        
        # Initialize HTTP client
        self.client = KalshiClient(api_key, private_key_path)
        
        # Polling state
        self.subscribed_tickers = set()
        self.running = False
        self.poll_interval = 2.0  # Poll every 2 seconds
        
        # Statistics
        self.message_count = 0
        self.reconnect_count = 0  # For compatibility with WebSocket interface
        
        print("✓ Kalshi polling fallback initialized (HTTP mode)")
    
    async def start(self):
        """Start polling loop"""
        self.running = True
        
        while self.running:
            try:
                # Poll all subscribed tickers
                for ticker in list(self.subscribed_tickers):
                    await self._poll_orderbook(ticker)
                
                # Wait before next poll
                await asyncio.sleep(self.poll_interval)
                
            except Exception as e:
                print(f"✗ Polling error: {e}")
                await asyncio.sleep(self.poll_interval)
    
    async def _poll_orderbook(self, ticker: str):
        """Poll orderbook for a single ticker"""
        try:
            # Get orderbook via HTTP
            orderbook = await asyncio.to_thread(
                self.client.get_market_orderbook,
                ticker,
                10  # depth
            )
            
            if orderbook:
                # YES side: bids = buy YES, asks = sell YES
                yes_bids = orderbook.get('yes_bids', [])
                yes_asks = orderbook.get('yes_asks', [])
                
                # Convert to (price, size) tuples
                bids = [(price, size) for price, size, count in yes_bids]
                asks = [(price, size) for price, size, count in yes_asks]
                
                # Callback for bids
                if bids:
                    self.on_orderbook_update(ticker, 'bids', bids)
                    self.message_count += 1
                
                # Callback for asks
                if asks:
                    self.on_orderbook_update(ticker, 'asks', asks)
                    self.message_count += 1
                
        except Exception as e:
            # Silently fail - don't spam logs during normal operation
            pass
    
    async def subscribe_orderbook(self, ticker: str):
        """
        Subscribe to orderbook updates for a ticker
        
        Args:
            ticker: Market ticker (e.g., "KXNFLGAME-25JAN04BALPIT-BAL")
        """
        self.subscribed_tickers.add(ticker)
        print(f"  → Polling enabled for {ticker}")
    
    async def stop(self):
        """Stop polling"""
        self.running = False
        print("Stopping Kalshi polling fallback...")
        await asyncio.sleep(0.1)  # Give tasks time to finish
        print("✓ Stopped")
    
    def get_stats(self) -> Dict:
        """Get statistics (for compatibility with WebSocket interface)"""
        return {
            'connected': self.running,  # "Connected" if polling is running
            'subscribed_markets': len(self.subscribed_tickers),
            'messages_received': self.message_count,
            'reconnect_count': 0,  # Not applicable for polling
            'orderbooks_cached': len(self.subscribed_tickers),
            'mode': 'HTTP_POLLING'
        }

