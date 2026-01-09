"""
Kalshi Order Executor (v2.0 - IMPROVED)

Improvements:
1. Structured order results
2. Order status checking
3. Cancellation support for rollback
4. Better error handling
"""
import os
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from dotenv import load_dotenv
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.data_sources.kalshi_client import KalshiClient

load_dotenv()


class OrderStatus(Enum):
    """Order status enum"""
    PENDING = "pending"
    RESTING = "resting"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


@dataclass
class OrderResult:
    """Structured order result"""
    success: bool  # True if order filled successfully
    order_id: Optional[str]
    status: OrderStatus
    filled_quantity: int
    filled_price: float
    remaining_quantity: int
    error: Optional[str]
    error_type: Optional[str]
    timestamp: float
    raw_response: Optional[Dict]
    placed: bool = True  # True if order was submitted to exchange (even if not filled)
    
    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'placed': self.placed,  # NEW: indicates order was submitted
            'order_id': self.order_id,
            'status': self.status.value,
            'filled_quantity': self.filled_quantity,
            'filled_price': self.filled_price,
            'remaining_quantity': self.remaining_quantity,
            'error': self.error,
            'error_type': self.error_type,
            'timestamp': self.timestamp,
        }


class KalshiExecutor:
    """Execute trades on Kalshi (v2.0)"""

    def __init__(self):
        self.client = KalshiClient()
        print("✓ Kalshi executor initialized (v2.0)")

    def execute_market_order(
        self,
        ticker: str,
        side: str,
        quantity: int,
        yes_price: Optional[int] = None,
    ) -> Dict:
        """
        Execute a market order on Kalshi.
        
        Returns legacy Dict format for compatibility.
        """
        result = self.execute_order(
            ticker=ticker,
            side=side,
            quantity=quantity,
            price_cents=yes_price
        )
        return result.to_dict()

    def execute_order(
        self,
        ticker: str,
        side: str,
        quantity: int,
        price_cents: Optional[int] = None,
        order_type: str = "limit",
        wait_for_fill: bool = True,
        fill_timeout: float = 5.0
    ) -> OrderResult:
        """
        Execute an order on Kalshi with structured result.
        
        Args:
            ticker: Market ticker
            side: "yes" or "no"
            quantity: Number of contracts
            price_cents: Limit price in cents (1-99)
            order_type: "limit" or "market"
            wait_for_fill: If True, waits for order to fill before returning
            fill_timeout: Max seconds to wait for fill
            
        Returns:
            OrderResult with detailed execution info
        """
        try:
            print(f"\n⚡ Executing Kalshi order:")
            print(f"  Ticker: {ticker}")
            print(f"  Side: {side}")
            print(f"  Quantity: {quantity} contracts")
            if price_cents:
                print(f"  Price limit: {price_cents}¢")

            order_params = {
                "ticker": ticker,
                "action": "buy",
                "side": side,
                "type": order_type if price_cents else "market",
                "count": quantity
            }

            if price_cents:
                order_params["yes_price"] = price_cents

            result = self.client._make_request('POST', '/portfolio/orders', body=order_params)

            if result and 'order' in result:
                order = result['order']
                order_id = order.get('order_id')
                status_str = order.get('status', 'unknown').lower()
                
                status_map = {
                    'pending': OrderStatus.PENDING,
                    'resting': OrderStatus.RESTING,
                    'filled': OrderStatus.FILLED,
                    'canceled': OrderStatus.CANCELLED,
                    'cancelled': OrderStatus.CANCELLED,
                }
                status = status_map.get(status_str, OrderStatus.UNKNOWN)
                
                # Count BOTH taker and maker fills
                initial_filled = order.get('taker_fill_count', 0) + order.get('maker_fill_count', 0)
                
                print(f"✓ Order placed: {order_id}")
                print(f"  Status: {status_str}")
                print(f"  Initial fill: {initial_filled}/{quantity}")
                
                # CRITICAL FIX: Wait for fill if not immediately filled
                if wait_for_fill and initial_filled < quantity and status != OrderStatus.FILLED:
                    print(f"  Waiting for fill (max {fill_timeout}s)...")
                    start_time = time.time()
                    
                    while time.time() - start_time < fill_timeout:
                        status_result = self.get_order_status(order_id)
                        
                        if status_result.status == OrderStatus.FILLED:
                            print(f"  ✓ FILLED! Qty: {status_result.filled_quantity}")
                            return OrderResult(
                                success=True,
                                order_id=order_id,
                                status=OrderStatus.FILLED,
                                filled_quantity=status_result.filled_quantity,
                                filled_price=price_cents / 100 if price_cents else 0,
                                remaining_quantity=0,
                                error=None,
                                error_type=None,
                                timestamp=time.time(),
                                raw_response=result
                            )
                        elif status_result.filled_quantity > initial_filled:
                            print(f"  ⚠️  Progress: {status_result.filled_quantity}/{quantity}")
                            initial_filled = status_result.filled_quantity
                        elif status_result.status == OrderStatus.CANCELLED:
                            print(f"  ❌ Order cancelled")
                            return OrderResult(
                                success=False,
                                order_id=order_id,
                                status=OrderStatus.CANCELLED,
                                filled_quantity=status_result.filled_quantity,
                                filled_price=price_cents / 100 if price_cents else 0,
                                remaining_quantity=quantity - status_result.filled_quantity,
                                error='Order cancelled',
                                error_type='cancelled',
                                timestamp=time.time(),
                                raw_response=None
                            )
                        
                        time.sleep(0.3)
                    
                    # Timeout - check final status
                    final_status = self.get_order_status(order_id)
                    if final_status.filled_quantity > 0:
                        fill_pct = (final_status.filled_quantity / quantity) * 100
                        print(f"  ⚠️  Timeout with {fill_pct:.1f}% filled ({final_status.filled_quantity}/{quantity})")
                        return OrderResult(
                            success=final_status.filled_quantity >= quantity * 0.95,  # 95%+ = success
                            order_id=order_id,
                            status=OrderStatus.PARTIALLY_FILLED if final_status.filled_quantity < quantity else OrderStatus.FILLED,
                            filled_quantity=final_status.filled_quantity,
                            filled_price=price_cents / 100 if price_cents else 0,
                            remaining_quantity=quantity - final_status.filled_quantity,
                            error='Timeout - partial fill' if final_status.filled_quantity < quantity else None,
                            error_type='partial_fill' if final_status.filled_quantity < quantity else None,
                            timestamp=time.time(),
                            raw_response=None
                        )
                    else:
                        print(f"  ❌ Order not filled after {fill_timeout}s")
                        return OrderResult(
                            success=False,
                            order_id=order_id,
                            status=OrderStatus.RESTING,
                            filled_quantity=0,
                            filled_price=price_cents / 100 if price_cents else 0,
                            remaining_quantity=quantity,
                            error=f'Order not filled after {fill_timeout}s - still resting',
                            error_type='no_fill',
                            timestamp=time.time(),
                            raw_response=result
                        )
                
                # Immediate fill or no wait requested
                return OrderResult(
                    success=True,
                    order_id=order_id,
                    status=status,
                    filled_quantity=initial_filled,
                    filled_price=price_cents / 100 if price_cents else 0,
                    remaining_quantity=quantity - initial_filled,
                    error=None,
                    error_type=None,
                    timestamp=time.time(),
                    raw_response=result
                )
            else:
                error_msg = 'No response from Kalshi API'
                error_type = 'no_response'
                
                if result:
                    error_msg = result.get('error', result.get('message', 'Unknown error'))
                    error_type = result.get('error_code', 'api_error')
                    
                print(f"❌ Order failed: {error_msg}")
                
                return OrderResult(
                    success=False,
                    order_id=None,
                    status=OrderStatus.UNKNOWN,
                    filled_quantity=0,
                    filled_price=price_cents / 100 if price_cents else 0,
                    remaining_quantity=quantity,
                    error=error_msg,
                    error_type=error_type,
                    timestamp=time.time(),
                    raw_response=result
                )

        except Exception as e:
            print(f"❌ Execution error: {e}")
            return OrderResult(
                success=False,
                order_id=None,
                status=OrderStatus.UNKNOWN,
                filled_quantity=0,
                filled_price=price_cents / 100 if price_cents else 0,
                remaining_quantity=quantity,
                error=str(e),
                error_type='exception',
                timestamp=time.time(),
                raw_response=None,
                placed=False
            )

    def get_order_status(self, order_id: str) -> OrderResult:
        """
        Check status of an order.
        
        NEW: Actually fetches order status from API.
        """
        try:
            result = self.client._make_request('GET', f'/portfolio/orders/{order_id}')
            
            if result and 'order' in result:
                order = result['order']
                status_str = order.get('status', 'unknown').lower()
                
                status_map = {
                    'pending': OrderStatus.PENDING,
                    'resting': OrderStatus.RESTING,
                    'filled': OrderStatus.FILLED,
                    'canceled': OrderStatus.CANCELLED,
                    'cancelled': OrderStatus.CANCELLED,
                }
                status = status_map.get(status_str, OrderStatus.UNKNOWN)
                
                filled = order.get('taker_fill_count', 0) + order.get('maker_fill_count', 0)
                original = order.get('count', 0)
                
                return OrderResult(
                    success=True,
                    order_id=order_id,
                    status=status,
                    filled_quantity=filled,
                    filled_price=order.get('yes_price', 0) / 100 if order.get('yes_price') else 0,
                    remaining_quantity=original - filled,
                    error=None,
                    error_type=None,
                    timestamp=time.time(),
                    raw_response=result
                )
            
            return OrderResult(
                success=False,
                order_id=order_id,
                status=OrderStatus.UNKNOWN,
                filled_quantity=0,
                filled_price=0,
                remaining_quantity=0,
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
                filled_quantity=0,
                filled_price=0,
                remaining_quantity=0,
                error=str(e),
                error_type='api_error',
                timestamp=time.time(),
                raw_response=None
            )

    def cancel_order(self, order_id: str) -> Tuple[bool, str]:
        """
        Cancel an open order.
        
        NEW: Actually cancels via API.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            print(f"  Cancelling order: {order_id}")
            
            result = self.client._make_request('DELETE', f'/portfolio/orders/{order_id}')
            
            if result:
                # Check if cancellation was successful
                if result.get('order', {}).get('status') == 'canceled':
                    print(f"  ✓ Order cancelled successfully")
                    return True, "Order cancelled"
                else:
                    return True, "Cancel request sent"
            else:
                return False, "Cancel returned no result"
                
        except Exception as e:
            error_msg = str(e)
            print(f"  ❌ Failed to cancel order: {error_msg}")
            
            if 'not found' in error_msg.lower():
                return False, "Order not found - may already be filled"
            if 'already' in error_msg.lower():
                return False, "Order already cancelled or filled"
            
            return False, error_msg

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
        print(f"\n🔄 Attempting Kalshi rollback for order {order_id}...")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Check current status
            status = self.get_order_status(order_id)
            
            if status.status == OrderStatus.CANCELLED:
                print(f"  ✓ Order already cancelled")
                return True
            
            if status.status == OrderStatus.FILLED:
                print(f"  ⚠️  Order already filled - cannot rollback")
                print(f"  Filled: {status.filled_quantity} contracts")
                return False
            
            if status.status in [OrderStatus.RESTING, OrderStatus.PENDING]:
                success, msg = self.cancel_order(order_id)
                if success:
                    return True
                print(f"  Cancel attempt failed: {msg}")
            
            time.sleep(0.5)
        
        print(f"  ❌ Rollback timed out after {timeout}s")
        return False

    def execute_arbitrage_leg(
        self,
        outcome_name: str,
        stake: float,
        expected_odds: float,
        market_info: Optional[Dict] = None
    ) -> Dict:
        """Execute one leg of an arbitrage trade"""
        try:
            if not market_info:
                return {
                    'success': False,
                    'error': 'Market info required for Kalshi execution'
                }

            ticker = market_info.get('ticker')
            if not ticker:
                return {
                    'success': False,
                    'error': 'Market ticker not provided'
                }

            probability = 1 / expected_odds
            price_cents = int(probability * 100)
            quantity = int(stake / (price_cents / 100))

            print(f"\nCalculated Kalshi order:")
            print(f"  Stake: ${stake:.2f}")
            print(f"  Probability: {probability:.4f}")
            print(f"  Price: {price_cents}¢")
            print(f"  Quantity: {quantity} contracts")

            result = self.execute_market_order(
                ticker=ticker,
                side="yes",
                quantity=quantity,
                yes_price=price_cents
            )

            return result

        except Exception as e:
            print(f"❌ Error executing arbitrage leg: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_market_info(self, series_ticker: str, team_name: str, date: str) -> Optional[Dict]:
        """Get market information for a specific game"""
        try:
            result = self.client._make_request('GET', '/markets', params={
                'series_ticker': series_ticker,
                'status': 'open',
                'limit': 100
            })

            if not result or 'markets' not in result:
                return None

            for market in result['markets']:
                ticker = market.get('ticker', '')
                title = market.get('title', '').lower()

                if date.lower() in ticker.lower() and team_name.lower() in title:
                    return {
                        'ticker': ticker,
                        'title': market.get('title'),
                        'yes_bid': market.get('yes_bid'),
                        'yes_ask': market.get('yes_ask')
                    }

            return None

        except Exception as e:
            print(f"Error fetching market info: {e}")
            return None

    def get_open_orders(self) -> list:
        """Get all open orders"""
        try:
            result = self.client._make_request('GET', '/portfolio/orders', params={
                'status': 'resting'
            })
            
            if result and 'orders' in result:
                return result['orders']
            return []
        except Exception as e:
            print(f"Error fetching open orders: {e}")
            return []

    def cancel_all_orders(self) -> Tuple[int, int]:
        """
        Cancel all open orders.
        
        Returns:
            Tuple of (cancelled_count, failed_count)
        """
        orders = self.get_open_orders()
        cancelled = 0
        failed = 0
        
        for order in orders:
            order_id = order.get('order_id')
            if order_id:
                success, _ = self.cancel_order(order_id)
                if success:
                    cancelled += 1
                else:
                    failed += 1
        
        print(f"  Cancelled: {cancelled}, Failed: {failed}")
        return cancelled, failed
