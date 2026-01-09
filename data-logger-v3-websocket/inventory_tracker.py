"""
Inventory and Exposure Tracking System

Tracks positions and exposure across both venues to manage risk from partial fills.
Critical for avoiding "death by a thousand partial arbs".

Key features:
- Per-event position tracking
- Net exposure calculation
- Exposure limits enforcement
- Partial fill handling
- Position unwinding logic
"""

import threading
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict


@dataclass
class Position:
    """Position in a single outcome"""
    event_id: str
    platform: str  # 'kalshi' or 'polymarket'
    outcome: str  # Outcome name
    size: float  # Positive for long, negative for short
    avg_price: float  # Average entry price
    realized_pnl: float = 0  # Realized P&L from closed positions
    last_update: float = field(default_factory=time.time)
    
    def update(self, fill_size: float, fill_price: float):
        """Update position with new fill"""
        # Calculate new average price
        if self.size == 0:
            self.avg_price = fill_price
            self.size = fill_size
        else:
            if (self.size > 0 and fill_size > 0) or (self.size < 0 and fill_size < 0):
                # Adding to position
                total_cost = (self.size * self.avg_price) + (fill_size * fill_price)
                self.size += fill_size
                self.avg_price = total_cost / self.size if self.size != 0 else fill_price
            else:
                # Reducing or reversing position
                closed_size = min(abs(self.size), abs(fill_size))
                pnl_per_unit = fill_price - self.avg_price
                if self.size < 0:
                    pnl_per_unit = -pnl_per_unit
                self.realized_pnl += closed_size * pnl_per_unit
                self.size += fill_size
                
                if abs(self.size) < 0.01:  # Essentially flat
                    self.size = 0
                elif self.size * fill_size > 0:  # Reversed position
                    self.avg_price = fill_price
        
        self.last_update = time.time()


@dataclass
class EventExposure:
    """Net exposure for a single event across all platforms"""
    event_id: str
    net_position: float  # Net long/short across all platforms
    gross_position: float  # Sum of absolute positions
    platforms: Dict[str, float] = field(default_factory=dict)  # {platform: size}
    unrealized_pnl: float = 0
    timestamp: float = field(default_factory=time.time)


@dataclass
class DutchBookPosition:
    """
    Paired Dutch Book position tracking
    
    Represents holding complementary outcomes across venues:
    - Team A on Kalshi + Team B on Polymarket
    
    One of these positions WILL pay $1.00 at settlement.
    Profit is locked in at time of execution.
    """
    event_id: str
    created_at: float = field(default_factory=time.time)
    
    # Kalshi leg
    kalshi_team: str = ""
    kalshi_size: float = 0
    kalshi_price: float = 0
    kalshi_order_id: Optional[str] = None
    
    # Polymarket leg
    poly_team: str = ""
    poly_size: float = 0
    poly_price: float = 0
    poly_order_id: Optional[str] = None
    
    # Combined metrics
    combined_cost: float = 0          # Total cost paid for both legs
    expected_payout: float = 1.0      # Always $1.00 per contract
    locked_profit: float = 0          # Guaranteed profit (1.0 - combined_cost - fees)
    fees_paid: float = 0
    
    # Status
    is_complete: bool = False         # True if both legs filled
    is_settled: bool = False          # True after event resolution
    winning_team: Optional[str] = None
    settlement_pnl: Optional[float] = None
    
    def calculate_settlement_pnl(self, winner: str) -> float:
        """
        Calculate actual P&L after event resolution
        
        Args:
            winner: The team that won ('kalshi_team' or 'poly_team')
        
        Returns:
            Actual P&L based on which leg pays out
        """
        if winner == self.kalshi_team:
            # Kalshi leg pays $1.00 per contract
            payout = self.kalshi_size * 1.0
        elif winner == self.poly_team:
            # Polymarket leg pays $1.00 per contract
            payout = self.poly_size * 1.0
        else:
            # Unknown winner - shouldn't happen in binary market
            payout = 0
        
        # P&L = payout - cost - fees
        actual_pnl = payout - self.combined_cost - self.fees_paid
        return actual_pnl
    
    def mark_settled(self, winner: str):
        """Mark position as settled"""
        self.is_settled = True
        self.winning_team = winner
        self.settlement_pnl = self.calculate_settlement_pnl(winner)
    
    @property
    def min_size(self) -> float:
        """Minimum size across both legs (for guaranteed payout calc)"""
        return min(self.kalshi_size, self.poly_size)
    
    @property 
    def is_balanced(self) -> bool:
        """True if both legs have equal size (ideal for Dutch Book)"""
        return abs(self.kalshi_size - self.poly_size) < 0.01


