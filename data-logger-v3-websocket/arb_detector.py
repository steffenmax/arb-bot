"""
Dutch Book Arbitrage Detector

Detects cross-venue Dutch Book arbitrage opportunities:
- Buy Team A YES on Kalshi + Buy Team B YES on Polymarket
- If combined ask prices < $1.00, profit is guaranteed regardless of outcome

This is the ONLY valid arbitrage strategy for prediction markets since
you cannot short-sell (sell contracts you don't own).

Formula:
    edge = $1.00 - (kalshi_ask + poly_ask) - fees
    
If edge > min_edge_bps, opportunity exists.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import time

from orderbook_manager import OrderbookManager
from depth_calculator import DepthCalculator, VWAPResult
from race_model import RaceModel


@dataclass
class DutchBookOpportunity:
    """Detected Dutch Book arbitrage opportunity"""
    event_id: str
    timestamp: float
    
    # Leg 1: Buy on Kalshi
    kalshi_team: str           # e.g., "IND" (Indiana)
    kalshi_ticker: str         # e.g., "KXNBAGAME-26JAN08INDCHA-IND"
    kalshi_ask: float          # Ask price (what you pay to buy)
    kalshi_ask_size: float     # Available size at best ask
    kalshi_vwap: float         # VWAP for target size
    
    # Leg 2: Buy on Polymarket (complementary team)
    poly_team: str             # e.g., "CHA" (Charlotte) - the OTHER team
    poly_token_id: str
    poly_ask: float            # Ask price
    poly_ask_size: float       # Available size at best ask
    poly_vwap: float           # VWAP for target size
    
    # Combined edge calculation
    combined_cost: float       # kalshi_vwap + poly_vwap
    guaranteed_payout: float   # Always 1.0 (exactly one outcome pays $1)
    gross_edge: float          # 1.0 - combined_cost
    kalshi_fee: float          # Fee on Kalshi leg
    poly_fee: float            # Fee on Polymarket leg
    total_fees: float          # Combined fees
    net_edge: float            # gross_edge - total_fees
    edge_bps: int              # Net edge in basis points
    
    # Execution
    size: float                # Recommended size in dollars per leg
    kalshi_cost: float         # Total cost for Kalshi leg
    poly_cost: float           # Total cost for Polymarket leg
    total_cost: float          # Combined cost for both legs
    
    # Slippage
    kalshi_slippage_bps: int
    poly_slippage_bps: int
    total_slippage_bps: int
    
    # Risk factors
    kalshi_p_fill: float       # Probability of Kalshi fill
    poly_p_fill: float         # Probability of Polymarket fill
    combined_p_fill: float     # Both legs fill
    
    # Orderbook health
    kalshi_staleness_ms: float
    poly_staleness_ms: float
    max_staleness_ms: float
    
    # Metadata
    kalshi_levels_used: int
    poly_levels_used: int
    reason: str                # Description of the opportunity
    confidence: str            # Low/Medium/High


# Keep old ArbOpportunity as alias for backward compatibility during transition
ArbOpportunity = DutchBookOpportunity


class ArbDetector:
    """
    Dutch Book Arbitrage Detector
    
    Detects opportunities where buying complementary outcomes across venues
    costs less than the guaranteed $1.00 payout.
    
    Example:
    - Kalshi: Indiana YES ask @ $0.55
    - Polymarket: Charlotte YES ask @ $0.40
    - Combined: $0.95
    - Guaranteed payout: $1.00 (exactly one team wins)
    - Gross profit: $0.05 (5.26%)
    """
    
    def __init__(
        self,
        orderbook_manager: OrderbookManager,
        depth_calculator: DepthCalculator,
        race_model: RaceModel,
        config: Optional[Dict] = None
    ):
        """
        Initialize Dutch Book detector
        
        Args:
            orderbook_manager: Source of L2 orderbook data
            depth_calculator: VWAP calculator
            race_model: Fill probability model
            config: Configuration dict with:
                - min_edge_bps: Minimum net edge (default: 50 = 0.5%)
                - max_slippage_bps: Max slippage budget per leg (default: 200 = 2%)
                - max_staleness_ms: Max orderbook age (default: 2000)
                - min_size_dollars: Minimum trade size per leg (default: 50)
                - max_size_dollars: Maximum trade size per leg (default: 500)
                - kalshi_fee_rate: Kalshi fee % (default: 0.07 = 7%)
                - polymarket_fee_rate: Polymarket fee % (default: 0.02 = 2%)
        """
        self.orderbook_manager = orderbook_manager
        self.depth_calculator = depth_calculator
        self.race_model = race_model
        
        # Configuration
        default_config = {
            'min_edge_bps': 50,       # 0.5% minimum profit (Dutch book edges are smaller)
            'max_slippage_bps': 200,  # 2% max slippage per leg
            'max_staleness_ms': 2000, # 2 seconds max age
            'min_size_dollars': 50,
            'max_size_dollars': 500,
            'kalshi_fee_rate': 0.07,  # 7% fee on Kalshi
            'polymarket_fee_rate': 0.02,  # 2% fee on Polymarket
        }
        self.config = {**default_config, **(config or {})}
        
        # Statistics
        self.opportunities_detected = 0
        self.opportunities_filtered = 0
        self.confidence_overrides = 0  # Count of Low → Medium-Override upgrades
        self.last_scan_time = 0
        
        # Diagnostic counters (reset each scan)
        self.scan_stats = {
            'markets_checked': 0,
            'combinations_checked': 0,
            'filtered_stale': 0,
            'filtered_no_liquidity': 0,
            'filtered_no_edge': 0,
            'filtered_edge_too_small': 0
        }
        
        print(f"✓ Dutch Book detector initialized (min edge: {self.config['min_edge_bps']}bps)")
    
    def scan_for_opportunities(self) -> List[DutchBookOpportunity]:
        """
        Scan all markets for Dutch Book arbitrage opportunities
        
        For each event (game), checks two combinations:
        1. Team A on Kalshi + Team B on Polymarket
        2. Team B on Kalshi + Team A on Polymarket
        
        Returns:
            List of DutchBookOpportunity objects, sorted by net edge descending
        """
        opportunities = []
        
        # Reset scan stats
        self.scan_stats = {
            'markets_checked': 0,
            'combinations_checked': 0,
            'filtered_stale': 0,
            'filtered_no_liquidity': 0,
            'filtered_no_edge': 0,
            'filtered_edge_too_small': 0
        }
        
        # Get all registered event_ids from metadata
        event_ids = self.orderbook_manager.get_all_markets()
        
        for event_id in event_ids:
            self.scan_stats['markets_checked'] += 1
            
            # Get metadata which contains Kalshi tickers and Poly token info
            metadata = self.orderbook_manager.get_market_metadata(event_id)
            if not metadata:
                continue
            
            # Get Kalshi tickers (list of tickers for this event - one per team)
            kalshi_tickers = metadata.get('kalshi_tickers', [])
            if len(kalshi_tickers) < 2:
                continue  # Need both team tickers
            
            # Get Polymarket token IDs keyed by team code
            poly_token_ids = metadata.get('poly_token_ids', {})
            if len(poly_token_ids) < 2:
                continue  # Need both team tokens
            
            # Extract team codes
            team_codes = list(poly_token_ids.keys())
            if len(team_codes) < 2:
                continue
            
            team_a = team_codes[0]
            team_b = team_codes[1]
            
            # Find Kalshi tickers for each team
            kalshi_a_ticker = None
            kalshi_b_ticker = None
            
            for ticker in kalshi_tickers:
                ticker_team = ticker.split('-')[-1].upper() if '-' in ticker else ''
                if ticker_team == team_a.upper():
                    kalshi_a_ticker = ticker
                elif ticker_team == team_b.upper():
                    kalshi_b_ticker = ticker
            
            if not kalshi_a_ticker or not kalshi_b_ticker:
                continue  # Can't find both Kalshi tickers
            
            # Build orderbook keys
            kalshi_a_key = f"kalshi:{kalshi_a_ticker}"
            kalshi_b_key = f"kalshi:{kalshi_b_ticker}"
            poly_a_key = f"{event_id}:polymarket:{team_a}"
            poly_b_key = f"{event_id}:polymarket:{team_b}"
            
            # Combination 1: Team A on Kalshi + Team B on Polymarket
            opp1 = self._check_dutch_book_opportunity(
                event_id=event_id,
                kalshi_team=team_a,
                kalshi_ticker=kalshi_a_ticker,
                kalshi_key=kalshi_a_key,
                poly_team=team_b,
                poly_token_id=str(poly_token_ids[team_b]),
                poly_key=poly_b_key
            )
            if opp1:
                opportunities.append(opp1)
            
            # Combination 2: Team B on Kalshi + Team A on Polymarket
            opp2 = self._check_dutch_book_opportunity(
                event_id=event_id,
                kalshi_team=team_b,
                kalshi_ticker=kalshi_b_ticker,
                kalshi_key=kalshi_b_key,
                poly_team=team_a,
                poly_token_id=str(poly_token_ids[team_a]),
                poly_key=poly_a_key
            )
            if opp2:
                opportunities.append(opp2)
        
        # Sort by net edge descending
        opportunities.sort(key=lambda x: x.net_edge, reverse=True)
        
        self.opportunities_detected += len(opportunities)
        self.last_scan_time = time.time()
        
        return opportunities
    
    def check_event(self, event_id: str) -> Optional[DutchBookOpportunity]:
        """
        Check a single event for Dutch Book opportunities (event-driven detection).
        
        Called when an orderbook update is received for a specific market.
        More efficient than full scan - only checks the relevant event.
        
        Args:
            event_id: Event identifier to check
        
        Returns:
            Best DutchBookOpportunity for this event, or None if no opportunity
        """
        # Get metadata for this event
        metadata = self.orderbook_manager.get_market_metadata(event_id)
        if not metadata:
            return None
        
        # Get Kalshi tickers
        kalshi_tickers = metadata.get('kalshi_tickers', [])
        if len(kalshi_tickers) < 2:
            return None
        
        # Get Polymarket token IDs keyed by team code
        poly_token_ids = metadata.get('poly_token_ids', {})
        if len(poly_token_ids) < 2:
            return None
        
        # Extract team codes
        team_codes = list(poly_token_ids.keys())
        if len(team_codes) < 2:
            return None
        
        team_a = team_codes[0]
        team_b = team_codes[1]
        
        # Find Kalshi tickers for each team
        kalshi_a_ticker = None
        kalshi_b_ticker = None
        
        for ticker in kalshi_tickers:
            ticker_team = ticker.split('-')[-1].upper() if '-' in ticker else ''
            if ticker_team == team_a.upper():
                kalshi_a_ticker = ticker
            elif ticker_team == team_b.upper():
                kalshi_b_ticker = ticker
        
        if not kalshi_a_ticker or not kalshi_b_ticker:
            return None
        
        # Build orderbook keys
        kalshi_a_key = f"kalshi:{kalshi_a_ticker}"
        kalshi_b_key = f"kalshi:{kalshi_b_ticker}"
        poly_a_key = f"{event_id}:polymarket:{team_a}"
        poly_b_key = f"{event_id}:polymarket:{team_b}"
        
        # Check both combinations
        opportunities = []
        
        # Combination 1: Team A on Kalshi + Team B on Polymarket
        opp1 = self._check_dutch_book_opportunity(
            event_id=event_id,
            kalshi_team=team_a,
            kalshi_ticker=kalshi_a_ticker,
            kalshi_key=kalshi_a_key,
            poly_team=team_b,
            poly_token_id=str(poly_token_ids.get(team_b, '')),
            poly_key=poly_b_key
        )
        if opp1:
            opportunities.append(opp1)
        
        # Combination 2: Team B on Kalshi + Team A on Polymarket
        opp2 = self._check_dutch_book_opportunity(
            event_id=event_id,
            kalshi_team=team_b,
            kalshi_ticker=kalshi_b_ticker,
            kalshi_key=kalshi_b_key,
            poly_team=team_a,
            poly_token_id=str(poly_token_ids.get(team_a, '')),
            poly_key=poly_a_key
        )
        if opp2:
            opportunities.append(opp2)
        
        # Return best opportunity (highest edge)
        if opportunities:
            return max(opportunities, key=lambda x: x.edge_bps)
        return None
    
    def _check_dutch_book_opportunity(
        self,
        event_id: str,
        kalshi_team: str,
        kalshi_ticker: str,
        kalshi_key: str,
        poly_team: str,
        poly_token_id: str,
        poly_key: str
    ) -> Optional[DutchBookOpportunity]:
        """
        Check for Dutch Book opportunity: Buy Team A on Kalshi + Buy Team B on Polymarket
        
        Profitable if: kalshi_ask + poly_ask < 1.0 - fees
        
        Args:
            event_id: Event identifier
            kalshi_team: Team code for Kalshi leg (e.g., "IND")
            kalshi_ticker: Kalshi market ticker
            kalshi_key: Full orderbook key for Kalshi
            poly_team: Team code for Polymarket leg (e.g., "CHA") - complementary team
            poly_token_id: Polymarket token ID
            poly_key: Full orderbook key for Polymarket
        
        Returns:
            DutchBookOpportunity if profitable, None otherwise
        """
        self.scan_stats['combinations_checked'] += 1
        
        # Get orderbooks - we need ASK prices (what we pay to buy)
        kalshi_book = self.orderbook_manager.get_orderbook(kalshi_key, 'kalshi')
        poly_book = self.orderbook_manager.get_orderbook(poly_key, 'polymarket')
        
        # Check staleness
        kalshi_staleness = self.orderbook_manager.get_staleness_ms(kalshi_key, 'kalshi')
        poly_staleness = self.orderbook_manager.get_staleness_ms(poly_key, 'polymarket')
        max_staleness = max(kalshi_staleness, poly_staleness)
        
        if max_staleness > self.config['max_staleness_ms']:
            self.opportunities_filtered += 1
            self.scan_stats['filtered_stale'] += 1
            return None
        
        # Check if orderbooks exist and have asks (we're buying, not selling)
        if not kalshi_book.get('asks') or not poly_book.get('asks'):
            self.scan_stats['filtered_no_liquidity'] += 1
            return None
        
        # Quick check: do best asks sum to less than $1.00?
        kalshi_best_ask = kalshi_book['asks'][0][0]
        poly_best_ask = poly_book['asks'][0][0]
        
        if kalshi_best_ask + poly_best_ask >= 1.0:
            self.scan_stats['filtered_no_edge'] += 1
            return None  # No Dutch Book opportunity at best prices
        
        # Evaluate at different sizes
        best_opp = None
        best_edge = -float('inf')
        
        for size_dollars in [
            self.config['min_size_dollars'],
            self.config['min_size_dollars'] * 2,
            self.config['max_size_dollars'] / 2,
            self.config['max_size_dollars']
        ]:
            opp = self._evaluate_dutch_book_at_size(
                event_id=event_id,
                kalshi_team=kalshi_team,
                kalshi_ticker=kalshi_ticker,
                kalshi_book=kalshi_book,
                kalshi_staleness=kalshi_staleness,
                poly_team=poly_team,
                poly_token_id=poly_token_id,
                poly_book=poly_book,
                poly_staleness=poly_staleness,
                size_dollars=size_dollars
            )
            
            if opp and opp.net_edge > best_edge:
                best_edge = opp.net_edge
                best_opp = opp
        
        # Check if best opportunity meets minimum edge
        if best_opp and best_opp.edge_bps >= self.config['min_edge_bps']:
            return best_opp
        
        if best_opp:
            self.scan_stats['filtered_edge_too_small'] += 1
        self.opportunities_filtered += 1
        return None
    
    def _evaluate_dutch_book_at_size(
        self,
        event_id: str,
        kalshi_team: str,
        kalshi_ticker: str,
        kalshi_book: Dict,
        kalshi_staleness: float,
        poly_team: str,
        poly_token_id: str,
        poly_book: Dict,
        poly_staleness: float,
        size_dollars: float
    ) -> Optional[DutchBookOpportunity]:
        """
        Evaluate Dutch Book opportunity at a specific size per leg
        
        Args:
            size_dollars: Amount to spend on EACH leg (total cost = 2x)
        
        Returns:
            DutchBookOpportunity if profitable at this size, None otherwise
        """
        # Calculate VWAP for Kalshi buy (walking ask side)
        kalshi_result = self.depth_calculator.calculate_vwap_for_dollars(
            orderbook_levels=kalshi_book['asks'],
            target_dollars=size_dollars,
            max_slippage_bps=self.config['max_slippage_bps']
        )
        
        if not kalshi_result.feasible:
            return None  # Can't buy desired size within slippage budget
        
        # Calculate VWAP for Polymarket buy (walking ask side)
        poly_result = self.depth_calculator.calculate_vwap_for_dollars(
            orderbook_levels=poly_book['asks'],
            target_dollars=size_dollars,
            max_slippage_bps=self.config['max_slippage_bps']
        )
        
        if not poly_result.feasible:
            return None  # Can't buy desired size within slippage budget
        
        # For Dutch Book, we need equal contract sizes, not equal dollar amounts
        # Use the smaller of the two sizes to ensure balanced legs
        min_size = min(kalshi_result.total_size, poly_result.total_size)
        
        # Recalculate costs at the balanced size
        kalshi_cost = min_size * kalshi_result.vwap_price
        poly_cost = min_size * poly_result.vwap_price
        
        # Combined cost for both legs
        combined_cost_per_contract = kalshi_result.vwap_price + poly_result.vwap_price
        total_cost = kalshi_cost + poly_cost
        
        # Guaranteed payout is $1.00 per contract (one outcome MUST pay out)
        guaranteed_payout = 1.0
        
        # Gross edge per contract
        gross_edge_per_contract = guaranteed_payout - combined_cost_per_contract
        
        if gross_edge_per_contract <= 0:
            return None  # No Dutch Book edge
        
        # Calculate fees CORRECTLY: Different rates per venue, on WINNING LEG PROFIT only
        # - Kalshi: 7% on profit when Kalshi leg wins
        # - Polymarket: 2% on profit when Poly leg wins
        # For conservative estimate: calculate BOTH scenarios, use WORST CASE
        
        kalshi_vwap = kalshi_result.vwap_price
        poly_vwap = poly_result.vwap_price
        kalshi_fee_rate = self.config.get('kalshi_fee_rate', 0.07)  # 7%
        poly_fee_rate = self.config.get('polymarket_fee_rate', 0.02)  # 2%
        
        # Scenario 1: Kalshi team wins (Kalshi leg pays out)
        kalshi_wins_profit = guaranteed_payout - kalshi_vwap  # Profit per contract if Kalshi wins
        kalshi_wins_fee = kalshi_wins_profit * kalshi_fee_rate  # 7% of Kalshi profit
        kalshi_wins_net = gross_edge_per_contract - kalshi_wins_fee
        
        # Scenario 2: Poly team wins (Poly leg pays out)
        poly_wins_profit = guaranteed_payout - poly_vwap  # Profit per contract if Poly wins
        poly_wins_fee = poly_wins_profit * poly_fee_rate  # 2% of Poly profit
        poly_wins_net = gross_edge_per_contract - poly_wins_fee
        
        # WORST CASE: Use the smaller net edge (more conservative)
        worst_case_net_per_contract = min(kalshi_wins_net, poly_wins_net)
        worst_case_fee_per_contract = gross_edge_per_contract - worst_case_net_per_contract
        
        # Total fees and net edge at size
        total_fees = min_size * worst_case_fee_per_contract
        net_edge = min_size * worst_case_net_per_contract
        
        # For reporting, show the scenario-specific fees
        kalshi_fee = min_size * kalshi_wins_fee
        poly_fee = min_size * poly_wins_fee
        
        # Gross edge (for reporting)
        gross_edge_total = min_size * gross_edge_per_contract
        
        # Edge in basis points (relative to cost) - using worst case net edge
        edge_bps = int((net_edge / total_cost) * 10000) if total_cost > 0 else 0
        
        if edge_bps < self.config['min_edge_bps']:
            return None  # Not profitable enough after fees
        
        # Calculate fill probabilities
        kalshi_prob = self.race_model.estimate_fill_probability(
            orderbook_age_ms=kalshi_staleness,
            level_index=0,
            target_size=min_size,
            available_size=kalshi_book['asks'][0][1] if kalshi_book['asks'] else 0,
            is_aggressive=True
        )
        
        poly_prob = self.race_model.estimate_fill_probability(
            orderbook_age_ms=poly_staleness,
            level_index=0,
            target_size=min_size,
            available_size=poly_book['asks'][0][1] if poly_book['asks'] else 0,
            is_aggressive=True
        )
        
        # Use MIN instead of multiplication for combined fill probability
        # Rationale: The bottleneck is the WORST leg, not the product
        # Old: 50% × 50% = 25% (too harsh)
        # New: min(50%, 50%) = 50% (reflects actual bottleneck)
        combined_p_fill = min(kalshi_prob.p_fill, poly_prob.p_fill)
        
        # Determine confidence
        max_staleness = max(kalshi_staleness, poly_staleness)
        if max_staleness < 500 and combined_p_fill > 0.5:
            confidence = "High"
        elif max_staleness < 1500 and combined_p_fill > 0.3:
            confidence = "Medium"
        else:
            confidence = "Low"
        
        # Edge-adjusted confidence override
        # For high-edge opportunities with good combined cost, upgrade Low to Medium-Override
        if confidence == "Low" and edge_bps >= 300 and combined_cost_per_contract <= 0.92:
            confidence = "Medium-Override"
            self.confidence_overrides += 1
            print(f"  ⚡ Confidence upgraded to Medium-Override (edge={edge_bps}bps, cost=${combined_cost_per_contract:.2f})")
        
        # Build description
        reason = (
            f"Dutch Book: Buy {kalshi_team}@${kalshi_result.vwap_price:.3f} (Kalshi) + "
            f"{poly_team}@${poly_result.vwap_price:.3f} (Poly) = ${combined_cost_per_contract:.3f} < $1.00"
        )
        
        return DutchBookOpportunity(
            event_id=event_id,
            timestamp=time.time(),
            # Kalshi leg
            kalshi_team=kalshi_team,
            kalshi_ticker=kalshi_ticker,
            kalshi_ask=kalshi_book['asks'][0][0],
            kalshi_ask_size=kalshi_book['asks'][0][1],
            kalshi_vwap=kalshi_result.vwap_price,
            # Polymarket leg
            poly_team=poly_team,
            poly_token_id=poly_token_id,
            poly_ask=poly_book['asks'][0][0],
            poly_ask_size=poly_book['asks'][0][1],
            poly_vwap=poly_result.vwap_price,
            # Edge calculation
            combined_cost=combined_cost_per_contract,
            guaranteed_payout=guaranteed_payout,
            gross_edge=gross_edge_total,
            kalshi_fee=kalshi_fee,
            poly_fee=poly_fee,
            total_fees=total_fees,
            net_edge=net_edge,
            edge_bps=edge_bps,
            # Execution
            size=min_size,
            kalshi_cost=kalshi_cost,
            poly_cost=poly_cost,
            total_cost=total_cost,
            # Slippage
            kalshi_slippage_bps=kalshi_result.slippage_bps,
            poly_slippage_bps=poly_result.slippage_bps,
            total_slippage_bps=kalshi_result.slippage_bps + poly_result.slippage_bps,
            # Risk
            kalshi_p_fill=kalshi_prob.p_fill,
            poly_p_fill=poly_prob.p_fill,
            combined_p_fill=combined_p_fill,
            # Staleness
            kalshi_staleness_ms=kalshi_staleness,
            poly_staleness_ms=poly_staleness,
            max_staleness_ms=max(kalshi_staleness, poly_staleness),
            # Metadata
            kalshi_levels_used=kalshi_result.levels_used,
            poly_levels_used=poly_result.levels_used,
            reason=reason,
            confidence=confidence
        )
    
    def get_stats(self) -> Dict:
        """Get detector statistics"""
        return {
            'opportunities_detected': self.opportunities_detected,
            'opportunities_filtered': self.opportunities_filtered,
            'confidence_overrides': self.confidence_overrides,
            'last_scan_time': self.last_scan_time,
            'scan_stats': self.scan_stats.copy(),
            'config': self.config.copy()
        }
    
    def update_config(self, **kwargs):
        """Update configuration parameters"""
        self.config.update(kwargs)
        print(f"✓ Updated config: {kwargs}")


# Test/Example usage
def test_dutch_book_detector():
    """Test the Dutch Book detector"""
    from orderbook_manager import OrderbookManager
    from depth_calculator import DepthCalculator
    from race_model import RaceModel
    
    # Initialize components
    ob_manager = OrderbookManager()
    calc = DepthCalculator()
    race = RaceModel()
    detector = ArbDetector(ob_manager, calc, race)
    
    # Register a test market with both teams
    event_id = "test-nba-game"
    ob_manager.register_market(event_id, {
        'kalshi_tickers': ['TEST-GAME-IND', 'TEST-GAME-CHA'],
        'poly_token_ids': {'IND': 'token-ind-123', 'CHA': 'token-cha-456'}
    })
    
    # Add orderbooks - Dutch Book opportunity exists:
    # Indiana on Kalshi: ask @ $0.55
    # Charlotte on Polymarket: ask @ $0.40
    # Combined: $0.95 < $1.00 = 5% gross edge!
    
    # Kalshi Indiana market (we're buying, so look at asks)
    ob_manager.update_orderbook_both_sides(
        'kalshi:TEST-GAME-IND', 'kalshi',
        bids=[(0.54, 100), (0.53, 150)],  # Not used for Dutch Book
        asks=[(0.55, 120), (0.56, 180)]   # We buy at ask
    )
    
    # Kalshi Charlotte market
    ob_manager.update_orderbook_both_sides(
        'kalshi:TEST-GAME-CHA', 'kalshi',
        bids=[(0.44, 100), (0.43, 150)],
        asks=[(0.46, 120), (0.47, 180)]
    )
    
    # Polymarket Indiana token
    ob_manager.update_orderbook_both_sides(
        f'{event_id}:polymarket:IND', 'polymarket',
        bids=[(0.53, 150), (0.52, 200)],
        asks=[(0.54, 100), (0.55, 120)]
    )
    
    # Polymarket Charlotte token
    ob_manager.update_orderbook_both_sides(
        f'{event_id}:polymarket:CHA', 'polymarket',
        bids=[(0.39, 150), (0.38, 200)],
        asks=[(0.40, 100), (0.41, 120)]   # We buy at ask
    )
    
    print("\n" + "="*60)
    print("Test: Dutch Book Arbitrage Detector")
    print("="*60)
    
    print("\nMarket Setup:")
    print("  Kalshi Indiana ask: $0.55")
    print("  Polymarket Charlotte ask: $0.40")
    print("  Combined: $0.95 < $1.00 payout")
    print("  Expected gross edge: 5%")
    
    # Scan for opportunities
    opportunities = detector.scan_for_opportunities()
    
    print(f"\nFound {len(opportunities)} Dutch Book opportunities:")
    
    for i, opp in enumerate(opportunities, 1):
        print(f"\n--- Opportunity #{i} ---")
        print(f"Event: {opp.event_id}")
        print(f"Strategy: Buy {opp.kalshi_team} on Kalshi + Buy {opp.poly_team} on Polymarket")
        print(f"Pricing:")
        print(f"  Kalshi {opp.kalshi_team} VWAP: ${opp.kalshi_vwap:.4f}")
        print(f"  Polymarket {opp.poly_team} VWAP: ${opp.poly_vwap:.4f}")
        print(f"  Combined cost: ${opp.combined_cost:.4f}")
        print(f"  Guaranteed payout: ${opp.guaranteed_payout:.2f}")
        print(f"Execution:")
        print(f"  Size: {opp.size:.2f} contracts")
        print(f"  Kalshi cost: ${opp.kalshi_cost:.2f}")
        print(f"  Polymarket cost: ${opp.poly_cost:.2f}")
        print(f"  Total cost: ${opp.total_cost:.2f}")
        print(f"Profit:")
        print(f"  Gross edge: ${opp.gross_edge:.2f}")
        print(f"  Fees: ${opp.total_fees:.2f} (Kalshi: ${opp.kalshi_fee:.2f}, Poly: ${opp.poly_fee:.2f})")
        print(f"  Net edge: ${opp.net_edge:.2f} ({opp.edge_bps}bps)")
        print(f"Fill probability: {opp.combined_p_fill:.1%}")
        print(f"Confidence: {opp.confidence}")
        print(f"Reason: {opp.reason}")
    
    # Stats
    print("\n" + "="*60)
    print("Stats:", detector.get_stats())
    print("="*60)


if __name__ == "__main__":
    test_dutch_book_detector()
