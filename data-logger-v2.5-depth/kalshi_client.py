"""
Enhanced Kalshi API Client with Orderbook Depth Support

This version adds orderbook depth data collection to enable:
- Full bid/ask ladder visibility
- Slippage calculation for trade sizing
- Volume-weighted average price (VWAP) analysis
- Liquidity-aware arbitrage detection

New endpoint: /markets/{ticker}/orderbook
Documentation: https://docs.kalshi.com/api-reference/market/get-market-orderbook
"""

import requests
import time
import base64
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend


class KalshiClient:
    """Enhanced Kalshi API Client with orderbook depth support"""
    
    def __init__(self, api_key, private_key_path, api_base="https://api.elections.kalshi.com/trade-api/v2"):
        """Initialize Kalshi client
        
        Args:
            api_key: Kalshi API key
            private_key_path: Path to RSA private key PEM file
            api_base: API base URL (default: production)
        """
        self.api_key = api_key
        self.api_base = api_base
        self.session = requests.Session()
        
        # Load private key
        private_key_file = Path(private_key_path)
        if not private_key_file.exists():
            raise FileNotFoundError(f"Private key not found: {private_key_path}")
        
        with open(private_key_file, 'rb') as f:
            self.private_key = serialization.load_pem_private_key(
                f.read(),
                password=None,
                backend=default_backend()
            )
        
        print("✓ Kalshi client initialized with API key authentication + orderbook depth")
    
    def _sign_request(self, method, path):
        """Sign request using RSA private key"""
        timestamp = str(int(time.time() * 1000))
        msg_string = timestamp + method + path
        
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
    
    def _make_request(self, method, path, params=None):
        """Make authenticated API request"""
        try:
            url = f"{self.api_base}{path}"
            timestamp, signature = self._sign_request(method, path)
            
            headers = {
                'KALSHI-ACCESS-KEY': self.api_key,
                'KALSHI-ACCESS-SIGNATURE': signature,
                'KALSHI-ACCESS-TIMESTAMP': timestamp,
                'Content-Type': 'application/json'
            }
            
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"✗ Kalshi request failed: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"✗ Kalshi request error: {e}")
            return None
    
    def get_market_orderbook(self, ticker, depth=10):
        """Get full orderbook depth for a market
        
        Args:
            ticker: Kalshi market ticker
            depth: Number of price levels to retrieve (default: 10)
        
        Returns:
            dict: Orderbook data with bid/ask ladders
            {
                'ticker': str,
                'yes_bids': [(price, size, count), ...],  # sorted best to worst
                'yes_asks': [(price, size, count), ...],  # sorted best to worst
                'no_bids': [(price, size, count), ...],
                'no_asks': [(price, size, count), ...],
                'timestamp': str
            }
        """
        try:
            data = self._make_request('GET', f"/markets/{ticker}/orderbook", params={'depth': depth})
            
            if not data or 'orderbook' not in data:
                return None
            
            orderbook = data['orderbook']
            
            # Check if orderbook has data
            if not orderbook or (orderbook.get('yes') is None and orderbook.get('no') is None):
                return None
            
            # Parse YES side orderbook
            # Format: [[price_in_cents, size], ...] or [{"price": ..., "size": ...}, ...]
            yes_bids = []
            yes_asks = []
            
            yes_levels = orderbook.get('yes') or []
            for level in yes_levels:
                if isinstance(level, list) and len(level) >= 2:
                    # Array format: [price, size]
                    price = level[0] / 100.0
                    size = level[1]
                    yes_asks.append((price, size, 1))  # Assume 1 order if not specified
                elif isinstance(level, dict):
                    # Dict format: {"price": ..., "size": ..., "side": ...}
                    price = level.get('price', 0) / 100.0
                    size = level.get('size', 0)
                    count = level.get('count', 1)
                    
                    if level.get('side') == 'bid':
                        yes_bids.append((price, size, count))
                    elif level.get('side') == 'ask':
                        yes_asks.append((price, size, count))
            
            # Parse NO side orderbook
            no_bids = []
            no_asks = []
            
            no_levels = orderbook.get('no') or []
            for level in no_levels:
                if isinstance(level, list) and len(level) >= 2:
                    # Array format: [price, size]
                    price = level[0] / 100.0
                    size = level[1]
                    no_asks.append((price, size, 1))
                elif isinstance(level, dict):
                    # Dict format
                    price = level.get('price', 0) / 100.0
                    size = level.get('size', 0)
                    count = level.get('count', 1)
                    
                    if level.get('side') == 'bid':
                        no_bids.append((price, size, count))
                    elif level.get('side') == 'ask':
                        no_asks.append((price, size, count))
            
            # Sort: bids descending (best first), asks ascending (best first)
            yes_bids.sort(reverse=True, key=lambda x: x[0])
            yes_asks.sort(key=lambda x: x[0])
            no_bids.sort(reverse=True, key=lambda x: x[0])
            no_asks.sort(key=lambda x: x[0])
            
            return {
                'ticker': ticker,
                'yes_bids': yes_bids,
                'yes_asks': yes_asks,
                'no_bids': no_bids,
                'no_asks': no_asks,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            print(f"✗ Error fetching orderbook for {ticker}: {e}")
            return None
    
    def calculate_vwap(self, orders, target_size):
        """Calculate volume-weighted average price for a target size
        
        Args:
            orders: List of (price, size, count) tuples from orderbook
            target_size: Number of contracts to fill
        
        Returns:
            tuple: (vwap, total_filled, remaining, slippage_pct)
        """
        if not orders or target_size <= 0:
            return None, 0, target_size, 0
        
        total_cost = 0
        total_filled = 0
        best_price = orders[0][0]
        
        for price, size, count in orders:
            if total_filled >= target_size:
                break
            
            # Fill what we can at this level
            fill_size = min(size, target_size - total_filled)
            total_cost += price * fill_size
            total_filled += fill_size
        
        if total_filled == 0:
            return None, 0, target_size, 0
        
        vwap = total_cost / total_filled
        remaining = target_size - total_filled
        slippage_pct = ((vwap - best_price) / best_price) * 100 if best_price > 0 else 0
        
        return vwap, total_filled, remaining, slippage_pct
    
    def get_market(self, ticker):
        """Get basic market data (top-of-book only) - legacy method"""
        try:
            data = self._make_request('GET', f"/markets/{ticker}")
            
            if not data:
                return None
            
            market = data.get("market", {})
            
            yes_bid = market.get("yes_bid", 0) / 100.0
            yes_ask = market.get("yes_ask", 0) / 100.0
            no_bid = market.get("no_bid", 0) / 100.0
            no_ask = market.get("no_ask", 0) / 100.0
            
            yes_price = (yes_bid + yes_ask) / 2 if yes_bid and yes_ask else None
            no_price = (no_bid + no_ask) / 2 if no_bid and no_ask else None
            
            if yes_price is None and market.get("last_price"):
                yes_price = market.get("last_price", 0) / 100.0
                no_price = 1.0 - yes_price if yes_price else None
            
            return {
                'ticker': ticker,
                'yes_price': yes_price,
                'no_price': no_price,
                'yes_bid': yes_bid if yes_bid else None,
                'yes_ask': yes_ask if yes_ask else None,
                'no_bid': no_bid if no_bid else None,
                'no_ask': no_ask if no_ask else None,
                'volume': market.get("volume", 0),
                'liquidity': market.get("liquidity", 0),
                'timestamp': datetime.utcnow().isoformat(),
                'raw_data': market
            }
            
        except Exception as e:
            print(f"✗ Error fetching {ticker}: {e}")
            return None
    
    def get_markets_parallel(self, tickers, max_workers=20):
        """Get market data for multiple tickers in parallel"""
        results = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ticker = {executor.submit(self.get_market, ticker): ticker for ticker in tickers}
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    data = future.result()
                    if data:
                        results[ticker] = data
                except Exception as exc:
                    print(f"✗ {ticker} generated an exception: {exc}")
        return results
    
    def health_check(self):
        """Test API connectivity"""
        try:
            # Test with a simple markets list call
            data = self._make_request('GET', '/markets', params={'limit': 1})
            return data is not None
        except:
            return False
    
    def close(self):
        """Close the session"""
        self.session.close()
        print("✓ Kalshi client closed")


if __name__ == "__main__":
    # Test the orderbook functionality
    import json
    import sys
    
    print("Testing Kalshi Orderbook Depth API...")
    print("=" * 80)
    
    # Load config
    try:
        with open('config/settings.json', 'r') as f:
            config = json.load(f)
        
        client = KalshiClient(
            api_key=config['kalshi']['api_key'],
            private_key_path=config['kalshi']['private_key_path']
        )
        
        # Test with an NFL market
        test_ticker = "KXNFLGAME-26JAN04BALPIT-PIT"  # Ravens vs Steelers (Sunday)
        
        print(f"\n📊 Fetching orderbook for: {test_ticker}")
        print("-" * 80)
        
        orderbook = client.get_market_orderbook(test_ticker, depth=10)
        
        if orderbook:
            print("\n✅ Orderbook retrieved successfully!")
            print(f"\nYES Side:")
            print(f"  Bids (buy orders): {len(orderbook['yes_bids'])} levels")
            for i, (price, size, count) in enumerate(orderbook['yes_bids'][:5], 1):
                print(f"    {i}. ${price:.3f} × {size:,} contracts ({count} orders)")
            
            print(f"\n  Asks (sell orders): {len(orderbook['yes_asks'])} levels")
            for i, (price, size, count) in enumerate(orderbook['yes_asks'][:5], 1):
                print(f"    {i}. ${price:.3f} × {size:,} contracts ({count} orders)")
            
            # Test VWAP calculation
            print(f"\n📈 VWAP Analysis for buying 1000 contracts:")
            print("-" * 80)
            
            vwap, filled, remaining, slippage = client.calculate_vwap(orderbook['yes_asks'], 1000)
            
            if vwap:
                print(f"  Best ask price: ${orderbook['yes_asks'][0][0]:.3f}")
                print(f"  VWAP: ${vwap:.3f}")
                print(f"  Filled: {filled:,} / 1000 contracts")
                print(f"  Slippage: {slippage:.2f}%")
                if remaining > 0:
                    print(f"  ⚠️  Unfilled: {remaining:,} contracts (insufficient liquidity)")
            else:
                print("  ❌ Unable to fill any contracts")
        else:
            print("\n❌ Failed to retrieve orderbook")
        
        client.close()
        
    except FileNotFoundError:
        print("❌ Config file not found. Run from data-logger-v2.5-depth directory.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
