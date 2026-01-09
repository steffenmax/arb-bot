#!/usr/bin/env python3
"""
Accurate Arbitrage Calculator with Real Fee Models

Implements:
1. Kalshi's actual fee formula: ceil(0.07 × Q × P × (1-P))
2. Polymarket 0% fees (for sports markets)
3. Size-aware net profit calculation
4. Optimal quantity selection
"""

import math
from typing import Dict, Optional, Tuple


class ArbCalculator:
    """Calculate net arbitrage profits with accurate fee models"""
    
    def __init__(
        self,
        kalshi_taker_rate: float = 0.07,    # 7% for taker orders
        kalshi_maker_rate: float = 0.0175,  # 1.75% for maker orders
        polymarket_fee_rate: float = 0.0,    # 0% for most sports markets
        gas_cost_usd: float = 0.0,           # Assumes relayer/proxy (gasless)
        min_roi_pct: float = 2.0,            # Minimum 2% ROI after fees
        min_profit_usd: float = 5.0          # Minimum $5 net profit
    ):
        self.kalshi_taker_rate = kalshi_taker_rate
        self.kalshi_maker_rate = kalshi_maker_rate
        self.polymarket_fee_rate = polymarket_fee_rate
        self.gas_cost_usd = gas_cost_usd
        self.min_roi_pct = min_roi_pct
        self.min_profit_usd = min_profit_usd
    
    def kalshi_fee(self, quantity: float, price: float, is_taker: bool = True) -> float:
        """
        Calculate Kalshi fee using their actual formula
        
        fee = ceil_to_cent(rate × Q × P × (1-P))
        
        Args:
            quantity: Number of contracts
            price: Price per contract ($0-$1)
            is_taker: True for taker orders (default), False for maker
        
        Returns:
            Fee in dollars (rounded up to nearest cent)
        """
        rate = self.kalshi_taker_rate if is_taker else self.kalshi_maker_rate
        fee_cents = rate * quantity * price * (1 - price) * 100
        return math.ceil(fee_cents) / 100.0
    
    def polymarket_fee(self, quantity: float, price: float) -> float:
        """
        Calculate Polymarket fee (0% for most sports markets)
        
        Args:
            quantity: Number of contracts
            price: Price per contract
            
        Returns:
            Fee in dollars
        """
        return self.polymarket_fee_rate * quantity * price
    
    def calculate_net_profit(
        self,
        quantity: float,
        kalshi_price: float,
        poly_price: float,
        kalshi_is_taker: bool = True
    ) -> Dict[str, float]:
        """
        Calculate net profit for a given quantity
        
        Args:
            quantity: Number of contracts to trade
            kalshi_price: Price on Kalshi
            poly_price: Price on Polymarket
            kalshi_is_taker: Whether Kalshi order is taker (vs maker)
        
        Returns:
            Dict with breakdown of profit calculation
        """
        # Gross costs
        kalshi_cost = quantity * kalshi_price
        poly_cost = quantity * poly_price
        total_cost = kalshi_cost + poly_cost
        
        # Gross profit (one side pays $1 per contract)
        payout = quantity * 1.0
        gross_profit = payout - total_cost
        
        # Fees
        kalshi_fee = self.kalshi_fee(quantity, kalshi_price, kalshi_is_taker)
        poly_fee = self.polymarket_fee(quantity, poly_price)
        gas = self.gas_cost_usd
        total_fees = kalshi_fee + poly_fee + gas
        
        # Net profit
        net_profit = gross_profit - total_fees
        
        # ROI
        roi_pct = (net_profit / total_cost * 100) if total_cost > 0 else 0
        
        return {
            'quantity': quantity,
            'kalshi_cost': kalshi_cost,
            'poly_cost': poly_cost,
            'total_cost': total_cost,
            'payout': payout,
            'gross_profit': gross_profit,
            'kalshi_fee': kalshi_fee,
            'poly_fee': poly_fee,
            'gas_cost': gas,
            'total_fees': total_fees,
            'net_profit': net_profit,
            'roi_pct': roi_pct,
            'fee_pct': (total_fees / total_cost * 100) if total_cost > 0 else 0
        }
    
    def find_optimal_quantity(
        self,
        kalshi_price: float,
        poly_price: float,
        max_quantity: float = 1000,
        step: float = 10
    ) -> Optional[Dict[str, float]]:
        """
        Find the optimal quantity that maximizes net profit
        while meeting minimum ROI and profit thresholds
        
        Args:
            kalshi_price: Price on Kalshi
            poly_price: Price on Polymarket
            max_quantity: Maximum contracts to consider
            step: Quantity increment to test
        
        Returns:
            Best result dict or None if no profitable size exists
        """
        best_result = None
        best_net = -float('inf')
        
        quantity = step
        while quantity <= max_quantity:
            result = self.calculate_net_profit(quantity, kalshi_price, poly_price)
            
            # Check if this meets our thresholds
            if (result['net_profit'] >= self.min_profit_usd and 
                result['roi_pct'] >= self.min_roi_pct):
                
                # Track best net profit
                if result['net_profit'] > best_net:
                    best_net = result['net_profit']
                    best_result = result
            
            quantity += step
        
        return best_result
    
    def evaluate_arbitrage(
        self,
        kalshi_a_yes_ask: float,
        kalshi_a_no_ask: float,
        kalshi_b_yes_ask: float,
        kalshi_b_no_ask: float,
        poly_a_ask: float,
        poly_b_ask: float,
        max_quantity: float = 1000
    ) -> Optional[Dict[str, any]]:
        """
        Evaluate all possible arbitrage combinations using improved logic
        
        Uses NO_ASK from opposite market for better pricing:
        - Cost(A wins) = min(A_yes_ask, B_no_ask)
        - Cost(B wins) = min(B_yes_ask, A_no_ask)
        
        Args:
            kalshi_a_yes_ask: Kalshi YES ask for team A
            kalshi_a_no_ask: Kalshi NO ask for team A
            kalshi_b_yes_ask: Kalshi YES ask for team B
            kalshi_b_no_ask: Kalshi NO ask for team B
            poly_a_ask: Polymarket ask for team A token
            poly_b_ask: Polymarket ask for team B token
            max_quantity: Max contracts to consider
        
        Returns:
            Best arbitrage opportunity or None
        """
        # Better Kalshi pricing using NO markets
        kalshi_cost_a = min(kalshi_a_yes_ask, kalshi_b_no_ask) if kalshi_a_yes_ask and kalshi_b_no_ask else kalshi_a_yes_ask
        kalshi_cost_b = min(kalshi_b_yes_ask, kalshi_a_no_ask) if kalshi_b_yes_ask and kalshi_a_no_ask else kalshi_b_yes_ask
        
        opportunities = []
        
        # Combination 1: Kalshi A + Poly B
        if kalshi_cost_a and poly_b_ask:
            result = self.find_optimal_quantity(kalshi_cost_a, poly_b_ask, max_quantity)
            if result:
                opportunities.append({
                    'combo': 'kalshi_a_poly_b',
                    'kalshi_side': 'A',
                    'kalshi_price': kalshi_cost_a,
                    'poly_side': 'B',
                    'poly_price': poly_b_ask,
                    **result
                })
        
        # Combination 2: Kalshi B + Poly A
        if kalshi_cost_b and poly_a_ask:
            result = self.find_optimal_quantity(kalshi_cost_b, poly_a_ask, max_quantity)
            if result:
                opportunities.append({
                    'combo': 'kalshi_b_poly_a',
                    'kalshi_side': 'B',
                    'kalshi_price': kalshi_cost_b,
                    'poly_side': 'A',
                    'poly_price': poly_a_ask,
                    **result
                })
        
        if not opportunities:
            return None
        
        # Return the opportunity with highest net profit
        return max(opportunities, key=lambda x: x['net_profit'])


