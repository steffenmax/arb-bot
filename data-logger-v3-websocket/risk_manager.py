"""
Risk Manager and Position Sizing Logic

Enforces risk limits and calculates appropriate position sizes for Dutch Book arbitrage.
Prevents the bot from taking on excessive risk.

Key functions:
1. Per-trade position sizing (based on combined cost for Dutch Book)
2. Portfolio-level exposure limits
3. Per-event position limits
4. Dynamic sizing based on confidence
5. Kill switch for emergency shutdown

Dutch Book Note:
- For Dutch Book, we buy two complementary outcomes
- Combined cost = Kalshi ask + Polymarket ask
- Profit is guaranteed if combined cost < $1.00
- Risk is that one leg fails to fill (leaves directional position)
"""

import threading
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class RiskLimits:
    """Risk limit configuration"""
    # Per-trade limits
    max_trade_size_usd: float = 100  # Max $100 per leg
    min_trade_size_usd: float = 50   # Min $50 per leg
    
    # Portfolio limits
    max_total_exposure_usd: float = 500  # Max $500 total exposure
    max_event_exposure_usd: float = 200  # Max $200 per event
    
    # Risk controls
    max_unhedged_time_s: float = 30  # Max 30s unhedged
    min_edge_bps: int = 100  # Min 1% edge required
    max_slippage_bps: int = 200  # Max 2% slippage
    
    # Confidence thresholds
    min_confidence: str = "Medium"  # Minimum confidence to trade
    min_fill_probability: float = 0.30  # Min 30% combined fill prob
    
    # Operational limits
    max_trades_per_hour: int = 20
    max_consecutive_losses: int = 5
    
    # Kill switch
    enabled: bool = True
    max_daily_loss_usd: float = 200  # Stop trading if down $200


