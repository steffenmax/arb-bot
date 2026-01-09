"""
Prediction Market Data Logger

Main script for collecting price data from Kalshi and Polymarket.
This is a READ-ONLY data collection system - NO TRADING.

Collects price snapshots at regular intervals and stores them in SQLite database
for later analysis.

Usage:
    python data_logger.py --hours 24
    python data_logger.py --hours 48 --config config/settings.json
"""

import argparse
import json
import time
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path

from db_setup import DatabaseManager
from kalshi_client import KalshiClient
from polymarket_client import PolymarketClient


class DataLogger:
    """Main data collection orchestrator"""
    
    def __init__(self, config_path="config/settings.json", markets_path="config/markets.json"):
        """Initialize data logger
        
        Args:
            config_path: Path to settings config file
            markets_path: Path to markets config file
        """
        self.config_path = Path(config_path)
        self.markets_path = Path(markets_path)
        
        # Will be initialized in setup()
        self.config = None
        self.markets = None
        self.db = None
        self.kalshi = None
        self.polymarket = None
        
        # Statistics
        self.cycle_count = 0
        self.total_kalshi_success = 0
        self.total_kalshi_failed = 0
        self.total_polymarket_success = 0
        self.total_polymarket_failed = 0
        
        # Control flags
        self.running = True
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print("\n\n⚠️  Shutdown signal received. Finishing current cycle...")
        self.running = False
    
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
            print(f"✓ Loaded configuration from {self.config_path}")
            return True
        except FileNotFoundError:
            print(f"✗ Configuration file not found: {self.config_path}")
            print(f"  Create it using the template in the README")
            return False
        except json.JSONDecodeError as e:
            print(f"✗ Invalid JSON in configuration file: {e}")
            return False
    
    def load_markets(self):
        """Load markets configuration from JSON file"""
        try:
            with open(self.markets_path, 'r') as f:
                data = json.load(f)
                self.markets = data.get("markets", [])
            
            # Filter to enabled markets
            self.markets = [m for m in self.markets if m.get("kalshi", {}).get("enabled") or m.get("polymarket", {}).get("enabled")]
            
            print(f"✓ Loaded {len(self.markets)} active market(s) from {self.markets_path}")
            return True
        except FileNotFoundError:
            print(f"✗ Markets file not found: {self.markets_path}")
            print(f"  Create it using the template in the README")
            return False
        except json.JSONDecodeError as e:
            print(f"✗ Invalid JSON in markets file: {e}")
            return False
    
    def setup(self):
        """Initialize all components"""
        print("=" * 70)
        print("Prediction Market Data Logger - Setup")
        print("=" * 70)
        
        # Load configurations
        if not self.load_config():
            return False
        if not self.load_markets():
            return False
        
        if len(self.markets) == 0:
            print("✗ No markets configured for collection")
            return False
        
        # Initialize database
        db_path = self.config.get("database", {}).get("path", "data/market_data.db")
        self.db = DatabaseManager(db_path)
        self.db.create_tables()
        
        # Add tracked markets to database
        for market in self.markets:
            self.db.add_tracked_market(
                event_id=market["event_id"],
                description=market["description"],
                sport=market.get("sport"),
                event_date=market.get("event_date"),
                teams=market.get("teams"),
                kalshi_markets=market.get("kalshi", {}).get("markets"),
                polymarket_markets=market.get("polymarket", {}).get("markets")
            )
        print(f"✓ Added {len(self.markets)} markets to database")
        
        # Initialize API clients
        kalshi_config = self.config.get("kalshi", {})
        if kalshi_config.get("enabled", False):
            try:
                self.kalshi = KalshiClient(
                    api_key=kalshi_config.get("api_key"),
                    private_key_path=kalshi_config.get("private_key_path")
                )
                if not self.kalshi.health_check():
                    print("⚠️  Kalshi health check failed - will skip Kalshi collection")
                    self.kalshi = None
            except Exception as e:
                print(f"⚠️  Failed to initialize Kalshi client: {e}")
                self.kalshi = None
        else:
            print("⚠️  Kalshi disabled in config")
        
        polymarket_config = self.config.get("polymarket", {})
        if polymarket_config.get("enabled", False):
            self.polymarket = PolymarketClient()
            if not self.polymarket.health_check():
                print("⚠️  Polymarket health check failed - will skip Polymarket collection")
                self.polymarket = None
        else:
            print("⚠️  Polymarket disabled in config")
        
        if not self.kalshi and not self.polymarket:
            print("✗ No API clients available - check configuration")
            return False
        
        print("\n✓ Setup complete!")
        return True
    
    def collect_kalshi_markets(self, market_config):
        """Collect data from Kalshi for one market
        
        Kalshi: TWO separate markets per game (one per team)
        Each market has yes/no prices where YES = this team wins
        
        Args:
            market_config: Market configuration dict
        
        Returns:
            tuple: (success_count, failed_count)
        """
        if not self.kalshi:
            return (0, 0)
        
        kalshi_markets = market_config.get("kalshi", {}).get("markets", {})
        if not kalshi_markets:
            return (0, 0)
        
        # Get the team name that YES refers to (for labeling)
        # This tells us which team wins if YES happens
        yes_team = market_config.get("kalshi", {}).get("yes_refers_to", "Unknown")
        
        success = 0
        failed = 0
        
        for side, ticker in kalshi_markets.items():
            if not ticker:
                continue
            
            data = self.kalshi.get_market(ticker)
            
            if data:
                # Use team name as market_side for clarity
                # e.g., "Portland" instead of "main"
                market_side_label = yes_team
                
                # Store price snapshot
                self.db.log_price_snapshot(
                    event_id=market_config["event_id"],
                    platform="kalshi",
                    market_id=ticker,
                    market_side=market_side_label,
                    yes_price=data["yes_price"],
                    no_price=data["no_price"],
                    yes_bid=data["yes_bid"],
                    yes_ask=data["yes_ask"],
                    no_bid=data["no_bid"],
                    no_ask=data["no_ask"],
                    volume=data["volume"],
                    liquidity=data["liquidity"],
                    timestamp=data["timestamp"]
                )
                success += 1
            else:
                failed += 1
            
            # Small delay to respect rate limits
            time.sleep(0.1)
        
        return (success, failed)
    
    def collect_polymarket_markets(self, market_config):
        """Collect data from Polymarket for one market
        
        Polymarket: ONE condition_id returns BOTH team outcomes
        Unlike Kalshi (separate market per team), we only need to fetch once per game
        
        Args:
            market_config: Market configuration dict
        
        Returns:
            tuple: (success_count, failed_count)
        """
        if not self.polymarket:
            return (0, 0)
        
        polymarket_markets = market_config.get("polymarket", {}).get("markets", {})
        if not polymarket_markets:
            return (0, 0)
        
        success = 0
        failed = 0
        
        # Get the slug (preferred) or condition_id
        slug = polymarket_markets.get("slug")
        condition_id = polymarket_markets.get("game")
        
        if not slug and not condition_id:
            return (0, 0)
        
        # Fetch market data (returns both team outcomes)
        # Use slug if available (more reliable), fallback to condition_id
        if slug:
            data = self.polymarket.get_market_by_slug(slug)
        else:
            data = self.polymarket.get_market(condition_id)
        
        if data and data.get('outcomes'):
            # Check if market has real prices (not placeholder 0.5/0.5)
            has_real_prices = False
            for outcome in data['outcomes']:
                price = outcome.get('price')
                bid = outcome.get('bid')
                ask = outcome.get('ask')
                
                # Check for real prices (not 0.5) OR real bid/ask spread
                if price and price != 0.5:
                    has_real_prices = True
                    break
                if bid and ask and (ask - bid) < 0.9:
                    has_real_prices = True
                    break
            
            if not has_real_prices:
                # Skip markets with placeholder prices - they don't really exist yet
                print(f"    ⚠ Polymarket market has no real prices yet (showing 0.5/0.5 placeholders)")
                failed += 1
                return (success, failed)
            
            # Store a snapshot for EACH team outcome
            for outcome in data['outcomes']:
                team = outcome.get('team', 'Unknown')
                price = outcome.get('price')
                bid = outcome.get('bid')
                ask = outcome.get('ask')
                
                # Skip if no price data
                if price is None:
                    continue
                
                # Store price snapshot with team name as market_side
                self.db.log_price_snapshot(
                    event_id=market_config["event_id"],
                    platform="polymarket",
                    market_id=condition_id,
                    market_side=team,  # Use team name instead of "main"/"game"
                    yes_price=price,  # Polymarket doesn't have yes/no, just team price
                    no_price=None,  # N/A for Polymarket
                    yes_bid=bid,
                    yes_ask=ask,
                    no_bid=None,  # N/A for Polymarket
                    no_ask=None,  # N/A for Polymarket
                    volume=data["volume"],
                    liquidity=data["liquidity"],
                    timestamp=data["timestamp"]
                )
                success += 1
        else:
            failed += 1
        
        # Small delay to respect rate limits
        time.sleep(0.1)
        
        return (success, failed)
    
    def run_collection_cycle(self):
        """Run one complete collection cycle (with parallel fetching)"""
        self.cycle_count += 1
        
        print(f"\n{'=' * 70}")
        print(f"Collection Cycle #{self.cycle_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'=' * 70}")
        
        cycle_start = time.time()
        
        # Start collection log
        log_id = self.db.start_collection_cycle(self.cycle_count)
        
        cycle_kalshi_success = 0
        cycle_kalshi_failed = 0
        cycle_polymarket_success = 0
        cycle_polymarket_failed = 0
        errors = []
        
        # PHASE 1: Collect all tickers/slugs to fetch (PARALLEL PREPARATION)
        kalshi_tickers = []
        kalshi_market_map = {}  # ticker -> market config
        
        polymarket_slugs = []
        polymarket_market_map = {}  # slug -> market config
        polymarket_seen = set()  # Track unique condition_ids
        
        for market in self.markets:
            # Collect Kalshi tickers
            if self.kalshi and market.get("kalshi", {}).get("enabled"):
                kalshi_markets = market.get("kalshi", {}).get("markets", {})
                for side, ticker in kalshi_markets.items():
                    if ticker:
                        kalshi_tickers.append(ticker)
                        kalshi_market_map[ticker] = market
            
            # Collect Polymarket slugs (avoid duplicates)
            if self.polymarket and market.get("polymarket", {}).get("enabled"):
                poly_markets = market.get("polymarket", {}).get("markets", {})
                slug = poly_markets.get("slug")
                condition_id = poly_markets.get("game")
                
                if slug and condition_id not in polymarket_seen:
                    polymarket_slugs.append(slug)
                    polymarket_market_map[slug] = market
                    polymarket_seen.add(condition_id)
        
        # PHASE 2: Fetch all markets in PARALLEL (THE FAST PART!)
        fetch_start = time.time()
        
        kalshi_results = {}
        if self.kalshi and kalshi_tickers:
            print(f"\n⚡ Fetching {len(kalshi_tickers)} Kalshi markets in parallel...")
            kalshi_results = self.kalshi.get_markets_parallel(kalshi_tickers, max_workers=20)
            print(f"  ✓ Fetched {len(kalshi_results)}/{len(kalshi_tickers)} in {time.time() - fetch_start:.2f}s")
        
        polymarket_results = {}
        if self.polymarket and polymarket_slugs:
            poly_fetch_start = time.time()
            print(f"\n⚡ Fetching {len(polymarket_slugs)} Polymarket markets in parallel...")
            polymarket_results = self.polymarket.get_markets_parallel(polymarket_slugs, max_workers=15)
            print(f"  ✓ Fetched {len(polymarket_results)}/{len(polymarket_slugs)} in {time.time() - poly_fetch_start:.2f}s")
        
        # PHASE 3: Process and store results
        print(f"\n{'─' * 70}")
        print("Processing collected data...")
        print(f"{'─' * 70}")
        
        # Process Kalshi results
        for ticker, data in kalshi_results.items():
            market = kalshi_market_map[ticker]
            yes_team = market.get("kalshi", {}).get("yes_refers_to", "Unknown")
            
            try:
                self.db.log_price_snapshot(
                    event_id=market["event_id"],
                    platform="kalshi",
                    market_id=ticker,
                    market_side=yes_team,
                    yes_price=data["yes_price"],
                    no_price=data["no_price"],
                    yes_bid=data["yes_bid"],
                    yes_ask=data["yes_ask"],
                    no_bid=data["no_bid"],
                    no_ask=data["no_ask"],
                    volume=data["volume"],
                    liquidity=data["liquidity"],
                    timestamp=data["timestamp"]
                )
                cycle_kalshi_success += 1
            except Exception as e:
                errors.append(f"Error storing Kalshi {ticker}: {e}")
                cycle_kalshi_failed += 1
        
        cycle_kalshi_failed += len(kalshi_tickers) - len(kalshi_results)
        
        # Process Polymarket results
        for slug, data in polymarket_results.items():
            market = polymarket_market_map[slug]
            
            if not data or not data.get('outcomes'):
                cycle_polymarket_failed += 1
                continue
            
            # Check for real prices
            has_real_prices = False
            for outcome in data['outcomes']:
                price = outcome.get('price')
                if price and price != 0.5:
                    has_real_prices = True
                    break
            
            if not has_real_prices:
                cycle_polymarket_failed += 1
                continue
            
            # Store each outcome
            condition_id = data.get('condition_id')
            for outcome in data['outcomes']:
                team = outcome.get('team', 'Unknown')
                price = outcome.get('price')
                
                if price is None:
                    continue
                
                try:
                    self.db.log_price_snapshot(
                        event_id=market["event_id"],
                        platform="polymarket",
                        market_id=condition_id,
                        market_side=team,
                        yes_price=price,
                        no_price=None,
                        yes_bid=outcome.get('bid'),
                        yes_ask=outcome.get('ask'),
                        no_bid=None,
                        no_ask=None,
                        volume=data["volume"],
                        liquidity=data["liquidity"],
                        timestamp=data["timestamp"]
                    )
                    cycle_polymarket_success += 1
                except Exception as e:
                    errors.append(f"Error storing Polymarket {slug} ({team}): {e}")
                    cycle_polymarket_failed += 1
        
        cycle_polymarket_failed += len(polymarket_slugs) - len(polymarket_results)
        
        # Complete collection log
        self.db.complete_collection_cycle(
            log_id=log_id,
            kalshi_success=cycle_kalshi_success,
            kalshi_failed=cycle_kalshi_failed,
            polymarket_success=cycle_polymarket_success,
            polymarket_failed=cycle_polymarket_failed,
            errors=errors if errors else None
        )
        
        # Update totals
        self.total_kalshi_success += cycle_kalshi_success
        self.total_kalshi_failed += cycle_kalshi_failed
        self.total_polymarket_success += cycle_polymarket_success
        self.total_polymarket_failed += cycle_polymarket_failed
        
        # Print cycle summary
        cycle_duration = time.time() - cycle_start
        print(f"\n{'─' * 70}")
        print(f"Cycle #{self.cycle_count} Complete ({cycle_duration:.2f}s):")
        print(f"  Kalshi:     {cycle_kalshi_success} markets collected, {cycle_kalshi_failed} failed")
        print(f"  Polymarket: {cycle_polymarket_success} outcomes collected, {cycle_polymarket_failed} failed")
        if cycle_polymarket_success > 0:
            games_collected = cycle_polymarket_success // 2  # 2 outcomes per game
            print(f"              ({games_collected} games × 2 teams = {cycle_polymarket_success} outcomes)")
        print(f"{'─' * 70}")
    
    def run(self, duration_hours=24):
        """Run data collection for specified duration
        
        Args:
            duration_hours: How long to run (hours)
        """
        collection_interval = self.config.get("collection", {}).get("interval_seconds", 30)
        end_time = datetime.now() + timedelta(hours=duration_hours)
        
        print("\n" + "=" * 70)
        print("Starting Data Collection")
        print("=" * 70)
        print(f"Duration:         {duration_hours} hours")
        print(f"Interval:         {collection_interval} seconds")
        print(f"Markets:          {len(self.markets)}")
        print(f"End time:         {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Database:         {self.db.db_path}")
        print("=" * 70)
        print("\n⚠️  This is READ-ONLY data collection - no trading will occur")
        print("Press Ctrl+C to stop gracefully\n")
        
        try:
            while self.running and datetime.now() < end_time:
                cycle_start = time.time()
                
                # Run collection cycle
                self.run_collection_cycle()
                
                # Calculate time to next cycle
                cycle_duration = time.time() - cycle_start
                sleep_time = max(0, collection_interval - cycle_duration)
                
                if self.running and datetime.now() < end_time:
                    next_cycle = datetime.now() + timedelta(seconds=sleep_time)
                    print(f"\n⏱️  Waiting {sleep_time:.1f}s until next cycle (at {next_cycle.strftime('%H:%M:%S')})")
                    
                    # Sleep in small chunks to allow graceful shutdown
                    for _ in range(int(sleep_time)):
                        if not self.running:
                            break
                        time.sleep(1)
        
        except KeyboardInterrupt:
            print("\n\n⚠️  Keyboard interrupt received")
        
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Clean shutdown"""
        print("\n" + "=" * 70)
        print("Shutting Down")
        print("=" * 70)
        
        # Print final statistics
        total_attempts = (self.total_kalshi_success + self.total_kalshi_failed + 
                         self.total_polymarket_success + self.total_polymarket_failed)
        
        print(f"\nFinal Statistics:")
        print(f"  Total cycles:            {self.cycle_count}")
        print(f"  Total snapshots:         {total_attempts}")
        print(f"  Kalshi markets:          {self.total_kalshi_success} collected, {self.total_kalshi_failed} failed")
        print(f"  Polymarket outcomes:     {self.total_polymarket_success} collected, {self.total_polymarket_failed} failed")
        if self.total_polymarket_success > 0:
            poly_games = self.total_polymarket_success // 2
            print(f"  Polymarket games:        ~{poly_games} games (2 outcomes each)")
        
        if total_attempts > 0:
            success_rate = ((self.total_kalshi_success + self.total_polymarket_success) / total_attempts) * 100
            print(f"  Success rate:        {success_rate:.1f}%")
        
        # Close connections
        if self.kalshi:
            self.kalshi.close()
        if self.polymarket:
            self.polymarket.close()
        if self.db:
            self.db.close()
        
        print("\n✓ Data collection complete!")
        print(f"  Database saved to: {self.db.db_path if self.db else 'N/A'}")
        print(f"\n  Next step: Run analysis with:")
        print(f"    python analysis/analyze_opportunities.py")
        print("=" * 70)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Prediction Market Data Logger - Read-only data collection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python data_logger.py --hours 24
  python data_logger.py --hours 48 --config my_config.json
  python data_logger.py --hours 1 --markets my_markets.json

After collection, analyze the data:
  python analysis/analyze_opportunities.py
        """
    )
    
    parser.add_argument(
        "--hours",
        type=float,
        default=24,
        help="How long to collect data (hours). Default: 24"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default="config/settings.json",
        help="Path to settings configuration file"
    )
    
    parser.add_argument(
        "--markets",
        type=str,
        default="config/markets.json",
        help="Path to markets configuration file"
    )
    
    args = parser.parse_args()
    
    # Create and run logger
    logger = DataLogger(
        config_path=args.config,
        markets_path=args.markets
    )
    
    if logger.setup():
        logger.run(duration_hours=args.hours)
    else:
        print("\n✗ Setup failed. Cannot start data collection.")
        sys.exit(1)


if __name__ == "__main__":
    main()