class InventoryTracker:
    """
    Track inventory and exposure across both venues
    
    Manages positions to handle partial fills and prevent runaway exposure.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize inventory tracker
        
        Args:
            config: Configuration dict with:
                - max_event_exposure: Max net position per event (default: 200 contracts)
                - max_gross_exposure: Max total exposure across all events (default: 1000)
                - max_unhedged_time_s: Max time to hold unhedged position (default: 30s)
                - position_check_interval_s: How often to check positions (default: 5s)
        """
        default_config = {
            'max_event_exposure': 200,  # Max 200 contracts net per event
            'max_gross_exposure': 1000,  # Max 1000 contracts total
            'max_unhedged_time_s': 30,  # Max 30s unhedged
            'position_check_interval_s': 5,
        }
        self.config = {**default_config, **(config or {})}
        
        # Position tracking: {(event_id, platform, outcome): Position}
        self.positions = {}
        
        # Dutch Book position tracking: {event_id: [DutchBookPosition, ...]}
        self.dutch_book_positions: Dict[str, List[DutchBookPosition]] = {}
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Statistics
        self.total_fills = 0
        self.partial_fills = 0
        self.full_hedges = 0
        self.forced_unwinds = 0
        
        print(f"✓ Inventory tracker initialized (max exposure: {self.config['max_event_exposure']} per event)")
    
    def record_fill(
        self,
        event_id: str,
        platform: str,
        outcome: str,
        size: float,
        price: float,
        is_buy: bool
    ):
        """
        Record a fill (partial or complete)
        
        Args:
            event_id: Event identifier
            platform: 'kalshi' or 'polymarket'
            outcome: Outcome name
            size: Size filled
            price: Fill price
            is_buy: True if buying (long), False if selling (short)
        """
        with self.lock:
            # Adjust size for direction
            position_size = size if is_buy else -size
            
            # Get or create position
            key = (event_id, platform, outcome)
            if key not in self.positions:
                self.positions[key] = Position(
                    event_id=event_id,
                    platform=platform,
                    outcome=outcome,
                    size=0,
                    avg_price=0
                )
            
            # Update position
            self.positions[key].update(position_size, price)
            
            # Update statistics
            self.total_fills += 1
            
            # Remove position if flat
            if abs(self.positions[key].size) < 0.01:
                del self.positions[key]
    
    def get_event_exposure(self, event_id: str) -> EventExposure:
        """
        Calculate net exposure for an event
        
        Returns:
            EventExposure with net and gross positions
        """
        with self.lock:
            positions = [p for p in self.positions.values() if p.event_id == event_id]
            
            if not positions:
                return EventExposure(
                    event_id=event_id,
                    net_position=0,
                    gross_position=0,
                    platforms={}
                )
            
            # Calculate net position by platform
            platform_positions = defaultdict(float)
            for pos in positions:
                platform_positions[pos.platform] += pos.size
            
            # Net position across all platforms
            net_position = sum(platform_positions.values())
            
            # Gross position (sum of absolutes)
            gross_position = sum(abs(size) for size in platform_positions.values())
            
            # Calculate unrealized P&L (simplified - assumes current market price = entry price)
            unrealized_pnl = sum(p.realized_pnl for p in positions)
            
            return EventExposure(
                event_id=event_id,
                net_position=net_position,
                gross_position=gross_position,
                platforms=dict(platform_positions),
                unrealized_pnl=unrealized_pnl
            )
    
    def get_total_exposure(self) -> Dict:
        """
        Calculate total exposure across all events
        
        Returns:
            Dict with exposure metrics
        """
        with self.lock:
            total_gross = 0
            total_net = 0
            num_events = len(set(p.event_id for p in self.positions.values()))
            
            # Sum up exposure across events
            event_ids = set(p.event_id for p in self.positions.values())
            for event_id in event_ids:
                exposure = self.get_event_exposure(event_id)
                total_gross += exposure.gross_position
                total_net += abs(exposure.net_position)
            
            return {
                'total_gross_exposure': total_gross,
                'total_net_exposure': total_net,
                'num_events_with_positions': num_events,
                'num_positions': len(self.positions),
                'max_event_exposure': self.config['max_event_exposure'],
                'max_gross_exposure': self.config['max_gross_exposure']
            }
    
    def can_take_position(
        self,
        event_id: str,
        size: float,
        is_buy: bool
    ) -> Tuple[bool, str]:
        """
        Check if we can take a new position without violating limits
        
        Args:
            event_id: Event identifier
            size: Proposed position size
            is_buy: True if buying (long), False if selling (short)
        
        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        with self.lock:
            # Check event-level exposure
            current_exposure = self.get_event_exposure(event_id)
            position_delta = size if is_buy else -size
            new_net_position = current_exposure.net_position + position_delta
            
            if abs(new_net_position) > self.config['max_event_exposure']:
                return False, f"Would exceed max event exposure ({self.config['max_event_exposure']})"
            
            # Check total gross exposure
            total = self.get_total_exposure()
            new_gross = total['total_gross_exposure'] + size
            
            if new_gross > self.config['max_gross_exposure']:
                return False, f"Would exceed max gross exposure ({self.config['max_gross_exposure']})"
            
            return True, "OK"
    
    def get_unhedged_positions(self, max_age_s: Optional[float] = None) -> List[Dict]:
        """
        Find positions that need hedging
        
        Args:
            max_age_s: Maximum age in seconds (default: use config)
        
        Returns:
            List of positions that need hedging
        """
        if max_age_s is None:
            max_age_s = self.config['max_unhedged_time_s']
        
        with self.lock:
            current_time = time.time()
            unhedged = []
            
            # Group by event
            event_ids = set(p.event_id for p in self.positions.values())
            for event_id in event_ids:
                exposure = self.get_event_exposure(event_id)
                
                # Check if net position is significant
                if abs(exposure.net_position) > 1:  # More than 1 contract unhedged
                    # Find oldest position for this event
                    event_positions = [p for p in self.positions.values() if p.event_id == event_id]
                    oldest = min(event_positions, key=lambda p: p.last_update)
                    age = current_time - oldest.last_update
                    
                    if age > max_age_s:
                        unhedged.append({
                            'event_id': event_id,
                            'net_position': exposure.net_position,
                            'platforms': exposure.platforms,
                            'age_s': age,
                            'urgent': age > max_age_s * 2  # Very overdue
                        })
            
            return sorted(unhedged, key=lambda x: x['age_s'], reverse=True)
    
    def get_position(self, event_id: str, platform: str, outcome: str) -> Optional[Position]:
        """Get specific position"""
        with self.lock:
            key = (event_id, platform, outcome)
            return self.positions.get(key)
    
    def get_all_positions(self) -> List[Position]:
        """Get all current positions"""
        with self.lock:
            return list(self.positions.values())
    
    def calculate_required_hedge(
        self,
        event_id: str,
        target_platform: str
    ) -> Optional[Dict]:
        """
        Calculate hedge required to neutralize position
        
        Args:
            event_id: Event identifier
            target_platform: Platform to hedge on
        
        Returns:
            Dict with hedge details or None if no hedge needed
        """
        exposure = self.get_event_exposure(event_id)
        
        if abs(exposure.net_position) < 1:
            return None  # Already hedged
        
        # Determine hedge direction
        if exposure.net_position > 0:
            # Net long - need to sell
            return {
                'event_id': event_id,
                'platform': target_platform,
                'side': 'sell',
                'size': abs(exposure.net_position),
                'reason': f'Hedge net long position of {exposure.net_position:.2f}'
            }
        else:
            # Net short - need to buy
            return {
                'event_id': event_id,
                'platform': target_platform,
                'side': 'buy',
                'size': abs(exposure.net_position),
                'reason': f'Hedge net short position of {exposure.net_position:.2f}'
            }
    
    def mark_hedge_complete(self, event_id: str):
        """Mark an event as fully hedged"""
        with self.lock:
            self.full_hedges += 1
    
    def mark_forced_unwind(self, event_id: str):
        """Mark a forced position unwind"""
        with self.lock:
            self.forced_unwinds += 1
    
    def get_stats(self) -> Dict:
        """Get tracker statistics"""
        with self.lock:
            total_exposure = self.get_total_exposure()
            
            return {
                **total_exposure,
                'total_fills': self.total_fills,
                'partial_fills': self.partial_fills,
                'full_hedges': self.full_hedges,
                'forced_unwinds': self.forced_unwinds,
                'config': self.config.copy()
            }
    
    def clear_positions(self):
        """Clear all positions (for testing/reset)"""
        with self.lock:
            self.positions.clear()
            self.dutch_book_positions.clear()
    
    # =========================================================================
    # Dutch Book Position Management
    # =========================================================================
    
    def record_dutch_book(
        self,
        event_id: str,
        kalshi_team: str,
        kalshi_size: float,
        kalshi_price: float,
        kalshi_order_id: Optional[str],
        poly_team: str,
        poly_size: float,
        poly_price: float,
        poly_order_id: Optional[str],
        fees_paid: float
    ) -> DutchBookPosition:
        """
        Record a complete Dutch Book position (both legs filled)
        
        Args:
            event_id: Event identifier
            kalshi_team: Team bought on Kalshi
            kalshi_size: Size filled on Kalshi
            kalshi_price: Price paid on Kalshi
            kalshi_order_id: Kalshi order ID
            poly_team: Team bought on Polymarket (complementary)
            poly_size: Size filled on Polymarket
            poly_price: Price paid on Polymarket
            poly_order_id: Polymarket order ID
            fees_paid: Total fees paid for both legs
        
        Returns:
            The created DutchBookPosition
        """
        with self.lock:
            # Calculate combined cost
            kalshi_cost = kalshi_size * kalshi_price
            poly_cost = poly_size * poly_price
            combined_cost = kalshi_cost + poly_cost
            
            # Guaranteed payout is $1.00 per min(size)
            min_size = min(kalshi_size, poly_size)
            expected_payout = min_size * 1.0
            
            # Locked profit
            locked_profit = expected_payout - combined_cost - fees_paid
            
            position = DutchBookPosition(
                event_id=event_id,
                kalshi_team=kalshi_team,
                kalshi_size=kalshi_size,
                kalshi_price=kalshi_price,
                kalshi_order_id=kalshi_order_id,
                poly_team=poly_team,
                poly_size=poly_size,
                poly_price=poly_price,
                poly_order_id=poly_order_id,
                combined_cost=combined_cost,
                expected_payout=expected_payout,
                locked_profit=locked_profit,
                fees_paid=fees_paid,
                is_complete=True
            )
            
            # Store by event_id
            if event_id not in self.dutch_book_positions:
                self.dutch_book_positions[event_id] = []
            self.dutch_book_positions[event_id].append(position)
            
            # Also record individual fills for standard position tracking
            self.record_fill(event_id, 'kalshi', kalshi_team, kalshi_size, kalshi_price, is_buy=True)
            self.record_fill(event_id, 'polymarket', poly_team, poly_size, poly_price, is_buy=True)
            
            return position
    
    def get_dutch_book_positions(self, event_id: Optional[str] = None) -> List[DutchBookPosition]:
        """
        Get Dutch Book positions
        
        Args:
            event_id: Optional event filter
        
        Returns:
            List of DutchBookPosition objects
        """
        with self.lock:
            if event_id:
                return self.dutch_book_positions.get(event_id, [])
            else:
                all_positions = []
                for positions in self.dutch_book_positions.values():
                    all_positions.extend(positions)
                return all_positions
    
    def get_unsettled_dutch_books(self) -> List[DutchBookPosition]:
        """Get all unsettled Dutch Book positions"""
        with self.lock:
            unsettled = []
            for positions in self.dutch_book_positions.values():
                unsettled.extend([p for p in positions if not p.is_settled])
            return unsettled
    
    def settle_dutch_book(self, event_id: str, winner: str):
        """
        Settle all Dutch Book positions for an event
        
        Args:
            event_id: Event that has resolved
            winner: The winning team
        """
        with self.lock:
            positions = self.dutch_book_positions.get(event_id, [])
            for pos in positions:
                if not pos.is_settled:
                    pos.mark_settled(winner)
    
    def get_dutch_book_summary(self) -> Dict:
        """Get summary of Dutch Book positions"""
        with self.lock:
            all_positions = self.get_dutch_book_positions()
            
            total_locked_profit = sum(p.locked_profit for p in all_positions if p.is_complete)
            total_settled_pnl = sum(p.settlement_pnl or 0 for p in all_positions if p.is_settled)
            
            return {
                'total_positions': len(all_positions),
                'complete_positions': sum(1 for p in all_positions if p.is_complete),
                'settled_positions': sum(1 for p in all_positions if p.is_settled),
                'unsettled_positions': sum(1 for p in all_positions if p.is_complete and not p.is_settled),
                'total_locked_profit': total_locked_profit,
                'total_settled_pnl': total_settled_pnl,
                'events_with_positions': len(self.dutch_book_positions)
            }


# Test/Example usage
def test_inventory_tracker():
    """Test the inventory tracker"""
    tracker = InventoryTracker()
    
    print("\n" + "="*60)
    print("Test: Inventory Tracker")
    print("="*60)
    
    event_id = "test-nfl-game"
    
    # Scenario 1: Successful arbitrage (both legs fill)
    print("\n--- Scenario 1: Both legs fill ---")
    tracker.record_fill(event_id, 'kalshi', 'Baltimore', 100, 0.51, is_buy=True)
    print(f"Filled Kalshi buy: 100 @ $0.51")
    
    tracker.record_fill(event_id, 'polymarket', 'Baltimore', 100, 0.56, is_buy=False)
    print(f"Filled Polymarket sell: 100 @ $0.56")
    
    exposure = tracker.get_event_exposure(event_id)
    print(f"Net exposure: {exposure.net_position:.2f}")
    print(f"Gross exposure: {exposure.gross_position:.2f}")
    print(f"Hedged: {'Yes' if abs(exposure.net_position) < 1 else 'No'}")
    
    # Scenario 2: Partial fill (one leg only)
    print("\n--- Scenario 2: Partial fill (one leg only) ---")
    event_id2 = "test-nfl-game-2"
    tracker.record_fill(event_id2, 'kalshi', 'Pittsburgh', 50, 0.45, is_buy=True)
    print(f"Filled Kalshi buy: 50 @ $0.45")
    print(f"(Polymarket leg failed to fill)")
    
    exposure2 = tracker.get_event_exposure(event_id2)
    print(f"Net exposure: {exposure2.net_position:.2f}")
    print(f"Hedged: {'Yes' if abs(exposure2.net_position) < 1 else 'No'}")
    
    # Check if can take more positions
    print("\n--- Scenario 3: Position limits ---")
    can_take, reason = tracker.can_take_position(event_id2, 200, is_buy=True)
    print(f"Can take 200 more: {can_take} ({reason})")
    
    # Scenario 4: Find unhedged positions
    print("\n--- Scenario 4: Unhedged positions ---")
    time.sleep(1)  # Age the position
    unhedged = tracker.get_unhedged_positions(max_age_s=0.5)
    print(f"Found {len(unhedged)} unhedged positions:")
    for pos in unhedged:
        print(f"  {pos['event_id']}: {pos['net_position']:.2f} (age: {pos['age_s']:.1f}s)")
    
    # Scenario 5: Calculate required hedge
    print("\n--- Scenario 5: Calculate hedge ---")
    hedge = tracker.calculate_required_hedge(event_id2, 'polymarket')
    if hedge:
        print(f"Hedge required:")
        print(f"  Platform: {hedge['platform']}")
        print(f"  Side: {hedge['side']}")
        print(f"  Size: {hedge['size']:.2f}")
        print(f"  Reason: {hedge['reason']}")
    
    # Stats
    print("\n" + "="*60)
    stats = tracker.get_stats()
    print("Stats:")
    for key, value in stats.items():
        if isinstance(value, dict):
            continue
        print(f"  {key}: {value}")
    print("="*60)


if __name__ == "__main__":
    test_inventory_tracker()

