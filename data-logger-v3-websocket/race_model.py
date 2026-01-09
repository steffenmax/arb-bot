"""
Race Loss and Queue Position Probability Modeling

Models the probability of successfully filling an order based on:
1. Race loss: likelihood order is filled/moved before you hit it
2. Queue position: likelihood you're near front of line at same price

These probabilities are critical for realistic arbitrage edge calculation.
Initially uses heuristic models, but designed to learn from empirical fill data.
"""

import time
from typing import Dict, Optional
from dataclasses import dataclass
import math


@dataclass
class FillProbability:
    """Probability estimates for order fill"""
    p_win: float  # Probability of winning race (0.0 - 1.0)
    p_queue: float  # Probability of being near front of queue (0.0 - 1.0)
    p_fill: float  # Combined probability of fill (p_win * p_queue)
    confidence: float  # Confidence in estimate (0.0 - 1.0), higher with more data
    reason: str  # Explanation of probability factors


class RaceModel:
    """
    Model race loss and queue position probabilities
    
    Uses heuristic models initially, learns from empirical data over time.
    """
    
    def __init__(self):
        """Initialize race model"""
        # Empirical fill statistics (to be populated by fill_logger)
        self.fill_history = {
            'attempts': 0,
            'fills': 0,
            'partial_fills': 0,
            'no_fills': 0
        }
        
        # Age-based race win probabilities (in milliseconds)
        # Learned heuristics: stale orderbooks have low fill rates
        self.age_decay_params = {
            'half_life_ms': 500,  # Age at which p_win drops to 50%
            'min_probability': 0.05  # Floor probability for very stale data
        }
        
        # Level-based queue position probabilities
        # Heuristic: joining at same price puts you behind existing orders
        self.queue_probabilities = {
            0: 0.30,  # Level 0 (best price) - low queue probability
            1: 0.50,  # Level 1 - better queue probability
            2: 0.65,  # Level 2 - even better
            3: 0.75,  # Level 3+
        }
        
        print("✓ Race model initialized (heuristic mode)")
    
    def estimate_fill_probability(
        self,
        orderbook_age_ms: float,
        level_index: int = 0,
        target_size: float = 0,
        available_size: float = 0,
        is_aggressive: bool = True
    ) -> FillProbability:
        """
        Estimate probability of successfully filling an order
        
        Args:
            orderbook_age_ms: Milliseconds since last orderbook update
            level_index: Orderbook level (0=best, 1=second best, etc.)
            target_size: Desired fill size
            available_size: Size available at this level
            is_aggressive: True for market/marketable orders, False for resting
        
        Returns:
            FillProbability with p_win, p_queue, and combined p_fill
        """
        # Calculate race win probability based on orderbook age
        p_win = self._calculate_race_win_probability(orderbook_age_ms)
        
        # Calculate queue position probability
        if is_aggressive:
            # Aggressive orders (taker) - no queue, just race
            p_queue = 1.0
        else:
            # Resting orders (maker) - queue position matters
            p_queue = self._calculate_queue_probability(level_index)
        
        # Adjust for size ratio
        size_factor = self._calculate_size_factor(target_size, available_size)
        
        # Combined probability
        p_fill = p_win * p_queue * size_factor
        
        # Confidence based on empirical data
        confidence = self._calculate_confidence()
        
        # Explanation
        reason = self._build_reason_string(
            orderbook_age_ms, level_index, p_win, p_queue, 
            size_factor, is_aggressive
        )
        
        return FillProbability(
            p_win=p_win,
            p_queue=p_queue,
            p_fill=p_fill,
            confidence=confidence,
            reason=reason
        )
    
    def _calculate_race_win_probability(self, age_ms: float) -> float:
        """
        Calculate probability of winning race based on orderbook age
        
        Uses exponential decay: older data = lower probability
        
        Formula: p = min_p + (1 - min_p) * exp(-age / half_life)
        """
        if age_ms < 0:
            age_ms = 0
        
        half_life = self.age_decay_params['half_life_ms']
        min_p = self.age_decay_params['min_probability']
        
        # Exponential decay
        decay = math.exp(-age_ms / half_life)
        p_win = min_p + (1.0 - min_p) * decay
        
        return max(min_p, min(1.0, p_win))
    
    def _calculate_queue_probability(self, level_index: int) -> float:
        """
        Calculate probability of being near front of queue at a price level
        
        Heuristic: joining at same price puts you behind existing orders.
        Better to join at worse prices (higher level index) if edge remains.
        """
        if level_index >= 3:
            level_index = 3  # Use same probability for level 3+
        
        return self.queue_probabilities.get(level_index, 0.75)
    
    def _calculate_size_factor(self, target_size: float, available_size: float) -> float:
        """
        Adjust probability based on size ratio
        
        Larger orders relative to available size are less likely to fill completely
        """
        if available_size <= 0 or target_size <= 0:
            return 1.0
        
        ratio = target_size / available_size
        
        if ratio <= 0.5:
            # Small order relative to available - high fill probability
            return 1.0
        elif ratio <= 1.0:
            # Order size = available size - some risk
            return 0.85
        elif ratio <= 2.0:
            # Order larger than available - likely partial fill
            return 0.5
        else:
            # Order much larger - very likely partial
            return 0.3
    
    def _calculate_confidence(self) -> float:
        """
        Calculate confidence in probability estimate
        
        Low confidence initially (heuristic), increases with empirical data
        """
        total_attempts = self.fill_history['attempts']
        
        if total_attempts == 0:
            # Pure heuristic - low confidence
            return 0.3
        elif total_attempts < 100:
            # Some data - medium confidence
            return 0.3 + (total_attempts / 100) * 0.4
        else:
            # Lots of data - high confidence
            return min(0.9, 0.7 + (total_attempts / 1000) * 0.2)
    
    def _build_reason_string(
        self,
        age_ms: float,
        level_index: int,
        p_win: float,
        p_queue: float,
        size_factor: float,
        is_aggressive: bool
    ) -> str:
        """Build human-readable explanation of probability"""
        reasons = []
        
        # Age factor
        if age_ms < 100:
            reasons.append("fresh data")
        elif age_ms < 500:
            reasons.append("recent data")
        elif age_ms < 2000:
            reasons.append("aging data")
        else:
            reasons.append("stale data")
        
        # Level factor
        if is_aggressive:
            reasons.append(f"level-{level_index} aggressive")
        else:
            reasons.append(f"level-{level_index} maker")
        
        # Size factor
        if size_factor < 0.5:
            reasons.append("large size risk")
        elif size_factor < 0.85:
            reasons.append("moderate size")
        
        return ", ".join(reasons)
    
    def adjust_executable_size(
        self,
        displayed_size: float,
        orderbook_age_ms: float,
        level_index: int = 0
    ) -> float:
        """
        Calculate realistic executable size accounting for race/queue losses
        
        Formula from spec:
        executable_size ≈ displayed_size × p_win × p_queue
        
        Args:
            displayed_size: Size shown in orderbook
            orderbook_age_ms: Milliseconds since last update
            level_index: Orderbook level
        
        Returns:
            Adjusted executable size (lower than displayed)
        """
        prob = self.estimate_fill_probability(
            orderbook_age_ms=orderbook_age_ms,
            level_index=level_index,
            target_size=displayed_size,
            available_size=displayed_size,
            is_aggressive=True
        )
        
        # Reduce displayed size by combined probability
        return displayed_size * prob.p_fill
    
    def recommend_level_for_edge(
        self,
        levels: list,
        min_edge_bps: int,
        target_size: float,
        orderbook_age_ms: float
    ) -> Optional[Dict]:
        """
        Recommend which orderbook level to target based on edge and fill probability
        
        Key insight: Level 0 may have best price but worst fill odds.
        Sometimes Level 1-2 has better expected value.
        
        Args:
            levels: List of (price, size) tuples
            min_edge_bps: Minimum edge required in basis points
            target_size: Desired fill size
            orderbook_age_ms: Orderbook staleness
        
        Returns:
            Dict with recommended level, expected edge, and fill probability
        """
        if not levels:
            return None
        
        best_price = levels[0][0]
        best_expected_value = -float('inf')
        best_level = None
        
        for level_idx, (price, available_size) in enumerate(levels):
            # Calculate edge in bps from best price
            edge_bps = int(((price - best_price) / best_price) * 10000)
            
            # Skip if edge is worse than minimum
            if abs(edge_bps) > min_edge_bps:
                break
            
            # Calculate fill probability
            prob = self.estimate_fill_probability(
                orderbook_age_ms=orderbook_age_ms,
                level_index=level_idx,
                target_size=target_size,
                available_size=available_size,
                is_aggressive=True
            )
            
            # Expected value = edge × fill_probability
            # (Negative edge for asks, positive for bids in arb context)
            expected_value = edge_bps * prob.p_fill
            
            if expected_value > best_expected_value:
                best_expected_value = expected_value
                best_level = {
                    'level_index': level_idx,
                    'price': price,
                    'size': available_size,
                    'edge_bps': edge_bps,
                    'p_fill': prob.p_fill,
                    'expected_value': expected_value,
                    'reason': prob.reason
                }
        
        return best_level
    
    def update_from_fill_result(
        self,
        attempted: bool = True,
        filled: bool = False,
        partial: bool = False,
        orderbook_age_ms: Optional[float] = None
    ):
        """
        Update model based on actual fill result
        
        This allows the model to learn from empirical data over time.
        Called by fill_logger after each execution attempt.
        
        Args:
            attempted: Whether execution was attempted
            filled: Whether order was fully filled
            partial: Whether order was partially filled
            orderbook_age_ms: Age of orderbook when attempt was made
        """
        if attempted:
            self.fill_history['attempts'] += 1
            
            if filled:
                self.fill_history['fills'] += 1
            elif partial:
                self.fill_history['partial_fills'] += 1
            else:
                self.fill_history['no_fills'] += 1
        
        # TODO: Implement more sophisticated learning
        # - Bucket by orderbook age and update age_decay_params
        # - Bucket by level and update queue_probabilities
        # - Use Bayesian updates or moving averages
    
    def get_empirical_fill_rate(self) -> float:
        """Get empirical fill rate from historical data"""
        attempts = self.fill_history['attempts']
        if attempts == 0:
            return 0.0
        
        fills = self.fill_history['fills']
        partials = self.fill_history['partial_fills']
        
        # Count partials as 0.5 fills
        effective_fills = fills + (partials * 0.5)
        
        return effective_fills / attempts
    
    def get_stats(self) -> Dict:
        """Get model statistics"""
        fill_rate = self.get_empirical_fill_rate()
        confidence = self._calculate_confidence()
        
        return {
            'mode': 'empirical' if confidence > 0.5 else 'heuristic',
            'confidence': confidence,
            'fill_history': self.fill_history.copy(),
            'empirical_fill_rate': fill_rate,
            'age_decay_half_life_ms': self.age_decay_params['half_life_ms']
        }


