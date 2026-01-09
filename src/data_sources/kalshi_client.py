"""
Kalshi API Client (v2.0 - IMPROVED)

Improvements:
1. Full order book depth fetching
2. Proper bid/ask extraction with volume
3. Dynamic spread calculation
4. Batch market fetching optimization
"""
import os
import requests
import time
import hashlib
import base64
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from dotenv import load_dotenv

load_dotenv()


@dataclass
class OrderBookLevel:
    """Single level in order book"""
    price: float  # 0-1 probability
    quantity: int  # Number of contracts
    
    @property
    def value_usd(self) -> float:
        """Total USD value at this level"""
        return self.price * self.quantity


@dataclass
class OrderBookData:
    """Parsed order book with depth analysis"""
    ticker: str
    yes_bids: List[OrderBookLevel]
    yes_asks: List[OrderBookLevel]
    no_bids: List[OrderBookLevel]
    no_asks: List[OrderBookLevel]
    
    @property
    def best_yes_bid(self) -> Optional[float]:
        return self.yes_bids[0].price if self.yes_bids else None
    
    @property
    def best_yes_ask(self) -> Optional[float]:
        # If we have actual asks, use them; otherwise estimate from bid + spread
        if self.yes_asks:
            return self.yes_asks[0].price
        elif self.yes_bids:
            return min(self.yes_bids[0].price + 0.02, 0.99)
        return None
    
    @property
    def best_no_bid(self) -> Optional[float]:
        return self.no_bids[0].price if self.no_bids else None
    
    @property
    def best_no_ask(self) -> Optional[float]:
        if self.no_asks:
            return self.no_asks[0].price
        elif self.no_bids:
            return min(self.no_bids[0].price + 0.02, 0.99)
        return None
    
    @property
    def yes_spread(self) -> float:
        """Calculate YES bid-ask spread"""
        if self.best_yes_bid and self.best_yes_ask:
            return self.best_yes_ask - self.best_yes_bid
        return 0.02  # Default 2¢ spread
    
    @property
    def no_spread(self) -> float:
        """Calculate NO bid-ask spread"""
        if self.best_no_bid and self.best_no_ask:
            return self.best_no_ask - self.best_no_bid
        return 0.02
    
    @property
    def yes_bid_depth_usd(self) -> float:
        """Total USD liquidity on YES bid side"""
        return sum(level.value_usd for level in self.yes_bids)
    
    @property
    def yes_ask_depth_usd(self) -> float:
        """Total USD liquidity on YES ask side"""
        return sum(level.value_usd for level in self.yes_asks)
    
    @property
    def no_bid_depth_usd(self) -> float:
        """Total USD liquidity on NO bid side"""
        return sum(level.value_usd for level in self.no_bids)
    
    @property
    def no_ask_depth_usd(self) -> float:
        """Total USD liquidity on NO ask side"""
        return sum(level.value_usd for level in self.no_asks)
    
    def get_fill_price(self, side: str, size_usd: float) -> Optional[float]:
        """
        Calculate actual fill price for a given order size.
        
        This walks through the order book to determine the average
        price you'd pay/receive for the given size.
        
        Args:
            side: 'yes' or 'no'
            size_usd: Amount in USD to trade
            
        Returns:
            Average fill price, or None if insufficient liquidity
        """
        if side == 'yes':
            levels = self.yes_asks if self.yes_asks else []
            # If no asks, estimate from bids
            if not levels and self.yes_bids:
                return min(self.yes_bids[0].price + 0.02, 0.99)
        else:
            levels = self.no_asks if self.no_asks else []
            if not levels and self.no_bids:
                return min(self.no_bids[0].price + 0.02, 0.99)
        
        if not levels:
            return None
        
        remaining_size = size_usd
        total_cost = 0.0
        total_quantity = 0
        
        for level in levels:
            level_value = level.value_usd
            if level_value >= remaining_size:
                # Can fill remaining from this level
                quantity_needed = remaining_size / level.price
                total_cost += quantity_needed * level.price
                total_quantity += quantity_needed
                remaining_size = 0
                break
            else:
                # Take entire level
                total_cost += level_value
                total_quantity += level.quantity
                remaining_size -= level_value
        
        if remaining_size > 0:
            # Insufficient liquidity
            return None
        
        return total_cost / total_quantity if total_quantity > 0 else None


