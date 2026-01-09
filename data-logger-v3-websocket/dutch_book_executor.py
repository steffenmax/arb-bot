"""
Dutch Book Execution Engine

Executes Dutch Book arbitrage by simultaneously placing BUY orders on both venues:
- BUY Team A YES on Kalshi
- BUY Team B YES on Polymarket

Both legs are BUY orders (no selling). This is the only valid arbitrage strategy
for prediction markets since you cannot short-sell.

Key requirements:
1. Fast execution (<200ms for both legs)
2. Both legs must fill for guaranteed profit
3. If only one leg fills, position is directional (not arbitrage)
4. No "unwind" needed since both legs are buys (just hold until settlement)
"""

import asyncio
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inventory_tracker import InventoryTracker
from arb_detector import DutchBookOpportunity


@dataclass
class DutchBookResult:
    """Result of Dutch Book execution"""
    success: bool
    both_filled: bool
    
    # Kalshi leg
    kalshi_order_id: Optional[str]
    kalshi_fill_size: float
    kalshi_fill_price: float
    kalshi_team: str
    
    # Polymarket leg
    poly_order_id: Optional[str]
    poly_fill_size: float
    poly_fill_price: float
    poly_team: str
    
    # Combined
    combined_cost: float
    guaranteed_payout: float  # Always 1.0 per contract
    gross_profit: float
    fees: float
    net_profit: float
    
    execution_time_ms: float
    one_leg_only: bool  # True if only one leg filled (directional risk)
    error: Optional[str]
    reason: str


