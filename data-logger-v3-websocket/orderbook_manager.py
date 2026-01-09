"""
Unified Orderbook Manager

Central registry for L2 orderbooks from both Kalshi and Polymarket.
Provides thread-safe access to current orderbook state and staleness tracking.
"""

import threading
import time
import json
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from datetime import datetime
from pathlib import Path


class OrderbookManager:
    """
    Unified manager for orderbooks from multiple venues
    
    Maintains current L2 orderbook state for all tracked markets.
    Thread-safe for concurrent access from WebSocket clients and execution engine.
    """
    
    def __init__(self):
        """Initialize orderbook manager"""
        # Orderbooks: {(event_id, platform, side): [(price, size), ...]}
        self.orderbooks = {}
        
        # Last update timestamp: {(event_id, platform): timestamp}
        self.last_update = {}
        
        # Market metadata: {event_id: {'kalshi_ticker': ..., 'poly_token_ids': {...}}}
        self.market_metadata = {}
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Statistics
        self.update_count = defaultdict(int)  # {(event_id, platform): count}
        
        print("✓ Orderbook manager initialized")
    
    def register_market(self, event_id: str, metadata: Dict):
        """
        Register a market with its platform-specific identifiers
        
        Args:
            event_id: Universal event identifier
            metadata: Dict containing:
                - kalshi_ticker: Kalshi market ticker
                - poly_token_ids: Dict of {outcome: token_id}
                - teams: Dict of team information
        """
        with self.lock:
            self.market_metadata[event_id] = metadata
    
    def update_orderbook(self, event_id: str, platform: str, side: str, 
                        levels: List[Tuple[float, float]]):
        """
        Update orderbook for a specific market/platform/side
        
        Args:
            event_id: Universal event identifier
            platform: 'kalshi' or 'polymarket'
            side: 'bids' or 'asks'
            levels: List of (price, size) tuples, sorted appropriately
        """
        with self.lock:
            key = (event_id, platform, side)
            self.orderbooks[key] = levels.copy()
            self.last_update[(event_id, platform)] = time.time()
            self.update_count[key] += 1
    
    def update_orderbook_both_sides(self, event_id: str, platform: str,
                                    bids: List[Tuple[float, float]],
                                    asks: List[Tuple[float, float]]):
        """
        Update both bid and ask sides atomically
        
        Args:
            event_id: Universal event identifier
            platform: 'kalshi' or 'polymarket'
            bids: List of (price, size) tuples, sorted descending
            asks: List of (price, size) tuples, sorted ascending
        """
        with self.lock:
            timestamp = time.time()
            
            self.orderbooks[(event_id, platform, 'bids')] = bids.copy()
            self.orderbooks[(event_id, platform, 'asks')] = asks.copy()
            self.last_update[(event_id, platform)] = timestamp
            
            self.update_count[(event_id, platform, 'bids')] += 1
            self.update_count[(event_id, platform, 'asks')] += 1
    
    def get_orderbook(self, event_id: str, platform: str, 
                     side: str = 'both') -> Dict[str, List[Tuple[float, float]]]:
        """
        Get current orderbook for a market
        
        Args:
            event_id: Universal event identifier
            platform: 'kalshi' or 'polymarket'
            side: 'bids', 'asks', or 'both'
        
        Returns:
            Dict with 'bids' and/or 'asks' keys containing list of (price, size) tuples
        """
        with self.lock:
            if side == 'both':
                return {
                    'bids': self.orderbooks.get((event_id, platform, 'bids'), []).copy(),
                    'asks': self.orderbooks.get((event_id, platform, 'asks'), []).copy()
                }
            elif side in ['bids', 'asks']:
                return {
                    side: self.orderbooks.get((event_id, platform, side), []).copy()
                }
            else:
                return {'bids': [], 'asks': []}
    
    def get_best_bid_ask(self, event_id: str, platform: str) -> Tuple[Optional[float], Optional[float]]:
        """
        Get best bid and ask prices for a market
        
        Args:
            event_id: Universal event identifier
            platform: 'kalshi' or 'polymarket'
        
        Returns:
            Tuple of (best_bid, best_ask) or (None, None) if not available
        """
        with self.lock:
            bids = self.orderbooks.get((event_id, platform, 'bids'), [])
            asks = self.orderbooks.get((event_id, platform, 'asks'), [])
            
            best_bid = bids[0][0] if bids else None
            best_ask = asks[0][0] if asks else None
            
            return best_bid, best_ask
    
    def get_best_bid_ask_size(self, event_id: str, platform: str) -> Dict:
        """
        Get best bid/ask with sizes
        
        Returns:
            Dict with best_bid, best_ask, bid_size, ask_size
        """
        with self.lock:
            bids = self.orderbooks.get((event_id, platform, 'bids'), [])
            asks = self.orderbooks.get((event_id, platform, 'asks'), [])
            
            return {
                'best_bid': bids[0][0] if bids else None,
                'best_ask': asks[0][0] if asks else None,
                'bid_size': bids[0][1] if bids else 0,
                'ask_size': asks[0][1] if asks else 0
            }
    
    def get_depth(self, event_id: str, platform: str, side: str, 
                  num_levels: int = 5) -> List[Tuple[float, float]]:
        """
        Get orderbook depth for specified number of levels
        
        Args:
            event_id: Universal event identifier
            platform: 'kalshi' or 'polymarket'
            side: 'bids' or 'asks'
            num_levels: Number of levels to return
        
        Returns:
            List of (price, size) tuples, up to num_levels
        """
        with self.lock:
            levels = self.orderbooks.get((event_id, platform, side), [])
            return levels[:num_levels]
    
    def get_staleness_ms(self, event_id: str, platform: str) -> float:
        """
        Get milliseconds since last orderbook update
        
        Args:
            event_id: Universal event identifier
            platform: 'kalshi' or 'polymarket'
        
        Returns:
            Milliseconds since last update, or inf if never updated
        """
        with self.lock:
            key = (event_id, platform)
            if key not in self.last_update:
                return float('inf')
            
            return (time.time() - self.last_update[key]) * 1000
    
    def is_stale(self, event_id: str, platform: str, max_age_ms: float = 5000) -> bool:
        """
        Check if orderbook is stale
        
        Args:
            event_id: Universal event identifier
            platform: 'kalshi' or 'polymarket'
            max_age_ms: Maximum age in milliseconds before considered stale
        
        Returns:
            True if orderbook is stale or doesn't exist
        """
        return self.get_staleness_ms(event_id, platform) > max_age_ms
    
    def get_spread(self, event_id: str, platform: str) -> Optional[float]:
        """
        Get bid-ask spread for a market
        
        Returns:
            Spread in price units, or None if not available
        """
        best_bid, best_ask = self.get_best_bid_ask(event_id, platform)
        
        if best_bid is not None and best_ask is not None:
            return best_ask - best_bid
        
        return None
    
    def get_mid_price(self, event_id: str, platform: str) -> Optional[float]:
        """
        Get mid-market price
        
        Returns:
            Mid price (best_bid + best_ask) / 2, or None if not available
        """
        best_bid, best_ask = self.get_best_bid_ask(event_id, platform)
        
        if best_bid is not None and best_ask is not None:
            return (best_bid + best_ask) / 2
        
        return None
    
    def get_total_liquidity(self, event_id: str, platform: str, side: str,
                           num_levels: int = 10) -> float:
        """
        Calculate total liquidity (in size) for top N levels
        
        Args:
            event_id: Universal event identifier
            platform: 'kalshi' or 'polymarket'
            side: 'bids' or 'asks'
            num_levels: Number of levels to sum
        
        Returns:
            Total size across levels
        """
        with self.lock:
            levels = self.orderbooks.get((event_id, platform, side), [])
            return sum(size for _, size in levels[:num_levels])
    
    def get_all_markets(self) -> List[str]:
        """Get list of all registered market event_ids"""
        with self.lock:
            return list(self.market_metadata.keys())
    
    def get_market_metadata(self, event_id: str) -> Optional[Dict]:
        """Get metadata for a specific market"""
        with self.lock:
            return self.market_metadata.get(event_id)
    
    def has_orderbook(self, event_id: str, platform: str) -> bool:
        """Check if orderbook exists for a market"""
        with self.lock:
            return (event_id, platform, 'bids') in self.orderbooks or \
                   (event_id, platform, 'asks') in self.orderbooks
    
    def get_stats(self) -> Dict:
        """Get statistics about orderbook manager state"""
        with self.lock:
            total_updates = sum(self.update_count.values())
            
            # Count markets with data
            markets_with_data = set()
            for (event_id, platform, side) in self.orderbooks.keys():
                markets_with_data.add((event_id, platform))
            
            return {
                'registered_markets': len(self.market_metadata),
                'markets_with_orderbooks': len(markets_with_data),
                'total_orderbook_keys': len(self.orderbooks),
                'total_updates': total_updates,
                'platforms': {
                    'kalshi': len([k for k in markets_with_data if k[1] == 'kalshi']),
                    'polymarket': len([k for k in markets_with_data if k[1] == 'polymarket'])
                }
            }
    
    def export_to_json(self, output_path: str = "data/orderbooks.json"):
        """
        Export current orderbook state to JSON for dashboard consumption
        
        Args:
            output_path: Path to write JSON file
        """
        with self.lock:
            export_data = {}
            
            # Group by (event_id, platform)
            market_pairs = set((eid, plat) for eid, plat, side in self.orderbooks.keys())
            
            for event_id, platform in market_pairs:
                key = f"{event_id}:{platform}"
                
                # Get bids and asks
                bids = self.orderbooks.get((event_id, platform, 'bids'), [])
                asks = self.orderbooks.get((event_id, platform, 'asks'), [])
                
                # Get best bid/ask
                best_bid = {'price': bids[0][0], 'size': bids[0][1]} if bids else None
                best_ask = {'price': asks[0][0], 'size': asks[0][1]} if asks else None
                
                # Calculate staleness
                last_update_ts = self.last_update.get((event_id, platform), 0)
                staleness_ms = int((time.time() - last_update_ts) * 1000) if last_update_ts else 99999
                
                export_data[key] = {
                    'event_id': event_id,
                    'platform': platform,
                    'best_bid': best_bid,
                    'best_ask': best_ask,
                    'bid_depth': len(bids),
                    'ask_depth': len(asks),
                    'staleness_ms': staleness_ms,
                    'last_update': datetime.fromtimestamp(last_update_ts).isoformat() if last_update_ts else None
                }
            
            # Write to file
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2)
    
    def clear_orderbook(self, event_id: str, platform: Optional[str] = None):
        """
        Clear orderbook data for a market
        
        Args:
            event_id: Universal event identifier
            platform: Specific platform to clear, or None for all platforms
        """
        with self.lock:
            if platform:
                # Clear specific platform
                keys_to_remove = [
                    k for k in self.orderbooks.keys()
                    if k[0] == event_id and k[1] == platform
                ]
                for key in keys_to_remove:
                    del self.orderbooks[key]
                
                if (event_id, platform) in self.last_update:
                    del self.last_update[(event_id, platform)]
            else:
                # Clear all platforms for this event
                keys_to_remove = [
                    k for k in self.orderbooks.keys()
                    if k[0] == event_id
                ]
                for key in keys_to_remove:
                    del self.orderbooks[key]
                
                update_keys = [k for k in self.last_update.keys() if k[0] == event_id]
                for key in update_keys:
                    del self.last_update[key]
    
    def get_snapshot(self, event_id: str) -> Dict:
        """
        Get complete snapshot of orderbooks for a market across all platforms
        
        Returns:
            Dict with structure: {
                'kalshi': {'bids': [...], 'asks': [...]},
                'polymarket': {'bids': [...], 'asks': [...]},
                'timestamp': {...},
                'staleness': {...}
            }
        """
        with self.lock:
            snapshot = {}
            
            for platform in ['kalshi', 'polymarket']:
                if self.has_orderbook(event_id, platform):
                    snapshot[platform] = self.get_orderbook(event_id, platform, 'both')
                else:
                    snapshot[platform] = {'bids': [], 'asks': []}
            
            # Add metadata
            snapshot['timestamp'] = {
                platform: self.last_update.get((event_id, platform))
                for platform in ['kalshi', 'polymarket']
            }
            
            snapshot['staleness_ms'] = {
                platform: self.get_staleness_ms(event_id, platform)
                for platform in ['kalshi', 'polymarket']
            }
            
            return snapshot