# Test/Example usage
def test_race_model():
    """Test the race model"""
    model = RaceModel()
    
    print("\n" + "="*60)
    print("Test: Race Model")
    print("="*60)
    
    # Test 1: Fresh orderbook, level 0
    print("\n--- Test 1: Fresh orderbook (50ms), level 0 ---")
    prob = model.estimate_fill_probability(
        orderbook_age_ms=50,
        level_index=0,
        target_size=100,
        available_size=200,
        is_aggressive=True
    )
    print(f"P(win): {prob.p_win:.2%}")
    print(f"P(queue): {prob.p_queue:.2%}")
    print(f"P(fill): {prob.p_fill:.2%}")
    print(f"Reason: {prob.reason}")
    
    # Test 2: Stale orderbook, level 0
    print("\n--- Test 2: Stale orderbook (3000ms), level 0 ---")
    prob = model.estimate_fill_probability(
        orderbook_age_ms=3000,
        level_index=0,
        target_size=100,
        available_size=200,
        is_aggressive=True
    )
    print(f"P(win): {prob.p_win:.2%}")
    print(f"P(fill): {prob.p_fill:.2%}")
    print(f"Reason: {prob.reason}")
    
    # Test 3: Recent orderbook, level 2
    print("\n--- Test 3: Recent orderbook (200ms), level 2 ---")
    prob = model.estimate_fill_probability(
        orderbook_age_ms=200,
        level_index=2,
        target_size=100,
        available_size=200,
        is_aggressive=True
    )
    print(f"P(win): {prob.p_win:.2%}")
    print(f"P(fill): {prob.p_fill:.2%}")
    print(f"Reason: {prob.reason}")
    
    # Test 4: Executable size adjustment
    print("\n--- Test 4: Executable size adjustment ---")
    displayed_size = 500
    for age_ms in [50, 200, 500, 1000, 3000]:
        executable = model.adjust_executable_size(displayed_size, age_ms)
        print(f"Age {age_ms}ms: {displayed_size} → {executable:.0f} ({executable/displayed_size:.1%})")
    
    # Test 5: Level recommendation
    print("\n--- Test 5: Level recommendation ---")
    levels = [
        (0.55, 100),
        (0.56, 200),
        (0.57, 300),
        (0.58, 250),
    ]
    recommendation = model.recommend_level_for_edge(
        levels, min_edge_bps=300, target_size=150, orderbook_age_ms=100
    )
    if recommendation:
        print(f"Recommended level: {recommendation['level_index']}")
        print(f"Price: ${recommendation['price']:.4f}")
        print(f"P(fill): {recommendation['p_fill']:.2%}")
        print(f"Expected value: {recommendation['expected_value']:.1f} bps")
    
    # Test 6: Learning from fills
    print("\n--- Test 6: Simulate learning ---")
    print(f"Initial fill rate: {model.get_empirical_fill_rate():.1%}")
    print(f"Initial confidence: {model._calculate_confidence():.1%}")
    
    # Simulate some fills
    for _ in range(50):
        model.update_from_fill_result(attempted=True, filled=True)
    for _ in range(30):
        model.update_from_fill_result(attempted=True, partial=True)
    for _ in range(20):
        model.update_from_fill_result(attempted=True, filled=False)
    
    print(f"After 100 attempts:")
    print(f"  Fill rate: {model.get_empirical_fill_rate():.1%}")
    print(f"  Confidence: {model._calculate_confidence():.1%}")
    
    # Stats
    print("\n" + "="*60)
    print("Stats:", model.get_stats())
    print("="*60)


if __name__ == "__main__":
    test_race_model()