class DutchBookExecutor:
    """
    Execute Dutch Book arbitrage using simultaneous BUY orders on both venues
    
    Workflow:
    1. Receive DutchBookOpportunity (Team A on Kalshi, Team B on Polymarket)
    2. Simultaneously send BUY orders to both venues
    3. Monitor fills with tight timeout
    4. If both fill: guaranteed profit at settlement
    5. If one fills: directional position (hold or sell later)
    """
    
    def __init__(
        self,
        kalshi_executor,
        polymarket_executor,
        inventory_tracker: InventoryTracker,
        orderbook_manager=None,
        config: Optional[Dict] = None
    ):
        """
        Initialize Dutch Book executor
        
        Args:
            kalshi_executor: Kalshi order executor
            polymarket_executor: Polymarket order executor
            inventory_tracker: Position tracker
            orderbook_manager: OrderbookManager for pre-execution validation
            config: Configuration dict with:
                - execution_timeout_s: Max time to wait for both fills (default: 3)
                - max_price_slippage_bps: Max acceptable slippage (default: 100)
                - max_price_drift_bps: Max acceptable price drift before abort (default: 100)
                - max_profitable_combined_cost: Max combined cost for profitability (default: 0.94)
                - kalshi_fee_rate: Kalshi fee rate (default: 0.07)
                - polymarket_fee_rate: Polymarket fee rate (default: 0.02)
        """
        self.kalshi_executor = kalshi_executor
        self.polymarket_executor = polymarket_executor
        self.inventory_tracker = inventory_tracker
        self.orderbook_manager = orderbook_manager
        
        # Configuration
        default_config = {
            'execution_timeout_s': 3,
            'max_price_slippage_bps': 100,  # 1% max slippage per leg
            'max_price_drift_bps': 100,     # 1% max price drift before abort
            'max_profitable_combined_cost': 0.94,  # Must be under this for guaranteed profit
            'kalshi_fee_rate': 0.07,
            'polymarket_fee_rate': 0.02,
        }
        self.config = {**default_config, **(config or {})}
        
        # Statistics
        self.executions_attempted = 0
        self.executions_successful = 0
        self.executions_aborted = 0  # Pre-execution validation failures
        self.both_legs_filled = 0
        self.one_leg_only = 0
        self.total_profit = 0.0
        
        print(f"✓ Dutch Book executor initialized")
    
    async def execute_opportunity(
        self,
        opportunity: DutchBookOpportunity,
        market_info: Dict
    ) -> DutchBookResult:
        """
        Execute Dutch Book arbitrage
        
        Args:
            opportunity: Detected Dutch Book opportunity
            market_info: Market metadata
        
        Returns:
            DutchBookResult with execution details
        """
        self.executions_attempted += 1
        start_time = time.time()
        
        print(f"\n{'='*60}")
        print(f"DUTCH BOOK EXECUTION")
        print(f"{'='*60}")
        print(f"Event: {opportunity.event_id}")
        print(f"Strategy:")
        print(f"  BUY {opportunity.kalshi_team} YES on Kalshi @ ${opportunity.kalshi_vwap:.4f}")
        print(f"  BUY {opportunity.poly_team} YES on Polymarket @ ${opportunity.poly_vwap:.4f}")
        print(f"  Combined cost: ${opportunity.combined_cost:.4f} per contract")
        print(f"  Guaranteed payout: $1.00 per contract")
        print(f"Size: {opportunity.size:.2f} contracts")
        print(f"Expected net profit: ${opportunity.net_edge:.2f} ({opportunity.edge_bps}bps)")
        
        # Calculate price limits with slippage
        max_slippage = self.config['max_price_slippage_bps'] / 10000
        kalshi_limit = opportunity.kalshi_vwap * (1 + max_slippage)
        poly_limit = opportunity.poly_vwap * (1 + max_slippage)
        
        print(f"\nPrice limits (with {max_slippage:.1%} slippage buffer):")
        print(f"  Kalshi max: ${kalshi_limit:.4f}")
        print(f"  Polymarket max: ${poly_limit:.4f}")
        
        # ============================================================
        # PRE-EXECUTION VALIDATION: Verify prices haven't moved
        # ============================================================
        print(f"\n--- Pre-Execution Validation ---")
        
        validation_result = self._validate_opportunity_freshness(opportunity, market_info)
        
        if not validation_result['valid']:
            # Abort execution
            self.executions_aborted += 1
            execution_time = (time.time() - start_time) * 1000
            
            print(f"❌ EXECUTION ABORTED: {validation_result['reason']}")
            print(f"  Kalshi: ${opportunity.kalshi_vwap:.4f} → ${validation_result.get('kalshi_current', 0):.4f} ({validation_result.get('kalshi_drift_bps', 0):.0f}bps drift)")
            print(f"  Poly:   ${opportunity.poly_vwap:.4f} → ${validation_result.get('poly_current', 0):.4f} ({validation_result.get('poly_drift_bps', 0):.0f}bps drift)")
            print(f"  Combined: ${validation_result.get('new_combined', 0):.4f}")
            print(f"{'='*60}\n")
            
            # Log aborted execution
            self._log_aborted_execution(
                event_id=opportunity.event_id,
                reason=validation_result['reason'],
                original_kalshi=opportunity.kalshi_vwap,
                original_poly=opportunity.poly_vwap,
                current_kalshi=validation_result.get('kalshi_current', 0),
                current_poly=validation_result.get('poly_current', 0),
                kalshi_drift_bps=validation_result.get('kalshi_drift_bps', 0),
                poly_drift_bps=validation_result.get('poly_drift_bps', 0)
            )
            
            return DutchBookResult(
                success=False,
                both_filled=False,
                kalshi_order_id=None,
                kalshi_fill_size=0,
                kalshi_fill_price=0,
                kalshi_team=opportunity.kalshi_team,
                poly_order_id=None,
                poly_fill_size=0,
                poly_fill_price=0,
                poly_team=opportunity.poly_team,
                combined_cost=0,
                guaranteed_payout=0,
                gross_profit=0,
                fees=0,
                net_profit=0,
                execution_time_ms=execution_time,
                one_leg_only=False,
                error=validation_result['reason'],
                reason=f"Pre-execution validation failed: {validation_result['reason']}"
            )
        
        print(f"✓ Validation passed - prices stable")
        print(f"  Kalshi drift: {validation_result.get('kalshi_drift_bps', 0):.0f}bps")
        print(f"  Poly drift: {validation_result.get('poly_drift_bps', 0):.0f}bps")
        print(f"  New combined: ${validation_result.get('new_combined', 0):.4f}")
        
        # Step 1: Submit both BUY orders simultaneously
        print(f"\n--- Step 1: Submit Both BUY Orders ---")
        
        kalshi_task = asyncio.create_task(
            self._execute_kalshi_buy(
                ticker=opportunity.kalshi_ticker,
                team=opportunity.kalshi_team,
                size=opportunity.size,
                limit_price=kalshi_limit,
                market_info=market_info
            )
        )
        
        poly_task = asyncio.create_task(
            self._execute_poly_buy(
                token_id=opportunity.poly_token_id,
                team=opportunity.poly_team,
                size=opportunity.size,
                limit_price=poly_limit,
                market_info=market_info
            )
        )
        
        # Wait for both with timeout
        try:
            kalshi_result, poly_result = await asyncio.wait_for(
                asyncio.gather(kalshi_task, poly_task),
                timeout=self.config['execution_timeout_s']
            )
        except asyncio.TimeoutError:
            print(f"⚠️  Execution timeout after {self.config['execution_timeout_s']}s")
            kalshi_result = kalshi_task.result() if kalshi_task.done() else {'filled': False}
            poly_result = poly_task.result() if poly_task.done() else {'filled': False}
        
        # Step 2: Analyze results
        print(f"\n--- Step 2: Analyze Fill Results ---")
        
        kalshi_filled = kalshi_result.get('filled', False)
        poly_filled = poly_result.get('filled', False)
        
        print(f"Kalshi {opportunity.kalshi_team}: {'✓ Filled' if kalshi_filled else '✗ Not filled'}")
        print(f"Polymarket {opportunity.poly_team}: {'✓ Filled' if poly_filled else '✗ Not filled'}")
        
        execution_time = (time.time() - start_time) * 1000
        
        # Case 1: BOTH FILLED - Dutch Book complete!
        if kalshi_filled and poly_filled:
            self.both_legs_filled += 1
            self.executions_successful += 1
            
            kalshi_cost = kalshi_result['size'] * kalshi_result['price']
            poly_cost = poly_result['size'] * poly_result['price']
            combined_cost = kalshi_cost + poly_cost
            
            # Use minimum size for guaranteed payout calculation
            min_size = min(kalshi_result['size'], poly_result['size'])
            guaranteed_payout = min_size * 1.0  # $1 per contract
            
            gross_profit = guaranteed_payout - combined_cost
            
            # Fee calculation: Different rates per venue, on WINNING LEG PROFIT only
            # - Kalshi: 7% on profit when Kalshi leg wins
            # - Polymarket: 2% on profit when Poly leg wins
            kalshi_fee_rate = self.config.get('kalshi_fee_rate', 0.07)
            poly_fee_rate = self.config.get('polymarket_fee_rate', 0.02)
            
            # Scenario 1: Kalshi team wins
            kalshi_profit = min_size * 1.0 - kalshi_cost
            kalshi_scenario_fee = kalshi_profit * kalshi_fee_rate
            kalshi_scenario_net = gross_profit - kalshi_scenario_fee
            
            # Scenario 2: Poly team wins
            poly_profit = min_size * 1.0 - poly_cost
            poly_scenario_fee = poly_profit * poly_fee_rate
            poly_scenario_net = gross_profit - poly_scenario_fee
            
            # Use worst case (minimum net profit)
            net_profit = min(kalshi_scenario_net, poly_scenario_net)
            total_fees = gross_profit - net_profit
            
            self.total_profit += net_profit
            
            # Record positions
            self.inventory_tracker.record_fill(
                event_id=opportunity.event_id,
                platform='kalshi',
                outcome=opportunity.kalshi_team,
                size=kalshi_result['size'],
                price=kalshi_result['price'],
                is_buy=True
            )
            
            self.inventory_tracker.record_fill(
                event_id=opportunity.event_id,
                platform='polymarket',
                outcome=opportunity.poly_team,
                size=poly_result['size'],
                price=poly_result['price'],
                is_buy=True
            )
            
            print(f"\n✓ DUTCH BOOK COMPLETE - GUARANTEED PROFIT!")
            print(f"Combined cost: ${combined_cost:.2f}")
            print(f"Guaranteed payout: ${guaranteed_payout:.2f}")
            print(f"Gross profit: ${gross_profit:.2f}")
            print(f"Fees: ${total_fees:.2f}")
            print(f"Net profit: ${net_profit:.2f}")
            print(f"Execution time: {execution_time:.0f}ms")
            print(f"{'='*60}\n")
            
            return DutchBookResult(
                success=True,
                both_filled=True,
                kalshi_order_id=kalshi_result.get('order_id'),
                kalshi_fill_size=kalshi_result['size'],
                kalshi_fill_price=kalshi_result['price'],
                kalshi_team=opportunity.kalshi_team,
                poly_order_id=poly_result.get('order_id'),
                poly_fill_size=poly_result['size'],
                poly_fill_price=poly_result['price'],
                poly_team=opportunity.poly_team,
                combined_cost=combined_cost,
                guaranteed_payout=guaranteed_payout,
                gross_profit=gross_profit,
                fees=total_fees,
                net_profit=net_profit,
                execution_time_ms=execution_time,
                one_leg_only=False,
                error=None,
                reason="Dutch Book complete"
            )
        
        # Case 2: ONE LEG FILLED - Directional position
        elif kalshi_filled or poly_filled:
            self.one_leg_only += 1
            
            print(f"\n⚠️  ONE LEG ONLY - Directional position (not arbitrage)")
            
            # Record the filled leg
            if kalshi_filled:
                self.inventory_tracker.record_fill(
                    event_id=opportunity.event_id,
                    platform='kalshi',
                    outcome=opportunity.kalshi_team,
                    size=kalshi_result['size'],
                    price=kalshi_result['price'],
                    is_buy=True
                )
                print(f"  Holding: {kalshi_result['size']:.2f} {opportunity.kalshi_team} YES on Kalshi")
            
            if poly_filled:
                self.inventory_tracker.record_fill(
                    event_id=opportunity.event_id,
                    platform='polymarket',
                    outcome=opportunity.poly_team,
                    size=poly_result['size'],
                    price=poly_result['price'],
                    is_buy=True
                )
                print(f"  Holding: {poly_result['size']:.2f} {opportunity.poly_team} YES on Polymarket")
            
            print(f"{'='*60}\n")
            
            return DutchBookResult(
                success=False,
                both_filled=False,
                kalshi_order_id=kalshi_result.get('order_id') if kalshi_filled else None,
                kalshi_fill_size=kalshi_result.get('size', 0) if kalshi_filled else 0,
                kalshi_fill_price=kalshi_result.get('price', 0) if kalshi_filled else 0,
                kalshi_team=opportunity.kalshi_team,
                poly_order_id=poly_result.get('order_id') if poly_filled else None,
                poly_fill_size=poly_result.get('size', 0) if poly_filled else 0,
                poly_fill_price=poly_result.get('price', 0) if poly_filled else 0,
                poly_team=opportunity.poly_team,
                combined_cost=0,
                guaranteed_payout=0,
                gross_profit=0,
                fees=0,
                net_profit=0,
                execution_time_ms=execution_time,
                one_leg_only=True,
                error="Only one leg filled",
                reason="Directional position - hold until settlement or sell"
            )
        
        # Case 3: NEITHER FILLED - Clean miss
        else:
            print(f"\n✗ NEITHER LEG FILLED - No position taken")
            print(f"{'='*60}\n")
            
            return DutchBookResult(
                success=False,
                both_filled=False,
                kalshi_order_id=None,
                kalshi_fill_size=0,
                kalshi_fill_price=0,
                kalshi_team=opportunity.kalshi_team,
                poly_order_id=None,
                poly_fill_size=0,
                poly_fill_price=0,
                poly_team=opportunity.poly_team,
                combined_cost=0,
                guaranteed_payout=0,
                gross_profit=0,
                fees=0,
                net_profit=0,
                execution_time_ms=execution_time,
                one_leg_only=False,
                error="Neither leg filled",
                reason="Clean miss - opportunity gone"
            )
    
    async def _execute_kalshi_buy(
        self,
        ticker: str,
        team: str,
        size: float,
        limit_price: float,
        market_info: Dict
    ) -> Dict:
        """Execute Kalshi BUY order"""
        try:
            print(f"  Submitting Kalshi BUY: {size:.2f} {team} @ ${limit_price:.4f}")
            
            price_cents = int(limit_price * 100)
            
            result = self.kalshi_executor.execute_order(
                ticker=ticker,
                side="yes",  # Always buying YES
                quantity=int(size),
                price_cents=price_cents,
                order_type="limit",
                wait_for_fill=True,
                fill_timeout=self.config['execution_timeout_s']
            )
            
            if result.success and result.filled_quantity > 0:
                print(f"  ✓ Kalshi filled: {result.filled_quantity} @ ${result.filled_price:.4f}")
                return {
                    'filled': True,
                    'size': result.filled_quantity,
                    'price': result.filled_price,
                    'order_id': result.order_id
                }
            else:
                print(f"  ✗ Kalshi not filled: {result.error}")
                return {'filled': False, 'error': result.error}
        
        except Exception as e:
            print(f"  ✗ Kalshi error: {e}")
            return {'filled': False, 'error': str(e)}
    
    async def _execute_poly_buy(
        self,
        token_id: str,
        team: str,
        size: float,
        limit_price: float,
        market_info: Dict
    ) -> Dict:
        """Execute Polymarket BUY order"""
        try:
            print(f"  Submitting Polymarket BUY: {size:.2f} {team} @ ${limit_price:.4f}")
            
            result = self.polymarket_executor.execute_order(
                market_id=market_info.get('poly_condition_id', ''),
                token_id=token_id,
                side="BUY",  # Always buying
                size=size,
                max_price=limit_price,
                wait_for_fill=True,
                fill_timeout=self.config['execution_timeout_s']
            )
            
            if result.success and result.filled_size > 0:
                print(f"  ✓ Polymarket filled: {result.filled_size:.2f} @ ${result.filled_price:.4f}")
                return {
                    'filled': True,
                    'size': result.filled_size,
                    'price': result.filled_price,
                    'order_id': result.order_id
                }
            else:
                print(f"  ✗ Polymarket not filled: {result.error}")
                return {'filled': False, 'error': result.error}
        
        except Exception as e:
            print(f"  ✗ Polymarket error: {e}")
            return {'filled': False, 'error': str(e)}
    
    def _validate_opportunity_freshness(
        self,
        opportunity: DutchBookOpportunity,
        market_info: Dict
    ) -> Dict:
        """
        Validate that opportunity prices haven't moved significantly.
        
        Re-fetches current orderbook prices and compares against opportunity.
        
        Args:
            opportunity: The detected opportunity
            market_info: Market metadata
        
        Returns:
            Dict with:
                - valid: bool - True if safe to proceed
                - reason: str - Reason if invalid
                - kalshi_current: float - Current Kalshi ask
                - poly_current: float - Current Poly ask
                - kalshi_drift_bps: float - Price drift in bps
                - poly_drift_bps: float - Price drift in bps
                - new_combined: float - New combined cost
        """
        result = {
            'valid': True,
            'reason': '',
            'kalshi_current': 0,
            'poly_current': 0,
            'kalshi_drift_bps': 0,
            'poly_drift_bps': 0,
            'new_combined': 0
        }
        
        # If no orderbook_manager, skip validation (paper trading or testing)
        if not self.orderbook_manager:
            result['kalshi_current'] = opportunity.kalshi_vwap
            result['poly_current'] = opportunity.poly_vwap
            result['new_combined'] = opportunity.combined_cost
            return result
        
        max_drift_bps = self.config.get('max_price_drift_bps', 100)
        max_combined = self.config.get('max_profitable_combined_cost', 0.94)
        
        try:
            # Get current Kalshi best ask
            kalshi_key = f"kalshi:{opportunity.kalshi_ticker}"
            kalshi_book = self.orderbook_manager.get_orderbook(kalshi_key, 'kalshi')
            kalshi_asks = kalshi_book.get('asks', [])
            
            if not kalshi_asks:
                result['valid'] = False
                result['reason'] = 'kalshi_no_asks'
                return result
            
            kalshi_current = kalshi_asks[0][0]
            result['kalshi_current'] = kalshi_current
            
            # Get current Polymarket best ask
            poly_key = f"{opportunity.event_id}:polymarket:{opportunity.poly_team}"
            poly_book = self.orderbook_manager.get_orderbook(poly_key, 'polymarket')
            poly_asks = poly_book.get('asks', [])
            
            if not poly_asks:
                result['valid'] = False
                result['reason'] = 'poly_no_asks'
                return result
            
            poly_current = poly_asks[0][0]
            result['poly_current'] = poly_current
            
            # Calculate drift
            if opportunity.kalshi_vwap > 0:
                kalshi_drift = abs(kalshi_current - opportunity.kalshi_vwap) / opportunity.kalshi_vwap
                result['kalshi_drift_bps'] = kalshi_drift * 10000
            
            if opportunity.poly_vwap > 0:
                poly_drift = abs(poly_current - opportunity.poly_vwap) / opportunity.poly_vwap
                result['poly_drift_bps'] = poly_drift * 10000
            
            # Check drift thresholds
            if result['kalshi_drift_bps'] > max_drift_bps:
                result['valid'] = False
                result['reason'] = f'kalshi_price_moved_{int(result["kalshi_drift_bps"])}bps'
                return result
            
            if result['poly_drift_bps'] > max_drift_bps:
                result['valid'] = False
                result['reason'] = f'poly_price_moved_{int(result["poly_drift_bps"])}bps'
                return result
            
            # Check combined cost still profitable
            new_combined = kalshi_current + poly_current
            result['new_combined'] = new_combined
            
            if new_combined > max_combined:
                result['valid'] = False
                result['reason'] = f'combined_cost_exceeded_{new_combined:.4f}'
                return result
            
            # All validations passed
            return result
            
        except Exception as e:
            result['valid'] = False
            result['reason'] = f'validation_error_{str(e)}'
            return result
    
    def _log_aborted_execution(
        self,
        event_id: str,
        reason: str,
        original_kalshi: float,
        original_poly: float,
        current_kalshi: float,
        current_poly: float,
        kalshi_drift_bps: float,
        poly_drift_bps: float
    ):
        """Log aborted execution to CSV file."""
        try:
            from pathlib import Path
            from datetime import datetime
            import csv
            
            log_file = Path("data/aborted_executions.csv")
            
            # Create file with headers if it doesn't exist
            if not log_file.exists():
                log_file.parent.mkdir(parents=True, exist_ok=True)
                with open(log_file, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        'timestamp', 'event_id', 'reason',
                        'original_kalshi', 'original_poly', 'original_combined',
                        'current_kalshi', 'current_poly', 'current_combined',
                        'kalshi_drift_bps', 'poly_drift_bps'
                    ])
            
            # Append aborted execution record
            original_combined = original_kalshi + original_poly
            current_combined = current_kalshi + current_poly
            
            with open(log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    event_id,
                    reason,
                    f"{original_kalshi:.4f}",
                    f"{original_poly:.4f}",
                    f"{original_combined:.4f}",
                    f"{current_kalshi:.4f}",
                    f"{current_poly:.4f}",
                    f"{current_combined:.4f}",
                    f"{kalshi_drift_bps:.0f}",
                    f"{poly_drift_bps:.0f}"
                ])
        except Exception as e:
            print(f"  ⚠️  Failed to log aborted execution: {e}")
    
    def get_stats(self) -> Dict:
        """Get executor statistics"""
        success_rate = (self.executions_successful / self.executions_attempted * 100) if self.executions_attempted > 0 else 0
        
        return {
            'executions_attempted': self.executions_attempted,
            'executions_successful': self.executions_successful,
            'executions_aborted': self.executions_aborted,
            'success_rate_pct': success_rate,
            'both_legs_filled': self.both_legs_filled,
            'one_leg_only': self.one_leg_only,
            'total_profit': self.total_profit,
            'config': self.config.copy()
        }


# Test
async def test_dutch_book_executor():
    """Test structure"""
    print("\n" + "="*60)
    print("Dutch Book Executor - Structure Test")
    print("="*60)
    print("\nThis executor:")
    print("  1. Takes a DutchBookOpportunity")
    print("  2. Places simultaneous BUY orders on both venues")
    print("  3. If both fill: guaranteed profit at settlement")
    print("  4. If one fills: directional position (hold/sell)")
    print("\nNo 'sell' or 'short' orders - only BUYING complementary outcomes!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(test_dutch_book_executor())

