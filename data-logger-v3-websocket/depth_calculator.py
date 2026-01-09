"""
Depth-Aware VWAP Calculator (Walk-the-Book)

Calculates volume-weighted average price by walking through orderbook levels.
Handles slippage calculation and determines execution feasibility based on depth.
"""

from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass


@dataclass
class VWAPResult:
    """Result of VWAP calculation"""
    vwap_price: float  # Volume-weighted average price
    total_size: float  # Total size that can be filled
    total_cost: float  # Total cost in quote currency
    slippage_bps: int  # Slippage in basis points from best price
    levels_used: int  # Number of orderbook levels consumed
    feasible: bool  # Whether target size can be filled
    worst_price: float  # Worst price paid (last level)
    best_price: float  # Best price (first level)


class DepthCalculator:
    """
    Calculate VWAP and slippage by walking through orderbook levels
    
    This is critical for execution - treats orderbook depth realistically
    instead of assuming infinite liquidity at best price.
    """
    
    def __init__(self):
        """Initialize depth calculator"""
        pass
    
    def calculate_vwap_for_size(
        self,
        orderbook_levels: List[Tuple[float, float]],
        target_size: float,
        max_levels: Optional[int] = None,
        max_slippage_bps: Optional[int] = None
    ) -> VWAPResult:
        """
        Calculate VWAP for a target size by walking the book
        
        Args:
            orderbook_levels: List of (price, size) tuples
            target_size: Desired size to fill (in contracts/tokens)
            max_levels: Maximum number of levels to walk (None = unlimited)
            max_slippage_bps: Maximum slippage in basis points from best price
        
        Returns:
            VWAPResult with pricing and feasibility information
        """
        if not orderbook_levels or target_size <= 0:
            return VWAPResult(
                vwap_price=0,
                total_size=0,
                total_cost=0,
                slippage_bps=0,
                levels_used=0,
                feasible=False,
                worst_price=0,
                best_price=0
            )
        
        # Find first valid price (skip zero prices)
        best_price = 0
        for price, _ in orderbook_levels:
            if price > 0:
                best_price = price
                break
        
        if best_price <= 0:
            return VWAPResult(
                vwap_price=0,
                total_size=0,
                total_cost=0,
                slippage_bps=0,
                levels_used=0,
                feasible=False,
                worst_price=0,
                best_price=0
            )
        
        remaining_size = target_size
        total_cost = 0
        total_filled = 0
        levels_used = 0
        worst_price = best_price
        
        # Walk through levels
        for level_idx, (price, available_size) in enumerate(orderbook_levels):
            # Skip invalid levels (zero or negative price)
            if price <= 0:
                continue
                
            # Check max levels constraint
            if max_levels is not None and level_idx >= max_levels:
                break
            
            # Check max slippage constraint
            if max_slippage_bps is not None and best_price > 0:
                slippage_bps = int(((price - best_price) / best_price) * 10000)
                if slippage_bps > max_slippage_bps:
                    break
            
            # Calculate fill at this level
            fill_size = min(remaining_size, available_size)
            fill_cost = fill_size * price
            
            total_cost += fill_cost
            total_filled += fill_size
            remaining_size -= fill_size
            levels_used += 1
            worst_price = price
            
            # Check if we've filled the order
            if remaining_size <= 0:
                break
        
        # Calculate results
        feasible = (remaining_size <= 0)
        vwap_price = total_cost / total_filled if total_filled > 0 else 0
        slippage_bps = int(((vwap_price - best_price) / best_price) * 10000) if best_price > 0 else 0
        
        return VWAPResult(
            vwap_price=vwap_price,
            total_size=total_filled,
            total_cost=total_cost,
            slippage_bps=slippage_bps,
            levels_used=levels_used,
            feasible=feasible,
            worst_price=worst_price,
            best_price=best_price
        )
    
    def calculate_vwap_for_dollars(
        self,
        orderbook_levels: List[Tuple[float, float]],
        target_dollars: float,
        max_levels: Optional[int] = None,
        max_slippage_bps: Optional[int] = None
    ) -> VWAPResult:
        """
        Calculate VWAP for a target dollar amount by walking the book
        
        Similar to calculate_vwap_for_size but targets a dollar amount instead
        of a specific size. Useful for sizing arbitrage legs.
        
        Args:
            orderbook_levels: List of (price, size) tuples
            target_dollars: Desired dollar amount to spend
            max_levels: Maximum number of levels to walk
            max_slippage_bps: Maximum slippage in basis points from best price
        
        Returns:
            VWAPResult with pricing and feasibility information
        """
        if not orderbook_levels or target_dollars <= 0:
            return VWAPResult(
                vwap_price=0,
                total_size=0,
                total_cost=0,
                slippage_bps=0,
                levels_used=0,
                feasible=False,
                worst_price=0,
                best_price=0
            )
        
        # Find first valid price (skip zero prices)
        best_price = 0
        for price, _ in orderbook_levels:
            if price > 0:
                best_price = price
                break
        
        if best_price <= 0:
            return VWAPResult(
                vwap_price=0,
                total_size=0,
                total_cost=0,
                slippage_bps=0,
                levels_used=0,
                feasible=False,
                worst_price=0,
                best_price=0
            )
        
        remaining_dollars = target_dollars
        total_cost = 0
        total_filled = 0
        levels_used = 0
        worst_price = best_price
        
        # Walk through levels
        for level_idx, (price, available_size) in enumerate(orderbook_levels):
            # Skip invalid levels (zero or negative price)
            if price <= 0:
                continue
                
            # Check max levels constraint
            if max_levels is not None and level_idx >= max_levels:
                break
            
            # Check max slippage constraint
            if max_slippage_bps is not None and best_price > 0:
                slippage_bps = int(((price - best_price) / best_price) * 10000)
                if slippage_bps > max_slippage_bps:
                    break
            
            # Calculate how much we can buy at this level with remaining dollars
            max_size_for_dollars = remaining_dollars / price
            fill_size = min(max_size_for_dollars, available_size)
            fill_cost = fill_size * price
            
            total_cost += fill_cost
            total_filled += fill_size
            remaining_dollars -= fill_cost
            levels_used += 1
            worst_price = price
            
            # Check if we've spent all our dollars
            if remaining_dollars <= 0.01:  # Allow for rounding
                break
        
        # Calculate results
        feasible = (remaining_dollars <= 0.01)
        vwap_price = total_cost / total_filled if total_filled > 0 else 0
        slippage_bps = int(((vwap_price - best_price) / best_price) * 10000) if best_price > 0 else 0
        
        return VWAPResult(
            vwap_price=vwap_price,
            total_size=total_filled,
            total_cost=total_cost,
            slippage_bps=slippage_bps,
            levels_used=levels_used,
            feasible=feasible,
            worst_price=worst_price,
            best_price=best_price
        )
    
    def calculate_max_size_for_slippage(
        self,
        orderbook_levels: List[Tuple[float, float]],
        max_slippage_bps: int
    ) -> Tuple[float, float]:
        """
        Calculate maximum size that can be filled within slippage budget
        
        Args:
            orderbook_levels: List of (price, size) tuples
            max_slippage_bps: Maximum slippage in basis points
        
        Returns:
            Tuple of (max_size, vwap_price)
        """
        if not orderbook_levels:
            return 0, 0
        
        best_price = orderbook_levels[0][0]
        max_price = best_price * (1 + max_slippage_bps / 10000)
        
        total_size = 0
        total_cost = 0
        
        for price, available_size in orderbook_levels:
            if price > max_price:
                break
            
            total_cost += price * available_size
            total_size += available_size
        
        vwap_price = total_cost / total_size if total_size > 0 else 0
        
        return total_size, vwap_price
    
    def estimate_fill_probability(
        self,
        orderbook_levels: List[Tuple[float, float]],
        target_size: float,
        level_index: int = 0
    ) -> float:
        """
        Estimate probability of filling at a specific level
        
        This is a simplified model - actual fill probabilities should be
        learned empirically (see fill_logger.py).
        
        Args:
            orderbook_levels: List of (price, size) tuples
            target_size: Desired fill size
            level_index: Which level (0 = best, 1 = second best, etc.)
        
        Returns:
            Probability estimate (0.0 to 1.0)
        """
        if not orderbook_levels or level_index >= len(orderbook_levels):
            return 0.0
        
        available_size = orderbook_levels[level_index][1]
        
        if available_size >= target_size * 2:
            # Plenty of size - high probability
            return 0.7 if level_index == 0 else 0.5
        elif available_size >= target_size:
            # Just enough size - medium probability
            return 0.4 if level_index == 0 else 0.25
        else:
            # Not enough size - low probability
            return 0.2 if level_index == 0 else 0.1
    
    def compare_execution_costs(
        self,
        bid_levels: List[Tuple[float, float]],
        ask_levels: List[Tuple[float, float]],
        size: float,
        max_slippage_bps: int = 100
    ) -> Dict:
        """
        Compare cost of buying vs selling for arbitrage analysis
        
        Args:
            bid_levels: Bid side orderbook (sorted descending)
            ask_levels: Ask side orderbook (sorted ascending)
            size: Target size
            max_slippage_bps: Maximum slippage budget
        
        Returns:
            Dict with buy and sell execution analysis
        """
        buy_result = self.calculate_vwap_for_size(
            ask_levels, size, max_slippage_bps=max_slippage_bps
        )
        
        sell_result = self.calculate_vwap_for_size(
            bid_levels, size, max_slippage_bps=max_slippage_bps
        )
        
        return {
            'buy': {
                'vwap': buy_result.vwap_price,
                'cost': buy_result.total_cost,
                'slippage_bps': buy_result.slippage_bps,
                'feasible': buy_result.feasible,
                'levels': buy_result.levels_used
            },
            'sell': {
                'vwap': sell_result.vwap_price,
                'proceeds': sell_result.total_cost,
                'slippage_bps': sell_result.slippage_bps,
                'feasible': sell_result.feasible,
                'levels': sell_result.levels_used
            }
        }