class RiskManager:
    """
    Manage risk and position sizing
    
    Acts as gatekeeper for all trades - must approve before execution.
    """
    
    def __init__(self, limits: Optional[RiskLimits] = None):
        """
        Initialize risk manager
        
        Args:
            limits: RiskLimits configuration
        """
        self.limits = limits or RiskLimits()
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Trading state
        self.trading_enabled = True
        self.kill_switch_triggered = False
        
        # Tracking
        self.trades_this_hour = 0
        self.last_hour_reset = time.time()
        self.consecutive_losses = 0
        self.daily_pnl = 0
        self.last_daily_reset = time.time()
        
        # Statistics
        self.total_trades = 0
        self.trades_approved = 0
        self.trades_rejected = 0
        self.rejection_reasons = {}
        
        print(f"✓ Risk manager initialized")
        print(f"  Max trade size: ${self.limits.max_trade_size_usd}")
        print(f"  Max exposure: ${self.limits.max_total_exposure_usd}")
        print(f"  Min edge: {self.limits.min_edge_bps}bps")
    
    def check_trade_approval(
        self,
        opportunity_dict: Dict,
        current_exposure: Dict,
        inventory_tracker
    ) -> Tuple[bool, str, float]:
        """
        Check if trade should be approved
        
        Args:
            opportunity_dict: Dict with opportunity details
            current_exposure: Current portfolio exposure
            inventory_tracker: InventoryTracker instance
        
        Returns:
            Tuple of (approved: bool, reason: str, recommended_size: float)
        """
        with self.lock:
            self.total_trades += 1
            
            # Reset hourly counter
            if time.time() - self.last_hour_reset > 3600:
                self.trades_this_hour = 0
                self.last_hour_reset = time.time()
            
            # Reset daily P&L
            if time.time() - self.last_daily_reset > 86400:
                self.daily_pnl = 0
                self.last_daily_reset = time.time()
            
            # Check 1: Kill switch
            if self.kill_switch_triggered:
                self._reject("Kill switch activated")
                return False, "Kill switch activated", 0
            
            # Check 2: Trading enabled
            if not self.trading_enabled or not self.limits.enabled:
                self._reject("Trading disabled")
                return False, "Trading disabled", 0
            
            # Check 3: Daily loss limit
            if self.daily_pnl < -self.limits.max_daily_loss_usd:
                self._trigger_kill_switch("Daily loss limit exceeded")
                return False, "Daily loss limit exceeded", 0
            
            # Check 4: Consecutive losses
            if self.consecutive_losses >= self.limits.max_consecutive_losses:
                self._reject("Too many consecutive losses")
                return False, f"Consecutive losses: {self.consecutive_losses}", 0
            
            # Check 5: Trades per hour
            if self.trades_this_hour >= self.limits.max_trades_per_hour:
                self._reject("Hourly trade limit reached")
                return False, "Hourly trade limit reached", 0
            
            # Check 6: Minimum edge
            edge_bps = opportunity_dict.get('edge_bps', 0)
            if edge_bps < self.limits.min_edge_bps:
                self._reject("Insufficient edge")
                return False, f"Edge {edge_bps}bps < min {self.limits.min_edge_bps}bps", 0
            
            # Check 7: Maximum slippage
            total_slippage = opportunity_dict.get('total_slippage_bps', 0)
            if total_slippage > self.limits.max_slippage_bps:
                self._reject("Excessive slippage")
                return False, f"Slippage {total_slippage}bps > max {self.limits.max_slippage_bps}bps", 0
            
            # Check 8: Confidence level
            # "Medium-Override" is treated as equivalent to "Medium" (edge-adjusted upgrade)
            confidence = opportunity_dict.get('confidence', 'Low')
            confidence_rank = {
                'Low': 0, 
                'Medium': 1, 
                'Medium-Override': 1,  # Edge-adjusted override treated as Medium
                'High': 2
            }
            min_confidence_rank = confidence_rank.get(self.limits.min_confidence, 1)
            actual_confidence_rank = confidence_rank.get(confidence, 0)
            
            if actual_confidence_rank < min_confidence_rank:
                self._reject("Low confidence")
                return False, f"Confidence {confidence} < {self.limits.min_confidence}", 0
            
            # Check 9: Fill probability
            combined_p_fill = opportunity_dict.get('combined_p_fill', 0)
            if combined_p_fill < self.limits.min_fill_probability:
                self._reject("Low fill probability")
                return False, f"Fill prob {combined_p_fill:.1%} < {self.limits.min_fill_probability:.1%}", 0
            
            # Check 10: Portfolio exposure limits
            current_total_exposure = current_exposure.get('total_gross_exposure', 0)
            # Dutch Book uses total_cost (both legs), fallback to buy_cost for compatibility
            proposed_size_usd = opportunity_dict.get('total_cost', opportunity_dict.get('buy_cost', 0))
            
            if current_total_exposure + proposed_size_usd > self.limits.max_total_exposure_usd:
                self._reject("Portfolio exposure limit")
                return False, "Would exceed portfolio exposure limit", 0
            
            # Check 11: Event exposure limits
            event_id = opportunity_dict.get('event_id')
            event_exposure = inventory_tracker.get_event_exposure(event_id)
            
            if abs(event_exposure.net_position) + proposed_size_usd > self.limits.max_event_exposure_usd:
                self._reject("Event exposure limit")
                return False, "Would exceed event exposure limit", 0
            
            # Calculate recommended size
            recommended_size = self._calculate_position_size(
                opportunity_dict,
                current_exposure,
                event_exposure
            )
            
            if recommended_size < self.limits.min_trade_size_usd:
                self._reject("Size too small")
                return False, f"Recommended size ${recommended_size:.2f} < min ${self.limits.min_trade_size_usd}", 0
            
            # APPROVED
            self.trades_approved += 1
            self.trades_this_hour += 1
            
            return True, "Approved", recommended_size
    
    def _calculate_position_size(
        self,
        opportunity: Dict,
        current_exposure: Dict,
        event_exposure
    ) -> float:
        """
        Calculate appropriate position size based on:
        1. Edge size (bigger edge = bigger size)
        2. Confidence (higher confidence = bigger size)
        3. Fill probability (higher prob = bigger size)
        4. Current exposure (less room = smaller size)
        """
        # Base size from limits
        base_size = self.limits.max_trade_size_usd
        
        # Adjust for edge (scale 0.5x to 1.0x based on edge)
        edge_bps = opportunity.get('edge_bps', 100)
        edge_factor = min(1.0, 0.5 + (edge_bps - self.limits.min_edge_bps) / 200)
        
        # Adjust for confidence
        confidence = opportunity.get('confidence', 'Medium')
        confidence_factor = {'Low': 0.5, 'Medium': 0.75, 'High': 1.0}.get(confidence, 0.75)
        
        # Adjust for fill probability
        fill_prob = opportunity.get('combined_p_fill', 0.5)
        fill_factor = min(1.0, fill_prob * 1.5)  # Scale up to 1.0 at 67% fill prob
        
        # Adjust for current exposure
        current_total = current_exposure.get('total_gross_exposure', 0)
        exposure_remaining = self.limits.max_total_exposure_usd - current_total
        exposure_factor = min(1.0, exposure_remaining / self.limits.max_total_exposure_usd)
        
        # Combined size
        recommended_size = base_size * edge_factor * confidence_factor * fill_factor * exposure_factor
        
        # Clamp to limits
        recommended_size = max(
            self.limits.min_trade_size_usd,
            min(recommended_size, self.limits.max_trade_size_usd)
        )
        
        return recommended_size
    
    def record_trade_outcome(self, pnl: float, success: bool):
        """
        Record trade outcome for risk tracking
        
        Args:
            pnl: P&L from trade
            success: Whether trade was successful
        """
        with self.lock:
            self.daily_pnl += pnl
            
            if success and pnl > 0:
                self.consecutive_losses = 0
            elif not success or pnl < 0:
                self.consecutive_losses += 1
    
    def _reject(self, reason: str):
        """Record trade rejection"""
        self.trades_rejected += 1
        self.rejection_reasons[reason] = self.rejection_reasons.get(reason, 0) + 1
    
    def _trigger_kill_switch(self, reason: str):
        """Trigger emergency kill switch"""
        self.kill_switch_triggered = True
        self.trading_enabled = False
        print(f"\n{'!'*60}")
        print(f"KILL SWITCH TRIGGERED: {reason}")
        print(f"{'!'*60}\n")
    
    def reset_kill_switch(self):
        """Reset kill switch (manual intervention)"""
        with self.lock:
            self.kill_switch_triggered = False
            self.trading_enabled = True
            self.consecutive_losses = 0
            print("✓ Kill switch reset - trading enabled")
    
    def pause_trading(self):
        """Pause trading temporarily"""
        with self.lock:
            self.trading_enabled = False
            print("⏸️  Trading paused")
    
    def resume_trading(self):
        """Resume trading"""
        with self.lock:
            if not self.kill_switch_triggered:
                self.trading_enabled = True
                print("▶️  Trading resumed")
    
    def update_limits(self, **kwargs):
        """Update risk limits"""
        with self.lock:
            for key, value in kwargs.items():
                if hasattr(self.limits, key):
                    setattr(self.limits, key, value)
                    print(f"✓ Updated {key} = {value}")
    
    def get_stats(self) -> Dict:
        """Get risk manager statistics"""
        with self.lock:
            approval_rate = (self.trades_approved / self.total_trades * 100) if self.total_trades > 0 else 0
            
            return {
                'trading_enabled': self.trading_enabled,
                'kill_switch_triggered': self.kill_switch_triggered,
                'total_trades_evaluated': self.total_trades,
                'trades_approved': self.trades_approved,
                'trades_rejected': self.trades_rejected,
                'approval_rate_pct': approval_rate,
                'trades_this_hour': self.trades_this_hour,
                'consecutive_losses': self.consecutive_losses,
                'daily_pnl': self.daily_pnl,
                'rejection_reasons': self.rejection_reasons.copy(),
                'limits': {
                    'max_trade_size_usd': self.limits.max_trade_size_usd,
                    'max_total_exposure_usd': self.limits.max_total_exposure_usd,
                    'min_edge_bps': self.limits.min_edge_bps,
                    'max_consecutive_losses': self.limits.max_consecutive_losses,
                    'max_daily_loss_usd': self.limits.max_daily_loss_usd
                }
            }
    
    def get_current_state(self) -> Dict:
        """Get current risk state for monitoring"""
        with self.lock:
            return {
                'enabled': self.trading_enabled,
                'kill_switch': self.kill_switch_triggered,
                'trades_today': self.trades_this_hour,
                'daily_pnl': self.daily_pnl,
                'consecutive_losses': self.consecutive_losses,
                'can_trade': self.trading_enabled and not self.kill_switch_triggered
            }


