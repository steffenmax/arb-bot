"""
Enhanced Data Logger with Orderbook Depth Collection

Collects both top-of-book prices AND full orderbook depth in parallel.
Uses parallel fetching to maintain fast collection cycles (~2-3 seconds).
"""

import argparse
import json
import time
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from db_setup import DatabaseManager
from kalshi_client import KalshiClient
from polymarket_client import PolymarketClient


class DepthDataLogger:
    """Enhanced data logger with orderbook depth collection"""
    
    def __init__(self, config_path="config/settings.json", markets_path="config/markets.json"):
        self.config = self.load_config(config_path)
        self.markets = self.load_markets(markets_path)
        
        self.db = None
        self.kalshi = None
        self.polymarket = None
        
        self.running = True
        self.cycle_count = 0
        
        # Statistics
        self.total_kalshi_success = 0
        self.total_kalshi_failed = 0
        self.total_polymarket_success = 0
        self.total_polymarket_failed = 0
        self.total_depth_levels = 0
        
        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        print("\n\n⚠️  Shutdown signal received...")
        self.running = False
    
    def load_config(self, path):
        """Load configuration from JSON"""
        with open(path, 'r') as f:
            return json.load(f)
    
    def load_markets(self, path):
        """Load markets configuration"""
        with open(path, 'r') as f:
            data = json.load(f)
            return [m for m in data.get("markets", []) 
                   if m.get("kalshi", {}).get("enabled") or m.get("polymarket", {}).get("enabled")]
    
    def setup(self):
        """Initialize database and API clients"""
        print("=" * 70)
        print("🚀 Enhanced Data Logger with Orderbook Depth - Starting...")
        print("=" * 70)
        
        # Initialize database
        db_path = self.config.get("database", {}).get("path", "data/market_data.db")
        self.db = DatabaseManager(db_path)
        self.db.create_tables()
        
        # Initialize Kalshi
        kalshi_config = self.config.get("kalshi", {})
        if kalshi_config.get("enabled"):
            self.kalshi = KalshiClient(
                api_key=kalshi_config.get("api_key"),
                private_key_path=kalshi_config.get("private_key_path")
            )
        
        # Initialize Polymarket
        poly_config = self.config.get("polymarket", {})
        if poly_config.get("enabled"):
            self.polymarket = PolymarketClient()
        
        print(f"\n✓ Tracking {len(self.markets)} markets")
        print(f"✓ Collection interval: {self.config.get('collection', {}).get('interval_seconds', 1)}s")
        print(f"✓ Orderbook depth: ENABLED")
    
    def run_collection_cycle(self):
        """Run one complete collection cycle with orderbook depth"""
        self.cycle_count += 1
        cycle_start = time.time()
        
        print(f"\n{'=' * 70}")
        print(f"Cycle #{self.cycle_count} - {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'=' * 70}")
        
        log_id = self.db.start_collection_cycle(self.cycle_count)
        
        cycle_kalshi_success = 0
        cycle_kalshi_failed = 0
        cycle_polymarket_success = 0
        cycle_polymarket_failed = 0
        cycle_depth_levels = 0
        errors = []
        
        # Phase 1: Collect all market and orderbook data in parallel
        kalshi_markets = {}
        kalshi_orderbooks = {}
        polymarket_orderbooks = {}
        
        if self.kalshi:
            print("⚡ Fetching Kalshi market data in parallel...")
            kalshi_tickers = []
            for market_config in self.markets:
                if market_config.get("kalshi", {}).get("enabled"):
                    # Fetch BOTH markets (main and opponent)
                    main_ticker = market_config["kalshi"]["markets"].get("main")
                    opponent_ticker = market_config["kalshi"]["markets"].get("opponent")
                    if main_ticker:
                        kalshi_tickers.append(main_ticker)
                    if opponent_ticker:
                        kalshi_tickers.append(opponent_ticker)
            
            # Parallel fetch market data (for accurate current prices)
            with ThreadPoolExecutor(max_workers=20) as executor:
                future_to_ticker = {
                    executor.submit(self.kalshi.get_market, ticker): ticker 
                    for ticker in kalshi_tickers
                }
                for future in as_completed(future_to_ticker):
                    ticker = future_to_ticker[future]
                    try:
                        market_data = future.result()
                        if market_data:
                            kalshi_markets[ticker] = market_data
                    except Exception as exc:
                        print(f"✗ Kalshi market {ticker}: {exc}")
            
            # Also fetch orderbooks for depth analysis
            with ThreadPoolExecutor(max_workers=20) as executor:
                future_to_ticker = {
                    executor.submit(self.kalshi.get_market_orderbook, ticker, depth=10): ticker 
                    for ticker in kalshi_tickers
                }
                for future in as_completed(future_to_ticker):
                    ticker = future_to_ticker[future]
                    try:
                        orderbook = future.result()
                        if orderbook:
                            kalshi_orderbooks[ticker] = orderbook
                    except Exception as exc:
                        print(f"✗ Kalshi orderbook {ticker}: {exc}")
            
            print(f"  ✓ Fetched {len(kalshi_markets)}/{len(kalshi_tickers)} markets with current prices")
            print(f"  ✓ Fetched {len(kalshi_orderbooks)}/{len(kalshi_tickers)} orderbooks for depth")
        
        if self.polymarket:
            print("⚡ Fetching Polymarket orderbooks in parallel...")
            poly_slugs = []
            for market_config in self.markets:
                if market_config.get("polymarket", {}).get("enabled"):
                    slug = market_config["polymarket"]["markets"].get("slug")
                    if slug:
                        poly_slugs.append(slug)
            
            # First get token IDs in parallel
            token_data_map = {}
            with ThreadPoolExecutor(max_workers=15) as executor:
                future_to_slug = {
                    executor.submit(self.polymarket.get_token_ids_from_slug, slug): slug 
                    for slug in poly_slugs
                }
                for future in as_completed(future_to_slug):
                    slug = future_to_slug[future]
                    try:
                        token_data = future.result()
                        if token_data:
                            token_data_map[slug] = token_data
                    except Exception as exc:
                        print(f"✗ Polymarket {slug}: {exc}")
            
            # Then fetch orderbooks for all tokens
            with ThreadPoolExecutor(max_workers=15) as executor:
                futures = []
                for slug, token_data in token_data_map.items():
                    for token in token_data['tokens']:
                        future = executor.submit(self.polymarket.get_orderbook, token['token_id'])
                        futures.append((future, slug, token))
                
                for future, slug, token in futures:
                    try:
                        orderbook = future.result()
                        if orderbook:
                            if slug not in polymarket_orderbooks:
                                polymarket_orderbooks[slug] = {}
                            polymarket_orderbooks[slug][token['outcome']] = orderbook
                    except Exception as exc:
                        print(f"✗ Polymarket {slug}/{token['outcome']}: {exc}")
            
            print(f"  ✓ Fetched orderbooks for {len(polymarket_orderbooks)} games")
        
        # Phase 2: Log all data to database
        for market_config in self.markets:
            event_id = market_config["event_id"]
            
            # Log Kalshi data - BOTH markets (main and opponent)
            if market_config.get("kalshi", {}).get("enabled") and self.kalshi:
                # Process main market (team A)
                main_ticker = market_config["kalshi"]["markets"].get("main")
                team_a = market_config["teams"].get("team_a", "Unknown")
                
                if main_ticker and main_ticker in kalshi_markets:
                    market_data = kalshi_markets[main_ticker]
                    
                    # Log top-of-book snapshot (from market endpoint - accurate current prices)
                    yes_bid = market_data.get('yes_bid')
                    yes_ask = market_data.get('yes_ask')
                    no_bid = market_data.get('no_bid')
                    no_ask = market_data.get('no_ask')
                    
                    snapshot_id = self.db.log_price_snapshot(
                        event_id=event_id,
                        platform="kalshi",
                        market_id=main_ticker,
                        market_side=team_a,  # YES refers to team_a
                        yes_bid=yes_bid,
                        yes_ask=yes_ask,
                        no_bid=no_bid,
                        no_ask=no_ask,
                        volume=market_data.get('volume', 0),
                        liquidity=market_data.get('liquidity', 0),
                        timestamp=market_data['timestamp']
                    )
                    
                    # Log orderbook depth (if available)
                    if snapshot_id and main_ticker in kalshi_orderbooks:
                        orderbook = kalshi_orderbooks[main_ticker]
                        for side, bids, asks in [
                            ('yes', orderbook['yes_bids'], orderbook['yes_asks']),
                            ('no', orderbook['no_bids'], orderbook['no_asks'])
                        ]:
                            if bids:
                                levels = self.db.log_orderbook_snapshot(
                                    snapshot_id, event_id, "kalshi", main_ticker,
                                    side, 'bid', bids[:10], orderbook['timestamp']
                                )
                                cycle_depth_levels += levels
                            
                            if asks:
                                levels = self.db.log_orderbook_snapshot(
                                    snapshot_id, event_id, "kalshi", main_ticker,
                                    side, 'ask', asks[:10], orderbook['timestamp']
                                )
                                cycle_depth_levels += levels
                    
                    cycle_kalshi_success += 1
                else:
                    if main_ticker:
                        cycle_kalshi_failed += 1
                
                # Process opponent market (team B)
                opponent_ticker = market_config["kalshi"]["markets"].get("opponent")
                team_b = market_config["teams"].get("team_b", "Unknown")
                
                if opponent_ticker and opponent_ticker in kalshi_markets:
                    market_data = kalshi_markets[opponent_ticker]
                    
                    # Log top-of-book snapshot (from market endpoint - accurate current prices)
                    yes_bid = market_data.get('yes_bid')
                    yes_ask = market_data.get('yes_ask')
                    no_bid = market_data.get('no_bid')
                    no_ask = market_data.get('no_ask')
                    
                    snapshot_id = self.db.log_price_snapshot(
                        event_id=event_id,
                        platform="kalshi",
                        market_id=opponent_ticker,
                        market_side=team_b,  # YES refers to team_b
                        yes_bid=yes_bid,
                        yes_ask=yes_ask,
                        no_bid=no_bid,
                        no_ask=no_ask,
                        volume=market_data.get('volume', 0),
                        liquidity=market_data.get('liquidity', 0),
                        timestamp=market_data['timestamp']
                    )
                    
                    # Log orderbook depth (if available)
                    if snapshot_id and opponent_ticker in kalshi_orderbooks:
                        orderbook = kalshi_orderbooks[opponent_ticker]
                        for side, bids, asks in [
                            ('yes', orderbook['yes_bids'], orderbook['yes_asks']),
                            ('no', orderbook['no_bids'], orderbook['no_asks'])
                        ]:
                            if bids:
                                levels = self.db.log_orderbook_snapshot(
                                    snapshot_id, event_id, "kalshi", opponent_ticker,
                                    side, 'bid', bids[:10], orderbook['timestamp']
                                )
                                cycle_depth_levels += levels
                            
                            if asks:
                                levels = self.db.log_orderbook_snapshot(
                                    snapshot_id, event_id, "kalshi", opponent_ticker,
                                    side, 'ask', asks[:10], orderbook['timestamp']
                                )
                                cycle_depth_levels += levels
                    
                    cycle_kalshi_success += 1
                else:
                    if opponent_ticker:
                        cycle_kalshi_failed += 1
            
            # Log Polymarket data
            if market_config.get("polymarket", {}).get("enabled") and self.polymarket:
                slug = market_config["polymarket"]["markets"].get("slug")
                
                if slug in polymarket_orderbooks:
                    for outcome, orderbook in polymarket_orderbooks[slug].items():
                        # Log top-of-book
                        best_bid = orderbook['bids'][0][0] if orderbook['bids'] else None
                        best_ask = orderbook['asks'][0][0] if orderbook['asks'] else None
                        
                        # Calculate total liquidity from orderbook
                        # Sum all available liquidity on both sides (in dollars)
                        total_liquidity = 0
                        for price, size in orderbook['bids']:
                            total_liquidity += price * size
                        for price, size in orderbook['asks']:
                            total_liquidity += price * size
                        
                        # Convert to cents for consistent storage with Kalshi
                        liquidity_cents = int(total_liquidity * 100)
                        
                        snapshot_id = self.db.log_price_snapshot(
                            event_id=event_id,
                            platform="polymarket",
                            market_id=slug,
                            market_side=outcome,
                            yes_price=best_ask,
                            yes_bid=best_bid,
                            yes_ask=best_ask,
                            liquidity=liquidity_cents,
                            timestamp=orderbook['timestamp']
                        )
                        
                        # Log orderbook depth
                        if snapshot_id:
                            if orderbook['bids']:
                                levels = self.db.log_orderbook_snapshot(
                                    snapshot_id, event_id, "polymarket", slug,
                                    'yes', 'bid', orderbook['bids'][:10], orderbook['timestamp']
                                )
                                cycle_depth_levels += levels
                            
                            if orderbook['asks']:
                                levels = self.db.log_orderbook_snapshot(
                                    snapshot_id, event_id, "polymarket", slug,
                                    'yes', 'ask', orderbook['asks'][:10], orderbook['timestamp']
                                )
                                cycle_depth_levels += levels
                        
                        cycle_polymarket_success += 1
        
        # Update statistics
        self.total_kalshi_success += cycle_kalshi_success
        self.total_kalshi_failed += cycle_kalshi_failed
        self.total_polymarket_success += cycle_polymarket_success
        self.total_polymarket_failed += cycle_polymarket_failed
        self.total_depth_levels += cycle_depth_levels
        
        self.db.complete_collection_cycle(
            log_id, cycle_kalshi_success, cycle_kalshi_failed,
            cycle_polymarket_success, cycle_polymarket_failed, errors
        )
        
        cycle_time = time.time() - cycle_start
        
        print(f"\n{'─' * 70}")
        print(f"Cycle #{self.cycle_count} Complete:")
        print(f"  Kalshi: {cycle_kalshi_success} markets, {cycle_depth_levels//4} depth levels/market")
        print(f"  Polymarket: {cycle_polymarket_success//2} games")
        print(f"  Cycle time: {cycle_time:.2f}s")
        print(f"{'─' * 70}")
    
    def run(self, hours=None):
        """Run data collection"""
        self.setup()
        
        if hours:
            end_time = datetime.now() + timedelta(hours=hours)
            print(f"\n🕐 Will run until: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print(f"\n♾️  Will run indefinitely (Ctrl+C to stop)")
        
        interval = self.config.get("collection", {}).get("interval_seconds", 1)
        
        print("\n" + "=" * 70)
        print("🏁 Starting collection...")
        print("=" * 70)
        
        try:
            while self.running:
                if hours and datetime.now() >= end_time:
                    print("\n⏰ Time limit reached")
                    break
                
                cycle_start = time.time()
                self.run_collection_cycle()
                
                # Wait for next cycle
                elapsed = time.time() - cycle_start
                wait_time = max(0, interval - elapsed)
                if wait_time > 0 and self.running:
                    time.sleep(wait_time)
        
        except KeyboardInterrupt:
            print("\n\n⚠️  Keyboard interrupt received")
        
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Clean shutdown"""
        print("\n" + "=" * 70)
        print("📊 FINAL STATISTICS")
        print("=" * 70)
        print(f"Total cycles: {self.cycle_count}")
        print(f"Kalshi: {self.total_kalshi_success} success, {self.total_kalshi_failed} failed")
        print(f"Polymarket: {self.total_polymarket_success} outcomes collected")
        print(f"Orderbook depth levels: {self.total_depth_levels:,}")
        print("=" * 70)
        
        if self.kalshi:
            self.kalshi.close()
        if self.polymarket:
            self.polymarket.close()
        
        print("\n✅ Shutdown complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enhanced data logger with orderbook depth")
    parser.add_argument("--hours", type=float, help="Number of hours to run")
    args = parser.parse_args()
    
    logger = DepthDataLogger()
    logger.run(hours=args.hours)