# Test/Example usage
def test_depth_calculator():
    """Test the depth calculator"""
    calculator = DepthCalculator()
    
    # Example orderbook (asks - buying)
    asks = [
        (0.55, 100),  # Best ask: $0.55, 100 contracts
        (0.56, 150),  # $0.56, 150 contracts
        (0.57, 200),  # $0.57, 200 contracts
        (0.58, 120),  # $0.58, 120 contracts
        (0.59, 180),  # $0.59, 180 contracts
    ]
    
    # Example orderbook (bids - selling)
    bids = [
        (0.54, 120),  # Best bid: $0.54, 120 contracts
        (0.53, 180),  # $0.53, 180 contracts
        (0.52, 150),  # $0.52, 150 contracts
        (0.51, 200),  # $0.51, 200 contracts
        (0.50, 100),  # $0.50, 100 contracts
    ]
    
    print("\n" + "="*60)
    print("Test: Depth Calculator")
    print("="*60)
    
    # Test 1: Buy 200 contracts
    print("\n--- Test 1: Buy 200 contracts ---")
    result = calculator.calculate_vwap_for_size(asks, 200)
    print(f"VWAP: ${result.vwap_price:.4f}")
    print(f"Total cost: ${result.total_cost:.2f}")
    print(f"Slippage: {result.slippage_bps} bps")
    print(f"Levels used: {result.levels_used}")
    print(f"Feasible: {result.feasible}")
    print(f"Price range: ${result.best_price:.4f} - ${result.worst_price:.4f}")
    
    # Test 2: Buy $100 worth
    print("\n--- Test 2: Buy $100 worth ---")
    result = calculator.calculate_vwap_for_dollars(asks, 100)
    print(f"VWAP: ${result.vwap_price:.4f}")
    print(f"Size filled: {result.total_size:.2f} contracts")
    print(f"Total cost: ${result.total_cost:.2f}")
    print(f"Slippage: {result.slippage_bps} bps")
    
    # Test 3: Buy with slippage limit
    print("\n--- Test 3: Buy 300 contracts (max 200 bps slippage) ---")
    result = calculator.calculate_vwap_for_size(asks, 300, max_slippage_bps=200)
    print(f"VWAP: ${result.vwap_price:.4f}")
    print(f"Size filled: {result.total_size:.2f} / 300")
    print(f"Slippage: {result.slippage_bps} bps")
    print(f"Feasible: {result.feasible}")
    
    # Test 4: Max size for slippage
    print("\n--- Test 4: Max size for 150 bps slippage ---")
    max_size, vwap = calculator.calculate_max_size_for_slippage(asks, 150)
    print(f"Max size: {max_size:.2f} contracts")
    print(f"VWAP: ${vwap:.4f}")
    
    # Test 5: Compare buy vs sell
    print("\n--- Test 5: Compare execution (150 contracts) ---")
    comparison = calculator.compare_execution_costs(bids, asks, 150)
    print(f"Buy side:")
    print(f"  VWAP: ${comparison['buy']['vwap']:.4f}")
    print(f"  Cost: ${comparison['buy']['cost']:.2f}")
    print(f"  Slippage: {comparison['buy']['slippage_bps']} bps")
    print(f"Sell side:")
    print(f"  VWAP: ${comparison['sell']['vwap']:.4f}")
    print(f"  Proceeds: ${comparison['sell']['proceeds']:.2f}")
    print(f"  Slippage: {comparison['sell']['slippage_bps']} bps")
    print(f"Net cost: ${comparison['buy']['cost'] - comparison['sell']['proceeds']:.2f}")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    test_depth_calculator()