# Test/Example usage
def test_risk_manager():
    """Test the risk manager"""
    from inventory_tracker import InventoryTracker
    
    # Create managers
    risk_mgr = RiskManager()
    inventory = InventoryTracker()
    
    print("\n" + "="*60)
    print("Test: Risk Manager")
    print("="*60)
    
    # Test 1: Good opportunity
    print("\n--- Test 1: Approve good opportunity ---")
    good_opp = {
        'event_id': 'test-event',
        'edge_bps': 150,
        'total_slippage_bps': 100,
        'confidence': 'High',
        'combined_p_fill': 0.6,
        'buy_cost': 80
    }
    
    approved, reason, size = risk_mgr.check_trade_approval(
        good_opp,
        {'total_gross_exposure': 0},
        inventory
    )
    
    print(f"Approved: {approved}")
    print(f"Reason: {reason}")
    print(f"Recommended size: ${size:.2f}")
    
    # Test 2: Low edge
    print("\n--- Test 2: Reject low edge ---")
    bad_opp = {
        'event_id': 'test-event-2',
        'edge_bps': 50,  # Below minimum
        'total_slippage_bps': 100,
        'confidence': 'High',
        'combined_p_fill': 0.6,
        'buy_cost': 80
    }
    
    approved, reason, size = risk_mgr.check_trade_approval(
        bad_opp,
        {'total_gross_exposure': 0},
        inventory
    )
    
    print(f"Approved: {approved}")
    print(f"Reason: {reason}")
    
    # Test 3: Exposure limit
    print("\n--- Test 3: Reject excessive exposure ---")
    approved, reason, size = risk_mgr.check_trade_approval(
        good_opp,
        {'total_gross_exposure': 500},  # Already at limit
        inventory
    )
    
    print(f"Approved: {approved}")
    print(f"Reason: {reason}")
    
    # Test 4: Record outcomes
    print("\n--- Test 4: Record trade outcomes ---")
    risk_mgr.record_trade_outcome(pnl=5.0, success=True)
    risk_mgr.record_trade_outcome(pnl=-2.0, success=False)
    risk_mgr.record_trade_outcome(pnl=-1.5, success=False)
    
    print(f"Daily P&L: ${risk_mgr.daily_pnl:.2f}")
    print(f"Consecutive losses: {risk_mgr.consecutive_losses}")
    
    # Test 5: Trigger kill switch
    print("\n--- Test 5: Test kill switch ---")
    risk_mgr._trigger_kill_switch("Test trigger")
    
    approved, reason, size = risk_mgr.check_trade_approval(
        good_opp,
        {'total_gross_exposure': 0},
        inventory
    )
    
    print(f"After kill switch - Approved: {approved}")
    print(f"Reason: {reason}")
    
    # Stats
    print("\n" + "="*60)
    stats = risk_mgr.get_stats()
    print("Stats:")
    for key, value in stats.items():
        if key != 'rejection_reasons' and key != 'limits':
            print(f"  {key}: {value}")
    print("="*60)


if __name__ == "__main__":
    test_risk_manager()

