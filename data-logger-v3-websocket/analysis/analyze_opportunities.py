"""
Arbitrage Opportunity Analysis

Analyzes collected price data to find arbitrage opportunities.
Runs AFTER data collection is complete.

This script:
1. Loads price snapshots from database
2. Finds time-matched prices (within 5-second window)
3. Calculates arbitrage opportunities
4. Accounts for exchange fees (Kalshi 7%, Polymarket 2%)
5. Generates detailed report

Usage:
    python analyze_opportunities.py
    python analyze_opportunities.py --db ../data/market_data.db
    python analyze_opportunities.py --window 10
"""

import argparse
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict


class ArbitrageAnalyzer:
    """Analyzes price data for arbitrage opportunities"""
    
    # Exchange fee percentages
    KALSHI_FEE_PCT = 0.07  # 7%
    POLYMARKET_FEE_PCT = 0.02  # 2%
    
    def __init__(self, db_path="data/market_data.db"):
        """Initialize analyzer
        
        Args:
            db_path: Path to SQLite database
        """
        base_dir = Path(__file__).parent.parent
        self.db_path = base_dir / db_path
        
        if not self.db_path.exists():
            print(f"✗ Database not found: {self.db_path}")
            print(f"  Run data_logger.py first to collect data")
            sys.exit(1)
        
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        print(f"✓ Connected to database: {self.db_path}")
    
    def get_price_snapshots(self, event_id=None):
        """Get all price snapshots, optionally filtered by event
        
        Args:
            event_id: Optional event ID to filter
        
        Returns:
            list: List of price snapshot dicts
        """
        cursor = self.conn.cursor()
        
        if event_id:
            cursor.execute("""
                SELECT * FROM price_snapshots
                WHERE event_id = ?
                ORDER BY timestamp
            """, (event_id,))
        else:
            cursor.execute("""
                SELECT * FROM price_snapshots
                ORDER BY event_id, timestamp
            """)
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_tracked_markets(self):
        """Get all tracked markets
        
        Returns:
            list: List of tracked market dicts
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM tracked_markets WHERE enabled = 1")
        return [dict(row) for row in cursor.fetchall()]
    
    def parse_timestamp(self, timestamp_str):
        """Parse ISO timestamp string to datetime
        
        Args:
            timestamp_str: ISO format timestamp string
        
        Returns:
            datetime: Parsed datetime object
        """
        # Handle various ISO formats
        for fmt in ["%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
            try:
                return datetime.strptime(timestamp_str.split('+')[0].split('Z')[0], fmt)
            except ValueError:
                continue
        return None
    
    def find_time_matched_pairs(self, snapshots, window_seconds=5):
        """Find Kalshi/Polymarket price pairs within time window
        
        Args:
            snapshots: List of price snapshots
            window_seconds: Maximum time difference (seconds)
        
        Returns:
            list: List of matched pairs (kalshi_snapshot, polymarket_snapshot, time_diff)
        """
        # Separate by platform
        kalshi_snaps = [s for s in snapshots if s['platform'] == 'kalshi']
        poly_snaps = [s for s in snapshots if s['platform'] == 'polymarket']
        
        matched_pairs = []
        
        for k_snap in kalshi_snaps:
            k_time = self.parse_timestamp(k_snap['timestamp'])
            if not k_time:
                continue
            
            # Find closest Polymarket snapshot within window
            best_match = None
            best_time_diff = float('inf')
            
            for p_snap in poly_snaps:
                p_time = self.parse_timestamp(p_snap['timestamp'])
                if not p_time:
                    continue
                
                time_diff = abs((k_time - p_time).total_seconds())
                
                if time_diff <= window_seconds and time_diff < best_time_diff:
                    best_match = p_snap
                    best_time_diff = time_diff
            
            if best_match:
                matched_pairs.append((k_snap, best_match, best_time_diff))
        
        return matched_pairs
    
    def calculate_arbitrage(self, kalshi_price, poly_price, position_size=1.0):
        """Calculate arbitrage profit/loss
        
        For arbitrage, we need complementary outcomes:
        - Buy Team A to WIN on one platform
        - Buy Team B to WIN on other platform (or same team to LOSE)
        
        Formula:
            Total Cost = kalshi_cost + polymarket_cost
            Gross Profit = 1.0 (we win $1 on one side)
            Net Profit = Gross Profit - Total Cost - Fees
        
        Args:
            kalshi_price: Kalshi price (0-1)
            poly_price: Polymarket price (0-1)
            position_size: Position size in dollars
        
        Returns:
            dict: Arbitrage calculation results
        """
        if kalshi_price is None or poly_price is None:
            return None
        
        # Total cost for both positions
        total_cost = kalshi_price + poly_price
        
        # Calculate fees
        kalshi_fee = kalshi_price * self.KALSHI_FEE_PCT
        poly_fee = poly_price * self.POLYMARKET_FEE_PCT
        total_fees = kalshi_fee + poly_fee
        
        # Profit calculations
        gross_profit = 1.0 - total_cost  # Before fees
        net_profit = gross_profit - total_fees  # After fees
        
        # ROI (return on investment)
        roi = (net_profit / total_cost * 100) if total_cost > 0 else 0
        
        # Opportunity exists if total cost < 1.0
        is_opportunity = total_cost < 1.0
        is_profitable = net_profit > 0
        
        return {
            'kalshi_price': kalshi_price,
            'poly_price': poly_price,
            'total_cost': total_cost,
            'kalshi_fee': kalshi_fee,
            'poly_fee': poly_fee,
            'total_fees': total_fees,
            'gross_profit': gross_profit,
            'net_profit': net_profit,
            'roi': roi,
            'is_opportunity': is_opportunity,
            'is_profitable': is_profitable
        }
    
    def analyze_event(self, event_id, window_seconds=5):
        """Analyze one event for arbitrage opportunities
        
        Args:
            event_id: Event identifier
            window_seconds: Time matching window
        
        Returns:
            dict: Analysis results
        """
        snapshots = self.get_price_snapshots(event_id)
        
        if not snapshots:
            return {
                'event_id': event_id,
                'error': 'No price data found'
            }
        
        # Find time-matched pairs
        matched_pairs = self.find_time_matched_pairs(snapshots, window_seconds)
        
        # Analyze each matched pair for arbitrage
        opportunities = []
        
        for k_snap, p_snap, time_diff in matched_pairs:
            # We want complementary outcomes
            # If both are tracking the same outcome (e.g., Team A YES), we compare:
            # - Kalshi YES price vs Polymarket NO price
            # - Kalshi NO price vs Polymarket YES price
            
            # Try multiple combinations to find arbitrage
            combinations = [
                {
                    'kalshi_side': 'yes',
                    'poly_side': 'no',
                    'kalshi_price': k_snap['yes_price'],
                    'poly_price': p_snap['no_price'],
                    'description': f"Kalshi YES + Polymarket NO"
                },
                {
                    'kalshi_side': 'no',
                    'poly_side': 'yes',
                    'kalshi_price': k_snap['no_price'],
                    'poly_price': p_snap['yes_price'],
                    'description': f"Kalshi NO + Polymarket YES"
                }
            ]
            
            for combo in combinations:
                arb = self.calculate_arbitrage(
                    combo['kalshi_price'],
                    combo['poly_price']
                )
                
                if arb and arb['is_opportunity']:
                    opportunities.append({
                        'timestamp': k_snap['timestamp'],
                        'time_diff': time_diff,
                        'kalshi_market': k_snap['market_id'],
                        'poly_market': p_snap['market_id'],
                        'kalshi_side': combo['kalshi_side'],
                        'poly_side': combo['poly_side'],
                        'description': combo['description'],
                        **arb
                    })
        
        # Calculate statistics
        profitable_opps = [o for o in opportunities if o['is_profitable']]
        
        return {
            'event_id': event_id,
            'total_snapshots': len(snapshots),
            'kalshi_snapshots': len([s for s in snapshots if s['platform'] == 'kalshi']),
            'poly_snapshots': len([s for s in snapshots if s['platform'] == 'polymarket']),
            'matched_pairs': len(matched_pairs),
            'opportunities_found': len(opportunities),
            'profitable_opportunities': len(profitable_opps),
            'opportunities': opportunities,
            'best_opportunity': max(profitable_opps, key=lambda x: x['net_profit']) if profitable_opps else None,
            'avg_profit': sum(o['net_profit'] for o in profitable_opps) / len(profitable_opps) if profitable_opps else 0,
            'avg_roi': sum(o['roi'] for o in profitable_opps) / len(profitable_opps) if profitable_opps else 0
        }
    
    def analyze_all_events(self, window_seconds=5):
        """Analyze all tracked events
        
        Args:
            window_seconds: Time matching window
        
        Returns:
            dict: Complete analysis results
        """
        markets = self.get_tracked_markets()
        
        print(f"\n{'=' * 70}")
        print(f"Analyzing {len(markets)} market(s)...")
        print(f"Time matching window: {window_seconds} seconds")
        print(f"{'=' * 70}\n")
        
        results = []
        
        for market in markets:
            event_id = market['event_id']
            description = market['description']
            
            print(f"Analyzing: {description}")
            result = self.analyze_event(event_id, window_seconds)
            result['description'] = description
            results.append(result)
            
            # Print quick summary
            if result.get('error'):
                print(f"  ✗ {result['error']}")
            else:
                print(f"  ✓ {result['matched_pairs']} matched pairs")
                print(f"  ✓ {result['opportunities_found']} opportunities found")
                print(f"  ✓ {result['profitable_opportunities']} profitable (after fees)")
                
                if result['best_opportunity']:
                    best = result['best_opportunity']
                    print(f"  💰 Best: ${best['net_profit']:.4f} profit ({best['roi']:.2f}% ROI)")
            print()
        
        return results
    
    def generate_report(self, results):
        """Generate detailed analysis report
        
        Args:
            results: Analysis results from analyze_all_events()
        """
        print("\n" + "=" * 70)
        print("ARBITRAGE ANALYSIS REPORT")
        print("=" * 70)
        
        # Overall statistics
        total_opportunities = sum(r.get('opportunities_found', 0) for r in results)
        total_profitable = sum(r.get('profitable_opportunities', 0) for r in results)
        total_snapshots = sum(r.get('total_snapshots', 0) for r in results)
        
        print(f"\nOverall Statistics:")
        print(f"  Markets analyzed:          {len(results)}")
        print(f"  Total price snapshots:     {total_snapshots}")
        print(f"  Opportunities found:       {total_opportunities}")
        print(f"  Profitable opportunities:  {total_profitable}")
        
        if total_opportunities > 0:
            profit_rate = (total_profitable / total_opportunities) * 100
            print(f"  Profitability rate:        {profit_rate:.1f}%")
        
        # Per-market details
        print(f"\n{'─' * 70}")
        print("Per-Market Analysis:")
        print(f"{'─' * 70}")
        
        for result in results:
            if result.get('error'):
                print(f"\n❌ {result['description']}")
                print(f"   Error: {result['error']}")
                continue
            
            print(f"\n📊 {result['description']}")
            print(f"   Event ID: {result['event_id']}")
            print(f"   Data points: {result['kalshi_snapshots']} Kalshi, {result['poly_snapshots']} Polymarket")
            print(f"   Time-matched pairs: {result['matched_pairs']}")
            print(f"   Opportunities: {result['opportunities_found']} total, {result['profitable_opportunities']} profitable")
            
            if result['profitable_opportunities'] > 0:
                print(f"   Average profit: ${result['avg_profit']:.4f}")
                print(f"   Average ROI: {result['avg_roi']:.2f}%")
                
                best = result['best_opportunity']
                print(f"\n   💰 Best Opportunity:")
                print(f"      Timestamp: {best['timestamp']}")
                print(f"      Strategy: {best['description']}")
                print(f"      Kalshi price: ${best['kalshi_price']:.4f}")
                print(f"      Polymarket price: ${best['poly_price']:.4f}")
                print(f"      Total cost: ${best['total_cost']:.4f}")
                print(f"      Fees: ${best['total_fees']:.4f}")
                print(f"      Net profit: ${best['net_profit']:.4f}")
                print(f"      ROI: {best['roi']:.2f}%")
        
        # Conclusions
        print(f"\n{'=' * 70}")
        print("CONCLUSIONS")
        print(f"{'=' * 70}")
        
        if total_profitable == 0:
            print("\n❌ NO PROFITABLE ARBITRAGE OPPORTUNITIES FOUND")
            print("\nPossible reasons:")
            print("  1. Markets are efficient - prices are aligned")
            print("  2. Fees (7% Kalshi + 2% Polymarket) eliminate profit margins")
            print("  3. Not enough data collected yet")
            print("  4. Time matching window too strict (try increasing --window)")
            print("  5. Wrong market sides being compared")
        else:
            print(f"\n✅ FOUND {total_profitable} PROFITABLE OPPORTUNITIES")
            
            # Calculate if opportunities last long enough
            all_opps = []
            for r in results:
                all_opps.extend(r.get('opportunities', []))
            
            profitable_opps = [o for o in all_opps if o['is_profitable']]
            avg_profit = sum(o['net_profit'] for o in profitable_opps) / len(profitable_opps)
            max_profit = max(o['net_profit'] for o in profitable_opps)
            
            print(f"\n   Average profit: ${avg_profit:.4f} per opportunity")
            print(f"   Maximum profit: ${max_profit:.4f}")
            
            # Duration analysis
            time_diffs = [o['time_diff'] for o in profitable_opps]
            avg_time_diff = sum(time_diffs) / len(time_diffs)
            
            print(f"\n   Timing Analysis:")
            print(f"   Average time between snapshots: {avg_time_diff:.1f} seconds")
            print(f"   Min time difference: {min(time_diffs):.1f} seconds")
            print(f"   Max time difference: {max(time_diffs):.1f} seconds")
            
            if avg_time_diff < 2:
                print("\n   ⚡ Opportunities exist within 2-second windows!")
                print("      This requires FAST execution.")
            elif avg_time_diff < 5:
                print("\n   ⏱️  Opportunities exist within 5-second windows")
                print("      Fast execution required, but feasible.")
            else:
                print("\n   ⏳ Opportunities last several seconds")
                print("      Should be executable with normal API calls.")
        
        print(f"\n{'=' * 70}\n")
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Analyze collected price data for arbitrage opportunities",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analyze_opportunities.py
  python analyze_opportunities.py --db ../data/market_data.db
  python analyze_opportunities.py --window 10

This script analyzes data AFTER collection is complete.
Run data_logger.py first to collect price data.
        """
    )
    
    parser.add_argument(
        "--db",
        type=str,
        default="../data/market_data.db",
        help="Path to database file"
    )
    
    parser.add_argument(
        "--window",
        type=int,
        default=5,
        help="Time matching window in seconds (default: 5)"
    )
    
    args = parser.parse_args()
    
    # Create analyzer
    analyzer = ArbitrageAnalyzer(db_path=args.db)
    
    # Run analysis
    results = analyzer.analyze_all_events(window_seconds=args.window)
    
    # Generate report
    analyzer.generate_report(results)
    
    # Close
    analyzer.close()


if __name__ == "__main__":
    main()

