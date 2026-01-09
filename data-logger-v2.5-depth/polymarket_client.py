"""
Enhanced Polymarket API Client with Orderbook Depth Support

This version adds CLOB orderbook integration to enable:
- Full bid/ask ladder visibility
- Slippage calculation for trade sizing
- Volume-weighted average price (VWAP) analysis
- Liquidity-aware arbitrage detection

APIs Used:
- Gamma API: Market discovery and event details
- CLOB API: Real-time orderbooks and depth data

Documentation: https://docs.polymarket.com/
"""

import requests
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


class PolymarketClient:
    """Enhanced Polymarket Client with orderbook depth support"""
    
    def __init__(self, gamma_api_base="https://gamma-api.polymarket.com", clob_api_base="https://clob.polymarket.com"):
        """Initialize Polymarket client
        
        Args:
            gamma_api_base: Gamma API base URL (for browsing/discovery)
            clob_api_base: CLOB API base URL (for orderbooks/depth)
        """
        self.gamma_api_base = gamma_api_base
        self.clob_api_base = clob_api_base
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json"
        })
        
        print("✓ Polymarket client initialized with orderbook depth support")
    
    def get_token_ids_from_slug(self, slug):
        """Get token IDs for market outcomes from event slug
        
        Args:
            slug: Event slug (e.g., 'nfl-bal-pit-2026-01-04')
        
        Returns:
            dict: {
                'condition_id': str,
                'tokens': [
                    {'outcome': str, 'token_id': str, 'price': float},
                    ...
                ]
            }
        """
        try:
            response = self.session.get(
                f"{self.gamma_api_base}/events/slug/{slug}",
                timeout=10
            )
            
            if response.status_code != 200:
                print(f"✗ Failed to fetch slug {slug}: {response.status_code}")
                return None
            
            event = response.json()
            markets = event.get('markets', [])
            
            if not markets:
                return None
            
            # Find the MONEYLINE market (not team totals, spreads, etc.)
            main_market = None
            for market in markets:
                market_type = market.get('sportsMarketType', '')
                if market_type == 'moneyline':
                    main_market = market
                    break
            
            # If no moneyline found, use first market as fallback
            if not main_market:
                main_market = markets[0]
            
            condition_id = main_market.get('conditionId')
            
            # Get token IDs - parse the JSON string
            clob_token_ids_str = main_market.get('clobTokenIds', '[]')
            outcomes_str = main_market.get('outcomes', '[]')
            outcome_prices_str = main_market.get('outcomePrices', '[]')
            
            # Parse JSON strings
            import json
            try:
                clob_token_ids = json.loads(clob_token_ids_str) if isinstance(clob_token_ids_str, str) else clob_token_ids_str
                outcomes = json.loads(outcomes_str) if isinstance(outcomes_str, str) else outcomes_str
                outcome_prices = json.loads(outcome_prices_str) if isinstance(outcome_prices_str, str) else outcome_prices_str
            except:
                print(f"✗ Failed to parse JSON fields for {slug}")
                return None
            
            if not clob_token_ids or len(clob_token_ids) != len(outcomes):
                print(f"✗ Token IDs not found or mismatched for {slug}")
                return None
            
            tokens = []
            for i, outcome in enumerate(outcomes):
                tokens.append({
                    'outcome': outcome,
                    'token_id': clob_token_ids[i],
                    'price': float(outcome_prices[i]) if i < len(outcome_prices) and outcome_prices[i] else None
                })
            
            return {
                'condition_id': condition_id,
                'tokens': tokens,
                'slug': slug
            }
            
        except Exception as e:
            print(f"✗ Error fetching token IDs for {slug}: {e}")
            return None
    
    def get_orderbook(self, token_id):
        """Get full orderbook for a specific token (outcome)
        
        Args:
            token_id: CLOB token ID for the outcome
        
        Returns:
            dict: {
                'token_id': str,
                'bids': [(price, size), ...],  # sorted best to worst
                'asks': [(price, size), ...],  # sorted best to worst
                'timestamp': str
            }
        """
        try:
            response = self.session.get(
                f"{self.clob_api_base}/book",
                params={'token_id': token_id},
                timeout=10
            )
            
            if response.status_code != 200:
                print(f"✗ Failed to fetch orderbook for {token_id}: {response.status_code}")
                return None
            
            data = response.json()
            
            # Parse bids and asks
            bids = []
            asks = []
            
            for bid in data.get('bids', []):
                price = float(bid.get('price', 0))
                size = float(bid.get('size', 0))
                if price > 0 and size > 0:
                    bids.append((price, size))
            
            for ask in data.get('asks', []):
                price = float(ask.get('price', 0))
                size = float(ask.get('size', 0))
                if price > 0 and size > 0:
                    asks.append((price, size))
            
            # Sort: bids descending (best first), asks ascending (best first)
            bids.sort(reverse=True, key=lambda x: x[0])
            asks.sort(key=lambda x: x[0])
            
            return {
                'token_id': token_id,
                'bids': bids,
                'asks': asks,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            print(f"✗ Error fetching orderbook for {token_id}: {e}")
            return None
    
    def calculate_vwap(self, orders, target_size):
        """Calculate volume-weighted average price for a target size
        
        Args:
            orders: List of (price, size) tuples from orderbook
            target_size: Number of contracts to fill
        
        Returns:
            tuple: (vwap, total_filled, remaining, slippage_pct)
        """
        if not orders or target_size <= 0:
            return None, 0, target_size, 0
        
        total_cost = 0
        total_filled = 0
        best_price = orders[0][0]
        
        for price, size in orders:
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
    
    def get_market_by_slug(self, slug):
        """Get market data using event slug (LEGACY - top-of-book only)
        
        For orderbook depth, use get_token_ids_from_slug() + get_orderbook()
        """
        try:
            response = self.session.get(
                f"{self.gamma_api_base}/events/slug/{slug}",
                timeout=10
            )
            
            if response.status_code != 200:
                print(f"✗ Failed to fetch slug {slug}: {response.status_code}")
                return None
            
            event = response.json()
            markets = event.get('markets', [])
            
            if not markets:
                print(f"✗ No markets found for slug {slug}")
                return None
            
            main_market = markets[0]
            condition_id = main_market.get('conditionId')
            outcomes_raw = main_market.get('outcomes', [])
            outcome_prices_raw = main_market.get('outcomePrices', [])
            
            if not isinstance(outcomes_raw, list) or not isinstance(outcome_prices_raw, list) or \
               len(outcomes_raw) != len(outcome_prices_raw) or len(outcomes_raw) < 2:
                print(f"✗ Invalid outcomes or prices for slug {slug}")
                return None
            
            outcomes = []
            for i in range(len(outcomes_raw)):
                team_name = outcomes_raw[i]
                price = float(outcome_prices_raw[i]) if i < len(outcome_prices_raw) and outcome_prices_raw[i] else None
                
                outcomes.append({
                    'team': team_name,
                    'price': price,
                    'bid': None,  # Not available from Gamma API
                    'ask': None
                })
            
            volume = float(main_market.get("volume", 0))
            liquidity = float(main_market.get("liquidity", 0))
            
            return {
                'condition_id': condition_id,
                'outcomes': outcomes,
                'volume': volume,
                'liquidity': liquidity,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
            
        except Exception as e:
            print(f"✗ Error fetching slug {slug}: {e}")
            return None
    
    def get_markets_parallel(self, slugs, max_workers=15):
        """Get market data for multiple slugs in parallel (LEGACY)"""
        results = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_slug = {executor.submit(self.get_market_by_slug, slug): slug for slug in slugs}
            for future in as_completed(future_to_slug):
                slug = future_to_slug[future]
                try:
                    data = future.result()
                    if data:
                        results[slug] = data
                except Exception as exc:
                    print(f"✗ {slug} generated an exception: {exc}")
        return results
    
    def health_check(self):
        """Test API connectivity"""
        try:
            # Test Gamma API
            response = self.session.get(f"{self.gamma_api_base}/events", params={'limit': 1}, timeout=5)
            gamma_ok = response.status_code == 200
            
            # Test CLOB API (just check if endpoint responds)
            response = self.session.get(f"{self.clob_api_base}/", timeout=5)
            clob_ok = response.status_code in [200, 404]  # 404 is fine, means endpoint exists
            
            return gamma_ok and clob_ok
        except:
            return False
    
    def close(self):
        """Close the session"""
        self.session.close()
        print("✓ Polymarket client closed")


if __name__ == "__main__":
    # Test the orderbook functionality
    import json
    
    print("Testing Polymarket Orderbook Depth API...")
    print("=" * 80)
    
    client = PolymarketClient()
    
    # Test with an NFL game
    test_slug = "nfl-bal-pit-2026-01-04"  # Ravens vs Steelers
    
    print(f"\n📊 Step 1: Fetching token IDs for: {test_slug}")
    print("-" * 80)
    
    token_data = client.get_token_ids_from_slug(test_slug)
    
    if token_data:
        print("\n✅ Token IDs retrieved successfully!")
        print(f"\nCondition ID: {token_data['condition_id']}")
        print(f"\nOutcomes:")
        for token in token_data['tokens']:
            print(f"  {token['outcome']}:")
            print(f"    Token ID: {token['token_id']}")
            print(f"    Price: ${token['price']:.3f}" if token['price'] else "    Price: N/A")
        
        # Test orderbook for first token
        if token_data['tokens']:
            first_token = token_data['tokens'][0]
            print(f"\n📊 Step 2: Fetching orderbook for {first_token['outcome']}...")
            print("-" * 80)
            
            orderbook = client.get_orderbook(first_token['token_id'])
            
            if orderbook:
                print("\n✅ Orderbook retrieved successfully!")
                print(f"\nBids (buy orders): {len(orderbook['bids'])} levels")
                for i, (price, size) in enumerate(orderbook['bids'][:5], 1):
                    print(f"  {i}. ${price:.3f} × {size:,.0f} contracts")
                
                print(f"\nAsks (sell orders): {len(orderbook['asks'])} levels")
                for i, (price, size) in enumerate(orderbook['asks'][:5], 1):
                    print(f"  {i}. ${price:.3f} × {size:,.0f} contracts")
                
                # Test VWAP calculation
                print(f"\n📈 Step 3: VWAP Analysis for buying 1000 contracts")
                print("-" * 80)
                
                vwap, filled, remaining, slippage = client.calculate_vwap(orderbook['asks'], 1000)
                
                if vwap:
                    print(f"  Best ask price: ${orderbook['asks'][0][0]:.3f}")
                    print(f"  VWAP: ${vwap:.3f}")
                    print(f"  Filled: {filled:,.0f} / 1000 contracts")
                    print(f"  Slippage: {slippage:.2f}%")
                    if remaining > 0:
                        print(f"  ⚠️  Unfilled: {remaining:,.0f} contracts (insufficient liquidity)")
                else:
                    print("  ❌ Unable to fill any contracts")
            else:
                print("\n❌ Failed to retrieve orderbook")
    else:
        print("\n❌ Failed to retrieve token IDs")
    
    client.close()