def format_arb_result(result: Dict) -> str:
    """Format arbitrage result for display"""
    if not result:
        return "No profitable arbitrage found"
    
    lines = [
        f"═══════════════════════════════════════════",
        f"ARBITRAGE OPPORTUNITY",
        f"═══════════════════════════════════════════",
        f"Combination: Kalshi {result['kalshi_side']} + Polymarket {result['poly_side']}",
        f"",
        f"📊 PRICING:",
        f"  Kalshi {result['kalshi_side']}: ${result['kalshi_price']:.3f}",
        f"  Polymarket {result['poly_side']}: ${result['poly_price']:.3f}",
        f"  Gross Total: ${result['kalshi_price'] + result['poly_price']:.4f}",
        f"",
        f"💰 OPTIMAL SIZE: {result['quantity']:.0f} contracts",
        f"  Investment: ${result['total_cost']:.2f}",
        f"  Payout: ${result['payout']:.2f}",
        f"  Gross Profit: ${result['gross_profit']:.2f} ({result['gross_profit']/result['total_cost']*100:.2f}%)",
        f"",
        f"💸 FEES:",
        f"  Kalshi Fee: ${result['kalshi_fee']:.2f}",
        f"  Polymarket Fee: ${result['poly_fee']:.2f}",
        f"  Gas Cost: ${result['gas_cost']:.2f}",
        f"  Total Fees: ${result['total_fees']:.2f} ({result['fee_pct']:.2f}%)",
        f"",
        f"🎯 NET PROFIT: ${result['net_profit']:.2f}",
        f"📈 NET ROI: {result['roi_pct']:.2f}%",
        f"═══════════════════════════════════════════"
    ]
    
    return "\n".join(lines)


# Example usage
if __name__ == "__main__":
    calc = ArbCalculator(
        min_roi_pct=2.0,
        min_profit_usd=5.0,
        gas_cost_usd=0.0  # Assuming gasless via relayer
    )
    
    # Denver/Philly example from the logs
    print("Example: Denver vs Philadelphia")
    print("Kalshi Denver YES: $0.24, NO: $0.76")
    print("Kalshi Philly YES: $0.76, NO: $0.24")
    print("Polymarket Nuggets: $0.24, 76ers: $0.70")
    print()
    
    result = calc.evaluate_arbitrage(
        kalshi_a_yes_ask=0.24,
        kalshi_a_no_ask=0.76,
        kalshi_b_yes_ask=0.76,
        kalshi_b_no_ask=0.24,
        poly_a_ask=0.31,  # Nuggets
        poly_b_ask=0.70,  # 76ers
        max_quantity=500
    )
    
    print(format_arb_result(result))