class KalshiClient:
    """Client for interacting with Kalshi API (v2.0)"""

    def __init__(self):
        self.api_key = os.getenv('KALSHI_API_KEY')
        private_key_path = os.getenv('KALSHI_PRIVATE_KEY_PATH', 'kalshi_private_key.pem')

        if not self.api_key or not private_key_path:
            raise ValueError("KALSHI_API_KEY and KALSHI_PRIVATE_KEY_PATH must be set in .env")

        # Load private key
        full_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), private_key_path)
        with open(full_path, 'rb') as f:
            self.private_key = serialization.load_pem_private_key(
                f.read(),
                password=None,
                backend=default_backend()
            )

        self.base_url = "https://api.elections.kalshi.com/trade-api/v2"
        self.session = requests.Session()
        
        # Increase connection pool for parallel fetching
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        adapter = HTTPAdapter(
            pool_connections=25,
            pool_maxsize=30,
            max_retries=Retry(total=3, backoff_factor=0.3)
        )
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

        print("✓ Kalshi client initialized (v2.0)")

    def _sign_request(self, method: str, path: str, body: str = "") -> Tuple[str, str]:
        """Sign request using RSA private key"""
        timestamp = str(int(time.time() * 1000))

        # Create signature payload: timestamp + method + path (NO body per Kalshi docs)
        msg_string = timestamp + method + path

        # Sign with private key using RSA-PSS
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

    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, 
                      body: Optional[Dict] = None) -> Optional[Dict]:
        """Make authenticated request to Kalshi API with rate limiting"""
        try:
            from src.rate_limiter import get_kalshi_limiter
            limiter = get_kalshi_limiter()
            limiter.wait_if_needed()

            path = f"/trade-api/v2{endpoint}"
            url = f"{self.base_url}{endpoint}"

            path_for_signing = path.split('?')[0]

            body_str = ""
            if body:
                import json
                body_str = json.dumps(body)

            timestamp, signature = self._sign_request(method, path_for_signing, body_str)

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
                json=body if body else None,
                timeout=15
            )

            response.raise_for_status()

            if hasattr(limiter, 'report_success'):
                limiter.report_success()

            return response.json()

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                from src.rate_limiter import get_kalshi_limiter
                limiter = get_kalshi_limiter()
                if hasattr(limiter, 'report_429'):
                    limiter.report_429()
            print(f"❌ Kalshi API error: {e}")
            print(f"   Response: {e.response.text if e.response else 'No response'}")
            return None
        except Exception as e:
            print(f"❌ Error making Kalshi request: {e}")
            return None

    def get_active_markets(self, limit: int = 100, status: str = "open") -> List[Dict]:
        """Get active markets from Kalshi"""
        params = {
            'limit': limit,
            'status': status
        }

        result = self._make_request('GET', '/markets', params=params)

        if result and 'markets' in result:
            markets = result['markets']
            print(f"✓ Fetched {len(markets)} active Kalshi markets")
            return markets

        return []

    def get_market(self, ticker: str) -> Optional[Dict]:
        """Get specific market by ticker"""
        result = self._make_request('GET', f'/markets/{ticker}')

        if result and 'market' in result:
            return result['market']

        return None

    def get_market_orderbook(self, ticker: str, depth: int = 1) -> Optional[Dict]:
        """
        Get orderbook for a specific market (legacy format for compatibility)
        
        For full depth analysis, use get_orderbook_full() instead.
        """
        params = {'depth': depth}
        result = self._make_request('GET', f'/markets/{ticker}/orderbook', params=params)

        if result and 'orderbook' in result:
            orderbook = result['orderbook']

            yes_data = orderbook.get('yes', [])
            no_data = orderbook.get('no', [])

            yes_bid = None
            yes_ask = None
            no_bid = None
            no_ask = None
            
            if yes_data and isinstance(yes_data, list) and len(yes_data) > 0:
                if isinstance(yes_data[0], list) and len(yes_data[0]) > 0:
                    yes_bid = yes_data[0][0] / 100
                    if yes_bid is not None:
                        yes_ask = yes_bid + 0.02

            if no_data and isinstance(no_data, list) and len(no_data) > 0:
                if isinstance(no_data[0], list) and len(no_data[0]) > 0:
                    no_bid = no_data[0][0] / 100
                    if no_bid is not None:
                        no_ask = no_bid + 0.02

            return {
                'ticker': ticker,
                'yes_bid': yes_bid,
                'yes_ask': yes_ask or (yes_bid + 0.01 if yes_bid else None),
                'no_bid': no_bid,
                'no_ask': no_ask or (no_bid + 0.01 if no_bid else None),
            }

        return None

    def get_orderbook_full(self, ticker: str, depth: int = 10) -> Optional[OrderBookData]:
        """
        Get FULL order book with depth analysis.
        
        NEW: Returns structured OrderBookData with depth calculations.
        
        Args:
            ticker: Market ticker
            depth: Number of levels to fetch (default 10)
            
        Returns:
            OrderBookData with full depth analysis
        """
        params = {'depth': depth}
        result = self._make_request('GET', f'/markets/{ticker}/orderbook', params=params)

        if not result or 'orderbook' not in result:
            return None

        orderbook = result['orderbook']
        yes_data = orderbook.get('yes', [])
        no_data = orderbook.get('no', [])

        def parse_levels(data: List) -> List[OrderBookLevel]:
            """Parse order book levels from API format [[price_cents, quantity], ...]"""
            levels = []
            if data and isinstance(data, list):
                for item in data:
                    if isinstance(item, list) and len(item) >= 2:
                        price = item[0] / 100  # Convert cents to probability
                        quantity = item[1]
                        levels.append(OrderBookLevel(price=price, quantity=quantity))
            return levels

        # Parse YES side (bids - what people want to pay)
        yes_bids = parse_levels(yes_data)
        
        # Parse NO side (bids - what people want to pay)
        no_bids = parse_levels(no_data)
        
        # CRITICAL FIX: In Kalshi's binary market:
        # - YES ask = 1 - NO bid (you buy YES by selling to NO bidders)
        # - NO ask = 1 - YES bid (you buy NO by selling to YES bidders)
        #
        # The API returns bids for each side. To get the effective ASK price,
        # we derive it from the OPPOSITE side's bid.
        #
        # Example: If NO bid = 0.70, then YES ask ≈ 0.30 (1 - 0.70)
        # This ensures YES ask + NO ask ≈ 100-106% (with typical vig)
        
        yes_asks = []
        no_asks = []
        
        # YES ask is derived from NO bids (the best NO bid determines YES ask)
        if no_bids:
            # YES ask = 1 - NO bid (with small spread adjustment)
            for bid in no_bids[:3]:
                ask_price = max(1.0 - bid.price + 0.01, 0.01)  # Small spread on top
                ask_price = min(ask_price, 0.99)
                yes_asks.append(OrderBookLevel(price=ask_price, quantity=bid.quantity))
        elif yes_bids:
            # Fallback: if no NO bids, estimate from YES bids
            for bid in yes_bids[:3]:
                ask_price = min(bid.price + 0.03, 0.99)
                yes_asks.append(OrderBookLevel(price=ask_price, quantity=bid.quantity))
        
        # NO ask is derived from YES bids (the best YES bid determines NO ask)
        if yes_bids:
            # NO ask = 1 - YES bid (with small spread adjustment)
            for bid in yes_bids[:3]:
                ask_price = max(1.0 - bid.price + 0.01, 0.01)  # Small spread on top
                ask_price = min(ask_price, 0.99)
                no_asks.append(OrderBookLevel(price=ask_price, quantity=bid.quantity))
        elif no_bids:
            # Fallback: if no YES bids, estimate from NO bids
            for bid in no_bids[:3]:
                ask_price = min(bid.price + 0.03, 0.99)
                no_asks.append(OrderBookLevel(price=ask_price, quantity=bid.quantity))

        return OrderBookData(
            ticker=ticker,
            yes_bids=yes_bids,
            yes_asks=yes_asks,
            no_bids=no_bids,
            no_asks=no_asks
        )

    def get_sports_markets(self) -> List[Dict]:
        """
        Get sports-related markets from Kalshi with parallel orderbook fetching
        """
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            selected_sports = os.getenv('SELECTED_SPORTS', 'all').lower()
            
            all_series = {
                'nba': 'KXNBAGAME',
                'nfl': 'KXNFLGAME',
                'nhl': 'KXNHLGAME',
                'mlb': 'KXMLBGAME',
                'cfb': 'KXNCAAFGAME',
                'ncaab': 'KXNCAABGAME',
            }
            
            if selected_sports != 'all':
                selected = [s.strip().lower() for s in selected_sports.split(',')]
                sports_series = [all_series[s] for s in selected if s in all_series]
            else:
                sports_series = list(all_series.values())
            
            all_markets_raw = []

            for series_ticker in sports_series:
                result = self._make_request('GET', '/markets', params={
                    'series_ticker': series_ticker,
                    'limit': 200,
                    'status': 'open'
                })

                if result and 'markets' in result:
                    markets = result['markets']
                    print(f"  Found {len(markets)} markets in {series_ticker}")
                    for market in markets:
                        market['series'] = series_ticker
                        all_markets_raw.append(market)

            if not all_markets_raw:
                print("✓ Found 0 total sports markets on Kalshi")
                return []

            def fetch_market_with_orderbook(market):
                """Fetch orderbook for a single market with full depth"""
                ticker = market.get('ticker', '')
                title = market.get('title', '')
                
                # Get full orderbook
                orderbook = self.get_orderbook_full(ticker, depth=5)

                if orderbook and orderbook.best_yes_bid is not None:
                    # Use actual ask prices (or estimated if not available)
                    yes_ask = orderbook.best_yes_ask
                    no_ask = orderbook.best_no_ask
                    
                    if yes_ask is not None and no_ask is not None:
                        # CRITICAL: yes_sub_title tells us WHICH TEAM "YES" refers to
                        # e.g., "Portland" means YES = Portland wins, NO = Portland loses
                        yes_team = market.get('yes_sub_title', '')
                        
                        return {
                            'ticker': ticker,
                            'title': title,
                            'subtitle': market.get('subtitle', ''),
                            'category': market.get('category', 'Sports'),
                            'series': market.get('series'),
                            'yes_team': yes_team,  # The team that YES refers to
                            'yes_price': yes_ask,
                            'no_price': no_ask,
                            'yes_bid': orderbook.best_yes_bid,
                            'no_bid': orderbook.best_no_bid,
                            'yes_ask': yes_ask,
                            'no_ask': no_ask,
                            'spread': orderbook.yes_spread,
                            'yes_depth_usd': orderbook.yes_bid_depth_usd,
                            'no_depth_usd': orderbook.no_bid_depth_usd,
                            'close_time': market.get('close_time'),
                            'volume': market.get('volume', 0),
                        }
                return None

            # Fetch orderbooks in parallel
            sports_markets = []
            with ThreadPoolExecutor(max_workers=20) as executor:
                future_to_market = {executor.submit(fetch_market_with_orderbook, market): market 
                                   for market in all_markets_raw}
                
                for future in as_completed(future_to_market):
                    result = future.result()
                    if result:
                        sports_markets.append(result)

            print(f"✓ Found {len(sports_markets)} total sports markets on Kalshi")
            return sports_markets

        except Exception as e:
            print(f"❌ Error fetching Kalshi sports markets: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_markets_by_tickers(self, tickers: List[str]) -> List[Dict]:
        """
        Fetch markets with orderbooks for a specific list of tickers (optimized)
        """
        if not tickers:
            return []
        
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            def fetch_market_with_orderbook(ticker):
                """Fetch market and orderbook for a single ticker"""
                market = self.get_market(ticker)
                if not market:
                    return None
                
                orderbook = self.get_orderbook_full(ticker, depth=5)
                
                if orderbook and orderbook.best_yes_bid is not None:
                    yes_ask = orderbook.best_yes_ask
                    no_ask = orderbook.best_no_ask
                    
                    if yes_ask is not None and no_ask is not None:
                        # CRITICAL: yes_sub_title tells us WHICH TEAM "YES" refers to
                        yes_team = market.get('yes_sub_title', '')
                        
                        return {
                            'ticker': ticker,
                            'title': market.get('title', ''),
                            'subtitle': market.get('subtitle', ''),
                            'category': market.get('category', 'Sports'),
                            'series': market.get('series'),
                            'yes_team': yes_team,  # The team that YES refers to
                            'yes_price': yes_ask,
                            'no_price': no_ask,
                            'yes_bid': orderbook.best_yes_bid,
                            'no_bid': orderbook.best_no_bid,
                            'yes_ask': yes_ask,
                            'no_ask': no_ask,
                            'spread': orderbook.yes_spread,
                            'yes_depth_usd': orderbook.yes_bid_depth_usd,
                            'no_depth_usd': orderbook.no_bid_depth_usd,
                            'close_time': market.get('close_time'),
                            'volume': market.get('volume', 0),
                        }
                return None
            
            markets = []
            with ThreadPoolExecutor(max_workers=20) as executor:
                future_to_ticker = {executor.submit(fetch_market_with_orderbook, ticker): ticker 
                                   for ticker in tickers}
                
                for future in as_completed(future_to_ticker):
                    result = future.result()
                    if result:
                        markets.append(result)
            
            return markets
            
        except Exception as e:
            print(f"❌ Error fetching Kalshi markets by tickers: {e}")
            import traceback
            traceback.print_exc()
            return []

    def search_market(self, event_title: str) -> Optional[Dict]:
        """Search for a market by event title"""
        try:
            markets = self.get_sports_markets()

            query_lower = event_title.lower()

            for market in markets:
                title_lower = market['title'].lower()
                subtitle_lower = market['subtitle'].lower()

                if query_lower in title_lower or query_lower in subtitle_lower:
                    return market

            return None

        except Exception as e:
            print(f"⚠️  Error searching for market '{event_title}': {e}")
            return None

    def get_balance(self) -> Optional[Dict]:
        """Get account balance and portfolio value"""
        result = self._make_request('GET', '/portfolio/balance')

        if result:
            balance_cents = result.get('balance', 0)
            payout_cents = result.get('payout', 0)

            return {
                'balance': balance_cents / 100,
                'payout': payout_cents / 100,
                'total': (balance_cents + payout_cents) / 100
            }

        return None

    def get_positions(self) -> Optional[List[Dict]]:
        """Get all open positions"""
        result = self._make_request('GET', '/portfolio/positions')

        if result and 'market_positions' in result:
            return result['market_positions']

        return []

    def get_fills(self, limit: int = 100) -> Optional[List[Dict]]:
        """Get recent fills (executed trades)"""
        params = {'limit': limit}
        result = self._make_request('GET', '/portfolio/fills', params=params)

        if result and 'fills' in result:
            return result['fills']

        return []


if __name__ == "__main__":
    # Test the client
    print("\nTesting Kalshi client v2.0...")
    client = KalshiClient()

    print("\n1. Fetching active markets...")
    markets = client.get_active_markets(limit=5)

    if markets:
        print(f"\nSample market:")
        print(f"  Title: {markets[0].get('title', 'N/A')}")
        print(f"  Ticker: {markets[0].get('ticker', 'N/A')}")

    print("\n2. Fetching sports markets with full orderbooks...")
    sports_markets = client.get_sports_markets()

    if sports_markets:
        print(f"\nFound {len(sports_markets)} sports markets")
        for market in sports_markets[:5]:
            print(f"  - {market['title']}")
            print(f"    YES: bid={market.get('yes_bid', 0):.3f} ask={market.get('yes_ask', 0):.3f}")
            print(f"    Spread: {market.get('spread', 0):.3f}")
            print(f"    Depth: ${market.get('yes_depth_usd', 0):.2f}")
    else:
        print("No sports markets found")