# Test/Example usage
def test_orderbook_manager():
    """Test the orderbook manager"""
    manager = OrderbookManager()
    
    # Register a test market
    event_id = "nfl-bal-pit-2026-01-04"
    manager.register_market(event_id, {
        'kalshi_ticker': 'KXNFLGAME-25JAN04BALPIT-BAL',
        'poly_token_ids': {
            'Baltimore': '0x123...',
            'Pittsburgh': '0x456...'
        },
        'teams': {'home': 'Baltimore', 'away': 'Pittsburgh'}
    })
    
    # Update orderbooks
    manager.update_orderbook_both_sides(
        event_id, 'kalshi',
        bids=[(0.55, 100), (0.54, 200), (0.53, 150)],
        asks=[(0.56, 120), (0.57, 180), (0.58, 90)]
    )
    
    manager.update_orderbook_both_sides(
        event_id, 'polymarket',
        bids=[(0.54, 300), (0.53, 250), (0.52, 200)],
        asks=[(0.55, 280), (0.56, 220), (0.57, 150)]
    )
    
    # Test retrieval
    print("\n" + "="*60)
    print("Test: Orderbook Manager")
    print("="*60)
    
    for platform in ['kalshi', 'polymarket']:
        print(f"\n{platform.upper()}:")
        best_bid, best_ask = manager.get_best_bid_ask(event_id, platform)
        print(f"  Best bid: ${best_bid:.4f}")
        print(f"  Best ask: ${best_ask:.4f}")
        print(f"  Spread: ${manager.get_spread(event_id, platform):.4f}")
        print(f"  Mid: ${manager.get_mid_price(event_id, platform):.4f}")
        print(f"  Staleness: {manager.get_staleness_ms(event_id, platform):.1f}ms")
        print(f"  Liquidity (top 5 bids): {manager.get_total_liquidity(event_id, platform, 'bids', 5):.0f}")
    
    # Get snapshot
    snapshot = manager.get_snapshot(event_id)
    print("\n" + "="*60)
    print("Full Snapshot:")
    print("="*60)
    import json
    print(json.dumps({
        k: v for k, v in snapshot.items() if k != 'timestamp'
    }, indent=2, default=str))
    
    # Stats
    print("\n" + "="*60)
    print("Stats:", manager.get_stats())
    print("="*60)


if __name__ == "__main__":
    test_orderbook_manager()

