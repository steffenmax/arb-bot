"""
Polymarket Order Executor (v2.0 - IMPROVED)

Improvements:
1. Better error handling with specific error types
2. Order status checking and monitoring
3. Cancellation support for rollback
4. Batch price fetching optimization
"""
import os
import time
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL
import sys
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

load_dotenv()


class OrderStatus(Enum):
    """Order status enum"""
    PENDING = "pending"
    LIVE = "live"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


@dataclass
class OrderResult:
    """Structured order result"""
    success: bool
    order_id: Optional[str]
    status: OrderStatus
    filled_size: float
    filled_price: float
    remaining_size: float
    error: Optional[str]
    error_type: Optional[str]
    timestamp: float
    raw_response: Optional[Dict]
    
    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'order_id': self.order_id,
            'status': self.status.value,
            'filled_size': self.filled_size,
            'filled_price': self.filled_price,
            'remaining_size': self.remaining_size,
            'error': self.error,
            'error_type': self.error_type,
            'timestamp': self.timestamp,
        }


class PolymarketExecutor:
    """Execute trades on Polymarket (v2.0)"""

    def __init__(self):
        self.private_key = os.getenv('POLYMARKET_PRIVATE_KEY')
        if not self.private_key:
            raise ValueError("POLYMARKET_PRIVATE_KEY not found in .env")
        
        self.funder_address = os.getenv('POLYMARKET_FUNDER_ADDRESS')
        signature_type = int(os.getenv('POLYMARKET_SIGNATURE_TYPE', '1' if self.funder_address else '0'))

        self.client = ClobClient(
            host="https://clob.polymarket.com",
            key=self.private_key,
            chain_id=137,
            signature_type=signature_type,
            funder=self.funder_address
        )

        self.creds = self.client.create_or_derive_api_creds()
        self.client.set_api_creds(self.creds)

        print("✓ Polymarket executor initialized (v2.0)")

    def get_orderbook(self, token_id: str) -> Optional[Dict]:
        """
        Fetch order book for a token.

        Returns:
            Dict with bids, asks, and calculated metrics
        """
        try:
            orderbook_url = f"https://clob.polymarket.com/book"
            params = {'token_id': token_id}
            response = requests.get(orderbook_url, params=params, timeout=10)
            
            if response.status_code != 200:
                return None

            data = response.json()
            bids = data.get('bids', [])
            asks = data.get('asks', [])
            
            best_bid = float(bids[0]['price']) if bids else None
            best_ask = float(asks[0]['price']) if asks else None
            
            bid_depth = sum(float(b['size']) * float(b['price']) for b in bids)
            ask_depth = sum(float(a['size']) * float(a['price']) for a in asks)
            
            spread = (best_ask - best_bid) if (best_bid and best_ask) else None
            
            return {
                'bids': bids,
                'asks': asks,
                'best_bid': best_bid,
                'best_ask': best_ask,
                'bid_depth_usd': bid_depth,
                'ask_depth_usd': ask_depth,
                'spread': spread,
                'mid_price': (best_bid + best_ask) / 2 if (best_bid and best_ask) else None
            }
        except Exception as e:
            print(f"  Error fetching orderbook: {e}")
            return None

    def get_midpoint(self, token_id: str) -> Optional[float]:
        """Get midpoint price for a token"""
        try:
            result = self.client.get_midpoint(token_id)
            if result and isinstance(result, dict):
                return float(result.get('mid', 0))
            return None
        except:
            return None

    def get_prices_batch(self, token_ids: List[str]) -> Dict[str, float]:
        """
        Batch fetch prices for multiple tokens.
        
        More efficient than individual calls.
        """
        prices = {}
        
        # Use parallel fetching
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def fetch_price(token_id):
            try:
                mid = self.get_midpoint(token_id)
                return token_id, mid
            except:
                return token_id, None
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(fetch_price, tid): tid for tid in token_ids}
            for future in as_completed(futures):
                token_id, price = future.result()
                if price is not None:
                    prices[token_id] = price
        
        return prices

    def execute_market_order(
        self,
        market_id: str,
        token_id: str,
        side: str,
        size: float,
        max_price: float = None
    ) -> Dict:
        """
        Execute a market order on Polymarket
        
        Returns legacy Dict format for compatibility
        """
        result = self.execute_order(
            market_id=market_id,
            token_id=token_id,
            side=side,
            size=size,
            max_price=max_price
        )
        return result.to_dict()

    def execute_order(
        self,
        market_id: str,
        token_id: str,
        side: str,
        size: float,
        max_price: float = None,
        wait_for_fill: bool = True,
        fill_timeout: float = 5.0
    ) -> OrderResult:
        """
        Execute an order on Polymarket with structured result.

        Args:
            market_id: Market/condition ID
            token_id: Token ID for the outcome
            side: "BUY" or "SELL"
            size: Amount in USDC
            max_price: Maximum price (0-1) - optional. If None, uses current best ask.
            wait_for_fill: If True, waits for order to fill before returning
            fill_timeout: Max seconds to wait for fill

        Returns:
            OrderResult with detailed execution info
        """
        try:
            print(f"\n⚡ Executing Polymarket order:")
            print(f"  Market ID: {market_id}")
            print(f"  Token ID: {token_id}")
            print(f"  Side: {side}")
            print(f"  Size: ${size:.2f}")

            # CRITICAL FIX: Fetch current best ask for aggressive pricing
            order_side = BUY if side.upper() == "BUY" else SELL
            
            if order_side == BUY:
                # For BUY orders, use current best ask (not stale expected price)
                orderbook = self.get_orderbook(token_id)
                if orderbook and orderbook.get('best_ask'):
                    current_ask = orderbook['best_ask']
                    # Use best ask + 1 cent for aggressive fill
                    order_price = min(current_ask + 0.01, 0.99)
                    print(f"  Current best ask: {current_ask:.4f}")
                    print(f"  Using aggressive price: {order_price:.4f}")
                elif max_price:
                    order_price = max_price
                    print(f"  Max price (fallback): {order_price:.4f}")
                else:
                    order_price = 0.99
                    print(f"  Using default max: {order_price:.4f}")
            else:
                # For SELL, use current best bid - 1 cent
                orderbook = self.get_orderbook(token_id)
                if orderbook and orderbook.get('best_bid'):
                    current_bid = orderbook['best_bid']
                    order_price = max(current_bid - 0.01, 0.01)
                    print(f"  Current best bid: {current_bid:.4f}")
                    print(f"  Using aggressive price: {order_price:.4f}")
                elif max_price:
                    order_price = max_price
                else:
                    order_price = 0.01
            
            # Convert USDC to tokens
            if order_price > 0:
                size_in_tokens = size / order_price
            else:
                size_in_tokens = size
            
            size_in_tokens = round(size_in_tokens, 2)
            
            # Minimum size check
            if size_in_tokens < 5:
                size_in_tokens = 5.0
                print(f"  ⚠️  Size adjusted to minimum: 5 tokens")
            
            order_args = OrderArgs(
                token_id=token_id,
                price=order_price,
                size=size_in_tokens,
                side=order_side
            )

            print(f"  Creating order...")
            signed_order = self.client.create_order(order_args)
            
            print(f"  Posting order...")
            try:
                # Sync balance/allowance
                try:
                    from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
                    sig_type = getattr(self.client.builder, 'sig_type', 0)
                    params = BalanceAllowanceParams(
                        asset_type=AssetType.COLLATERAL,
                        signature_type=sig_type
                    )
                    self.client.update_balance_allowance(params)
                except Exception as sync_error:
                    print(f"  ⚠️  Balance sync skipped: {str(sync_error)[:50]}")
                
                response = self.client.post_order(signed_order, OrderType.GTC)
                
            except Exception as e:
                error_str = str(e)
                
                if 'Request exception' in error_str or 'timeout' in error_str.lower():
                    return OrderResult(
                        success=False,
                        order_id=None,
                        status=OrderStatus.UNKNOWN,
                        filled_size=0,
                        filled_price=order_price,
                        remaining_size=size,
                        error='Request timeout - order may have been placed',
                        error_type='request_timeout',
                        timestamp=time.time(),
                        raw_response=None
                    )
                
                if '403' in error_str or 'cloudflare' in error_str.lower():
                    return OrderResult(
                        success=False,
                        order_id=None,
                        status=OrderStatus.UNKNOWN,
                        filled_size=0,
                        filled_price=order_price,
                        remaining_size=size,
                        error='Cloudflare block - likely US geolocation',
                        error_type='us_geoblock',
                        timestamp=time.time(),
                        raw_response=None
                    )
                
                    raise
            
            # Extract order ID - Polymarket uses 'orderID' (capital D)
            order_id = None
            if isinstance(response, dict):
                order_id = response.get('orderID') or response.get('orderId') or response.get('order_id') or response.get('id')
                if not order_id and 'order' in response:
                    order_id = response['order'].get('orderID') or response['order'].get('id') or response['order'].get('order_id')
            elif hasattr(response, 'orderID'):
                order_id = response.orderID
            elif hasattr(response, 'id'):
                order_id = response.id
            elif hasattr(response, 'order_id'):
                order_id = response.order_id
            
            if order_id:
                print(f"\n✓ Order placed: {order_id}")
                
                # CRITICAL FIX: Wait for fill confirmation
                if wait_for_fill:
                    print(f"  Waiting for fill (max {fill_timeout}s)...")
                    start_time = time.time()
                    
                    while time.time() - start_time < fill_timeout:
                        status_result = self.get_order_status(str(order_id))
                        
                        if status_result.status == OrderStatus.FILLED:
                            print(f"  ✓ FILLED! Size: {status_result.filled_size:.2f}")
                            return OrderResult(
                                success=True,
                                order_id=str(order_id),
                                status=OrderStatus.FILLED,
                                filled_size=status_result.filled_size,
                                filled_price=order_price,
                                remaining_size=0,
                                error=None,
                                error_type=None,
                                timestamp=time.time(),
                                raw_response=response if isinstance(response, dict) else None
                            )
                        elif status_result.status == OrderStatus.PARTIALLY_FILLED:
                            print(f"  ⚠️  Partial: {status_result.filled_size:.2f} filled")
                        elif status_result.status == OrderStatus.CANCELLED:
                            print(f"  ❌ Order was cancelled")
                            return OrderResult(
                                success=False,
                                order_id=str(order_id),
                                status=OrderStatus.CANCELLED,
                                filled_size=0,
                                filled_price=order_price,
                                remaining_size=size,
                                error='Order cancelled',
                                error_type='cancelled',
                                timestamp=time.time(),
                                raw_response=None
                            )
                        
                        time.sleep(0.3)
                    
                    # Timeout - check final status
                    final_status = self.get_order_status(str(order_id))
                    if final_status.filled_size > 0:
                        fill_pct = (final_status.filled_size / size_in_tokens) * 100
                        print(f"  ⚠️  Timeout with {fill_pct:.1f}% filled")
                        return OrderResult(
                            success=final_status.filled_size >= size_in_tokens * 0.95,  # 95%+ = success
                            order_id=str(order_id),
                            status=OrderStatus.PARTIALLY_FILLED if final_status.filled_size < size_in_tokens else OrderStatus.FILLED,
                            filled_size=final_status.filled_size,
                            filled_price=order_price,
                            remaining_size=size_in_tokens - final_status.filled_size,
                            error='Timeout - partial fill' if final_status.filled_size < size_in_tokens else None,
                            error_type='partial_fill' if final_status.filled_size < size_in_tokens else None,
                            timestamp=time.time(),
                            raw_response=None
                        )
                    else:
                        print(f"  ❌ Order not filled after {fill_timeout}s")
                        return OrderResult(
                            success=False,
                            order_id=str(order_id),
                            status=OrderStatus.LIVE,
                            filled_size=0,
                            filled_price=order_price,
                            remaining_size=size,
                            error=f'Order not filled after {fill_timeout}s - still live',
                            error_type='no_fill',
                            timestamp=time.time(),
                            raw_response=response if isinstance(response, dict) else None
                        )
                
                # No wait for fill - return immediately
                return OrderResult(
                    success=True,
                    order_id=str(order_id),
                    status=OrderStatus.LIVE,
                    filled_size=0,
                    filled_price=order_price,
                    remaining_size=size,
                    error=None,
                    error_type=None,
                    timestamp=time.time(),
                    raw_response=response if isinstance(response, dict) else None
                )
            else:
                print(f"\n⚠️  Order may have been placed but no ID returned")
                return OrderResult(
                    success=False,  # Changed to False - can't verify without ID
                    order_id=None,
                    status=OrderStatus.UNKNOWN,
                    filled_size=0,
                    filled_price=order_price,
                    remaining_size=size,
                    error='No order ID returned',
                    error_type='no_order_id',
                    timestamp=time.time(),
                    raw_response=response if isinstance(response, dict) else None
                )

        except Exception as e:
            print(f"\n❌ Order execution failed: {e}")
            return OrderResult(
                success=False,
                order_id=None,
                status=OrderStatus.UNKNOWN,
                filled_size=0,
                filled_price=max_price or 0,
                remaining_size=size,
                error=str(e),
                error_type='execution_error',
                timestamp=time.time(),
                raw_response=None
            )

    def get_order_status(self, order_id: str) -> OrderResult:
        """
        Check status of an order.
        
        NEW: Actually fetches order status from API.
        """
        try:
            # Try to get order from API
            result = self.client.get_order(order_id)
            
            if result:
                status_str = result.get('status', 'unknown').lower()
                status_map = {
                    'live': OrderStatus.LIVE,
                    'open': OrderStatus.LIVE,
                    'filled': OrderStatus.FILLED,
                    'matched': OrderStatus.FILLED,
                    'partially_filled': OrderStatus.PARTIALLY_FILLED,
                    'cancelled': OrderStatus.CANCELLED,
                    'expired': OrderStatus.EXPIRED,
                }
                status = status_map.get(status_str, OrderStatus.UNKNOWN)
                
                size_matched = float(result.get('size_matched', 0))
                original_size = float(result.get('original_size', 0))
                remaining = original_size - size_matched
                
                return OrderResult(
                    success=True,
                    order_id=order_id,
                    status=status,
                    filled_size=size_matched,
                    filled_price=float(result.get('price', 0)),
                    remaining_size=remaining,
                    error=None,
                    error_type=None,
                    timestamp=time.time(),
                    raw_response=result
                )
            
            return OrderResult(
                success=False,
                order_id=order_id,
                status=OrderStatus.UNKNOWN,
                filled_size=0,
                filled_price=0,
                remaining_size=0,
                error='Order not found',
                error_type='not_found',
                timestamp=time.time(),
                raw_response=None
            )
            
        except Exception as e:
            return OrderResult(
                success=False,
                order_id=order_id,
                status=OrderStatus.UNKNOWN,
                filled_size=0,
                filled_price=0,
                remaining_size=0,
                error=str(e),
                error_type='api_error',
                timestamp=time.time(),
                raw_response=None
            )

    def cancel_order(self, order_id: str) -> Tuple[bool, str]:
        """
        Cancel an open order.
        
        NEW: Actually cancels via API with status return.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            print(f"  Cancelling order: {order_id}")
            
            result = self.client.cancel(order_id)
            
            if result:
                print(f"  ✓ Order cancelled successfully")
                return True, "Order cancelled"
            else:
                return False, "Cancel returned no result"
                
        except Exception as e:
            error_msg = str(e)
            print(f"  ❌ Failed to cancel order: {error_msg}")
            
            # Check if already filled or cancelled
            if 'not found' in error_msg.lower():
                return False, "Order not found - may already be filled"
            if 'already' in error_msg.lower():
                return False, "Order already cancelled or filled"
            
            return False, error_msg

    def cancel_all_orders(self) -> Tuple[int, int]:
        """
        Cancel all open orders.
        
        Returns:
            Tuple of (cancelled_count, failed_count)
        """
        try:
            result = self.client.cancel_all()
            
            cancelled = result.get('canceled', []) if result else []
            failed = result.get('not_canceled', []) if result else []
            
            print(f"  Cancelled: {len(cancelled)}, Failed: {len(failed)}")
            return len(cancelled), len(failed)
            
        except Exception as e:
            print(f"  Error cancelling all orders: {e}")
            return 0, 0

    def rollback_order(self, order_id: str, timeout: float = 10.0) -> bool:
        """
        Attempt to rollback/cancel an order.
        
        NEW: Used for partial execution recovery.
        
        Args:
            order_id: Order to cancel
            timeout: Max time to wait for cancellation
            
        Returns:
            True if successfully cancelled/rolled back
        """
        print(f"\n🔄 Attempting rollback for order {order_id}...")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Check current status
            status = self.get_order_status(order_id)
            
            if status.status == OrderStatus.CANCELLED:
                print(f"  ✓ Order already cancelled")
                return True
            
            if status.status == OrderStatus.FILLED:
                print(f"  ⚠️  Order already filled - cannot rollback")
                return False
            
            if status.status in [OrderStatus.LIVE, OrderStatus.PARTIALLY_FILLED]:
                # Attempt cancel
                success, msg = self.cancel_order(order_id)
                if success:
                    return True
                
                # If partial fill, still try to cancel remaining
                if status.status == OrderStatus.PARTIALLY_FILLED:
                    print(f"  ⚠️  Partial fill: {status.filled_size} filled, trying to cancel remaining")
            
            time.sleep(0.5)
        
        print(f"  ❌ Rollback timed out after {timeout}s")
        return False

    def execute_arbitrage_leg(
        self,
        outcome_name: str,
        stake: float,
        expected_odds: float,
        market_id: str = None,
        token_id: str = None
    ) -> Dict:
        """Execute the Polymarket leg of an arbitrage trade"""
        try:
            print(f"\n{'='*60}")
            print(f"POLYMARKET EXECUTION")
            print(f"{'='*60}")
            print(f"Outcome: {outcome_name}")
            print(f"Stake: ${stake:.2f}")
            print(f"Expected odds: {expected_odds:.3f}")

            expected_prob = 1.0 / expected_odds
            print(f"Expected probability: {expected_prob:.4f}")

            if stake <= 0:
                raise ValueError(f"Invalid stake: ${stake}")

            if stake > 2000:
                raise ValueError(f"Stake too large: ${stake} (max $2000)")

            if expected_prob < 0.01 or expected_prob > 0.99:
                raise ValueError(f"Invalid probability: {expected_prob}")

            if not market_id or not token_id:
                print("\n⚠️  SIMULATION MODE (no market/token ID)")
                return {
                    'success': True,
                    'simulated': True,
                    'order_id': f'sim_{int(time.time())}',
                    'filled_size': stake,
                    'filled_price': expected_prob,
                    'timestamp': time.time()
                }
            
                result = self.execute_market_order(
                    market_id=market_id,
                    token_id=token_id,
                    side="BUY",
                    size=stake,
                max_price=expected_prob * 1.02
                )

            if result['success']:
                print(f"\n✓ Polymarket order executed!")
                print(f"  Order ID: {result.get('order_id')}")
            else:
                print(f"\n❌ Execution failed: {result.get('error')}")

            return result

        except Exception as e:
            print(f"\n❌ Execution error: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': time.time()
            }
