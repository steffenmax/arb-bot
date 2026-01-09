"""
Production Arbitrage Bot - Main Execution Loop

Orchestrates all components to run a complete arbitrage trading system:
- WebSocket orderbook streaming
- Real-time arbitrage detection
- Risk management
- Execution (maker-hedge or taker+taker)
- Position tracking
- Fill logging

This is the entry point for running the bot in production.
"""

import asyncio
import json
import os
import sys
import time
import signal
from typing import Dict, Optional
from datetime import datetime
from dotenv import load_dotenv

# Import all components
from kalshi_websocket_client import KalshiWebSocketClient
from polymarket_websocket_client import PolymarketWebSocketClient
from orderbook_manager import OrderbookManager
from depth_calculator import DepthCalculator
from race_model import RaceModel
from arb_detector import ArbDetector, DutchBookOpportunity
from inventory_tracker import InventoryTracker, DutchBookPosition
from risk_manager import RiskManager, RiskLimits
from dutch_book_executor import DutchBookExecutor
from fill_logger import FillLogger

# Add parent dir to path for executor imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.executors.kalshi_executor import KalshiExecutor
from src.executors.polymarket_executor import PolymarketExecutor


class ArbBot:
    """
    Main arbitrage bot orchestrator
    
    Coordinates all components to detect and execute arbitrage opportunities.
    """
    
    def __init__(self, config_path: str = "config/bot_config.json"):
        """
        Initialize arbitrage bot
        
        Args:
            config_path: Path to configuration file
        """
        print("\n" + "="*60)
        print("INITIALIZING ARBITRAGE BOT")
        print("="*60 + "\n")
        
        # Check if paper trading mode
        if config_path and 'paper' in config_path.lower():
            print("🔔 PAPER TRADING MODE DETECTED")
            print("   No real orders will be placed")
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Load environment variables
        load_dotenv()
        
        # Initialize components
        self._init_components()
        
        # Bot state
        self.running = False
        self.opportunities_detected = 0
        self.trades_executed = 0
        self.total_pnl = 0
        
        # Performance tracking
        self.start_time = None
        self.last_stats_print = 0
        
        # Dashboard tracking
        self.recent_opportunities = []  # Last 50 opportunities for dashboard
        
        # Stranded position unwind metrics
        self.stranded_positions_count = 0  # Current stranded positions
        self.stranded_positions_unwound_count = 0  # Lifetime unwound count
        self.unwind_pnl_total = 0.0  # Track losses from unwinding
        self.unwind_config = {
            'monitor_interval_s': 5,  # Check every 5 seconds
            'max_unhedged_time_s': 30,  # Max time before unwind
            'unwind_timeout_s': 10,  # Timeout for unwind order
            'slippage_buffer_bps': 50,  # Price buffer for aggressive fill (0.5%)
            'retry_slippage_bps': 100,  # More aggressive retry (1%)
        }
        
        # Event-driven detection metrics
        self.detections_via_callback = 0  # Count of opportunities from websocket callbacks
        self.detections_via_poll = 0  # Count of opportunities from polling loop
        self.callback_latency_samples = []  # Last 100 latency samples in ms
        
        # Debounce tracking for event-driven callbacks
        self.last_check_time = {}  # {event_id: timestamp_ms}
        self.debounce_ms = 50  # Minimum ms between checks for same event
        
        # Mapping from ticker/token to event_id for callback routing
        self._ticker_to_event = {}  # {ticker_or_token: event_id}
        
        print("\n✓ Bot initialized successfully")
        print("="*60 + "\n")
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from file"""
        default_config = {
            'mode': 'maker_hedge',  # 'maker_hedge' or 'taker'
            'scan_interval_s': 1.0,  # How often to scan for opportunities
            'stats_interval_s': 60,  # How often to print stats
            'risk_limits': {
                'max_trade_size_usd': 100,
                'max_total_exposure_usd': 500,
                'min_edge_bps': 100,
                'max_consecutive_losses': 5
            },
            'arb_detector': {
                'min_edge_bps': 100,
                'max_slippage_bps': 200,
                'max_staleness_ms': 2000
            }
        }
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def _init_components(self):
        """Initialize all bot components"""
        print("Initializing components...")
        
        # 1. Orderbook Manager
        self.orderbook_manager = OrderbookManager()
        
        # 2. WebSocket Clients
        kalshi_api_key = os.getenv('KALSHI_API_KEY')
        
        # Load Kalshi private key path from settings
        settings_path = "config/settings.json"
        kalshi_private_key = "../kalshi_private_key.pem"  # Default
        if os.path.exists(settings_path):
            with open(settings_path) as f:
                settings = json.load(f)
                kalshi_private_key = settings.get('kalshi', {}).get('private_key_path', kalshi_private_key)
        
        # Use real WebSocket for Kalshi (with RSA authentication)
        self.kalshi_ws = KalshiWebSocketClient(
            api_key=kalshi_api_key,
            private_key_path=kalshi_private_key,
            on_orderbook_update=self._on_kalshi_orderbook_update
        )
        
        self.polymarket_ws = PolymarketWebSocketClient(
            on_orderbook_update=self._on_polymarket_orderbook_update
        )
        
        # Wire up async callbacks for event-driven arb detection
        self.kalshi_ws.on_update_async = self._on_orderbook_update_async
        self.polymarket_ws.on_update_async = self._on_orderbook_update_async
        
        # 3. Analysis Components
        self.depth_calculator = DepthCalculator()
        self.race_model = RaceModel()
        
        # 4. Arbitrage Detector
        self.arb_detector = ArbDetector(
            orderbook_manager=self.orderbook_manager,
            depth_calculator=self.depth_calculator,
            race_model=self.race_model,
            config=self.config.get('arb_detector', {})
        )
        
        # 5. Risk & Position Management
        risk_limits = RiskLimits(**self.config.get('risk_limits', {}))
        self.risk_manager = RiskManager(limits=risk_limits)
        self.inventory_tracker = InventoryTracker()
        
        # 6. Executors
        self.kalshi_executor = KalshiExecutor()
        self.polymarket_executor = PolymarketExecutor()
        
        # Dutch Book executor (buys complementary outcomes on both venues)
        self.dutch_book_executor = DutchBookExecutor(
            kalshi_executor=self.kalshi_executor,
            polymarket_executor=self.polymarket_executor,
            inventory_tracker=self.inventory_tracker,
            orderbook_manager=self.orderbook_manager,
            config={
                'max_price_drift_bps': 100,  # 1% max price movement before abort
                'max_profitable_combined_cost': 0.94,  # Must be under this for profit
            }
        )
        
        # 7. Fill Logger
        self.fill_logger = FillLogger()
        
        print("✓ All components initialized\n")
    
    def _on_kalshi_orderbook_update(self, ticker: str, side: str, orderbook: Dict):
        """Callback for Kalshi orderbook updates"""
        # For Kalshi, store by ticker since there are 2 markets per event
        # Key format: "kalshi:{ticker}" to avoid conflicts with event_ids
        market_key = f"kalshi:{ticker}"
        
        if side == 'both':
            self.orderbook_manager.update_orderbook_both_sides(
                market_key, 'kalshi',
                bids=orderbook.get('bids', []),
                asks=orderbook.get('asks', [])
            )
        else:
            levels = orderbook.get('bids' if side == 'bids' else 'asks', [])
            self.orderbook_manager.update_orderbook(
                market_key, 'kalshi', side, levels
            )
    
    def _on_polymarket_orderbook_update(self, token_id: str, side: str, orderbook: Dict):
        """Callback for Polymarket orderbook updates"""
        # Get event_id and team_code from token_info
        token_id_str = str(token_id)
        info = self.polymarket_ws.token_info.get(token_id_str, {})
        event_id = info.get('event_id')
        team_code = info.get('team_code')  # Canonical team code (LAR, CAR, etc.)
        
        if not event_id or not team_code:
            # Unknown token - skip
            return
        
        # Create market key: event_id:polymarket:team_code
        # e.g. "kxnflgame_26jan10lacar:polymarket:LAR"
        market_key = f"{event_id}:polymarket:{team_code}"
        
        # Update orderbook
        if side == 'both':
            self.orderbook_manager.update_orderbook_both_sides(
                market_key, 'polymarket',
                bids=orderbook.get('bids', []),
                asks=orderbook.get('asks', [])
            )
        else:
            levels = orderbook.get('bids' if side == 'bids' else 'asks', [])
            self.orderbook_manager.update_orderbook(
                market_key, 'polymarket', side, levels
            )
    
    async def _on_orderbook_update_async(self, exchange: str, ticker_or_token: str, book: dict):
        """
        Event-driven callback: Called by websocket clients whenever orderbook updates.
        
        This enables near-instant arb detection without waiting for the poll interval.
        
        Args:
            exchange: 'kalshi' or 'polymarket'
            ticker_or_token: Kalshi ticker or Polymarket token_id
            book: Current orderbook state
        """
        if not self.running:
            return
        
        callback_start = time.time()
        
        # Get event_id for this ticker/token
        event_id = self._get_event_id_for_ticker(ticker_or_token, exchange)
        if not event_id:
            return
        
        # Debounce: Skip if we checked this event very recently
        current_time_ms = time.time() * 1000
        last_check = self.last_check_time.get(event_id, 0)
        if current_time_ms - last_check < self.debounce_ms:
            return
        
        self.last_check_time[event_id] = current_time_ms
        
        # Check if we have data for both sides of a potential Dutch Book
        if not self._has_both_sides(event_id):
            return
        
        # Run arb detection for this specific event only
        try:
            opportunity = self.arb_detector.check_event(event_id)
            
            if opportunity:
                # Track latency
                latency_ms = (time.time() - callback_start) * 1000
                self.callback_latency_samples.append(latency_ms)
                if len(self.callback_latency_samples) > 100:
                    self.callback_latency_samples.pop(0)
                
                # Process the opportunity
                await self._process_opportunity_from_callback(opportunity)
        except Exception as e:
            # Don't let callback errors crash the websocket
            print(f"  ⚠️  Callback detection error for {event_id}: {e}")
    
    def _get_event_id_for_ticker(self, ticker_or_token: str, exchange: str) -> Optional[str]:
        """Look up event_id from ticker/token."""
        # Check cache first
        cache_key = f"{exchange}:{ticker_or_token}"
        if cache_key in self._ticker_to_event:
            return self._ticker_to_event[cache_key]
        
        # Search through registered markets
        for event_id in self.orderbook_manager.get_all_markets():
            metadata = self.orderbook_manager.get_market_metadata(event_id)
            if not metadata:
                continue
            
            if exchange == 'kalshi':
                kalshi_tickers = metadata.get('kalshi_tickers', [])
                if ticker_or_token in kalshi_tickers:
                    self._ticker_to_event[cache_key] = event_id
                    return event_id
            else:  # polymarket
                poly_token_ids = metadata.get('poly_token_ids', {})
                if ticker_or_token in poly_token_ids.values():
                    self._ticker_to_event[cache_key] = event_id
                    return event_id
        
        return None
    
    def _has_both_sides(self, event_id: str) -> bool:
        """Check if we have orderbook data for both sides of a Dutch Book."""
        metadata = self.orderbook_manager.get_market_metadata(event_id)
        if not metadata:
            return False
        
        # Need at least one Kalshi ticker with asks
        kalshi_tickers = metadata.get('kalshi_tickers', [])
        kalshi_has_data = False
        for ticker in kalshi_tickers:
            key = f"kalshi:{ticker}"
            book = self.orderbook_manager.get_orderbook(key, 'kalshi')
            if book.get('asks'):
                kalshi_has_data = True
                break
        
        if not kalshi_has_data:
            return False
        
        # Need at least one Poly token with asks
        poly_token_ids = metadata.get('poly_token_ids', {})
        for team_code in poly_token_ids.keys():
            key = f"{event_id}:polymarket:{team_code}"
            book = self.orderbook_manager.get_orderbook(key, 'polymarket')
            if book.get('asks'):
                return True
        
        return False
    
    async def _process_opportunity_from_callback(self, opportunity):
        """Process an opportunity detected via event-driven callback."""
        self.detections_via_callback += 1
        self.opportunities_detected += 1
        
        print(f"\n⚡ [CALLBACK] Dutch Book detected: {opportunity.event_id}")
        print(f"   {opportunity.kalshi_team}@${opportunity.kalshi_vwap:.3f} + {opportunity.poly_team}@${opportunity.poly_vwap:.3f} = ${opportunity.combined_cost:.3f}")
        print(f"   Edge: {opportunity.edge_bps}bps | Confidence: {opportunity.confidence}")
        
        # Track opportunity for dashboard
        opp_record = {
            'event_id': opportunity.event_id,
            'edge_bps': opportunity.edge_bps,
            'confidence': opportunity.confidence,
            'kalshi_team': opportunity.kalshi_team,
            'poly_team': opportunity.poly_team,
            'combined_cost': opportunity.combined_cost,
            'timestamp': datetime.now().isoformat(),
            'action': 'detected_callback'
        }
        
        # Check with risk manager
        current_exposure = self.inventory_tracker.get_total_exposure()
        
        opp_dict = {
            'event_id': opportunity.event_id,
            'edge_bps': opportunity.edge_bps,
            'total_slippage_bps': opportunity.total_slippage_bps,
            'confidence': opportunity.confidence,
            'combined_p_fill': opportunity.combined_p_fill,
            'total_cost': opportunity.total_cost
        }
        
        approved, reason, size = self.risk_manager.check_trade_approval(
            opp_dict,
            current_exposure,
            self.inventory_tracker
        )
        
        if approved:
            print(f"   ✓ Approved - Size: ${size:.2f}")
            opp_record['action'] = 'approved'
            opp_record['size'] = size
            
            # Execute Dutch Book trade
            await self._execute_dutch_book(opportunity, size)
            opp_record['action'] = 'executed'
        else:
            print(f"   ✗ Rejected: {reason}")
            opp_record['action'] = 'rejected'
            opp_record['reason'] = reason
        
        # Add to recent opportunities for dashboard
        self.recent_opportunities.append(opp_record)
        if len(self.recent_opportunities) > 50:
            self.recent_opportunities.pop(0)
    
    def _export_orderbooks_with_labels(self, output_path: str):
        """Export orderbooks with proper team labels for dashboard"""
        export_data = {}
        
        # Iterate through all registered markets
        for event_id, metadata in self.orderbook_manager.market_metadata.items():
            teams = metadata.get('teams', {})
            team_a = teams.get('team_a', 'Team A')
            team_b = teams.get('team_b', 'Team B')
            
            # Export Kalshi markets (2 per event)
            kalshi_tickers = metadata.get('kalshi_tickers', [])
            kalshi_data = metadata.get('kalshi', {})
            
            if len(kalshi_tickers) >= 1:
                # Main market (team_a)
                ticker = kalshi_tickers[0]
                market_key = f"kalshi:{ticker}"
                team_ref = kalshi_data.get('market_a_refers_to', team_a)
                
                orderbook = self.orderbook_manager.get_orderbook(market_key, 'kalshi')
                if orderbook.get('bids') or orderbook.get('asks'):
                    bids = orderbook.get('bids', [])
                    asks = orderbook.get('asks', [])
                    
                    export_key = f"{event_id}:kalshi:{team_ref}"
                    export_data[export_key] = {
                        'event_id': event_id,
                        'platform': 'kalshi',
                        'team': team_ref,
                        'market_type': 'Yes to win',
                        'best_bid': {'price': bids[0][0], 'size': bids[0][1]} if bids else None,
                        'best_ask': {'price': asks[0][0], 'size': asks[0][1]} if asks else None,
                        'bid_depth': len(bids),
                        'ask_depth': len(asks),
                        'staleness_ms': int(self.orderbook_manager.get_staleness_ms(market_key, 'kalshi')),
                        'last_update': datetime.now().isoformat()
                    }
            
            if len(kalshi_tickers) >= 2:
                # Opponent market (team_b)
                ticker = kalshi_tickers[1]
                market_key = f"kalshi:{ticker}"
                team_ref = kalshi_data.get('market_b_refers_to', team_b)
                
                orderbook = self.orderbook_manager.get_orderbook(market_key, 'kalshi')
                if orderbook.get('bids') or orderbook.get('asks'):
                    bids = orderbook.get('bids', [])
                    asks = orderbook.get('asks', [])
                    
                    export_key = f"{event_id}:kalshi:{team_ref}"
                    export_data[export_key] = {
                        'event_id': event_id,
                        'platform': 'kalshi',
                        'team': team_ref,
                        'market_type': 'Yes to win',
                        'best_bid': {'price': bids[0][0], 'size': bids[0][1]} if bids else None,
                        'best_ask': {'price': asks[0][0], 'size': asks[0][1]} if asks else None,
                        'bid_depth': len(bids),
                        'ask_depth': len(asks),
                        'staleness_ms': int(self.orderbook_manager.get_staleness_ms(market_key, 'kalshi')),
                        'last_update': datetime.now().isoformat()
                    }
            
            # Export Polymarket tokens (2 per event)
            # Keys are stored as: {event_id}:polymarket:{team_code}
            poly_tokens = metadata.get('poly_token_ids', {})
            for team_code, token_id in poly_tokens.items():
                # FIXED: Use the same key format as storage in _on_polymarket_orderbook_update
                market_key = f"{event_id}:polymarket:{team_code}"
                
                orderbook = self.orderbook_manager.get_orderbook(market_key, 'polymarket')
                if orderbook.get('bids') or orderbook.get('asks'):
                    bids = orderbook.get('bids', [])
                    asks = orderbook.get('asks', [])
                    
                    export_key = f"{event_id}:polymarket:{team_code}"
                    export_data[export_key] = {
                        'event_id': event_id,
                        'platform': 'polymarket',
                        'team': team_code,
                        'market_type': 'Direct odds',
                        'best_bid': {'price': bids[0][0], 'size': bids[0][1]} if bids else None,
                        'best_ask': {'price': asks[0][0], 'size': asks[0][1]} if asks else None,
                        'bid_depth': len(bids),
                        'ask_depth': len(asks),
                        'staleness_ms': int(self.orderbook_manager.get_staleness_ms(market_key, 'polymarket')),
                        'last_update': datetime.now().isoformat()
                    }
        
        # Write to file
        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)
    
    async def _queue_polymarket_subscriptions(self):
        """Queue all Polymarket subscriptions BEFORE starting WebSocket"""
        print("Queuing Polymarket subscriptions...")
        
        markets = self._load_markets_config()
        poly_count = 0
        
        for market in markets:
            event_id = market['event_id']
            
            # Subscribe Polymarket (token IDs keyed by TEAM CODE now)
            if 'poly_token_ids' in market and market['poly_token_ids']:
                # poly_token_ids format: {team_code: token_id}
                # e.g. {"LAR": "78771...", "CAR": "91562..."}
                for team_code, token_id in market['poly_token_ids'].items():
                    # Ensure token_id is string
                    token_id_str = str(token_id)
                    # Just queue the token, don't send subscription yet
                    self.polymarket_ws.subscribed_tokens.add(token_id_str)
                    
                    # Store metadata: token_id -> (event_id, team_code, sport)
                    self.polymarket_ws.token_info[token_id_str] = {
                        'event_id': event_id,
                        'team_code': team_code,  # Canonical code (LAR, CAR, etc.)
                        'sport': market.get('sport', ''),
                        'condition_id': market.get('poly_condition_id', '')
                    }
                    poly_count += 1
            elif 'polymarket' in market and isinstance(market['polymarket'], dict):
                # Legacy nested format (deprecated)
                poly_data = market['polymarket']
                if poly_data.get('enabled'):
                    # Check if tokens are nested in polymarket object
                    if 'token_ids' in poly_data and poly_data['token_ids']:
                        for team_code, token_id in poly_data['token_ids'].items():
                            token_id_str = str(token_id)
                            self.polymarket_ws.subscribed_tokens.add(token_id_str)
                            self.polymarket_ws.token_info[token_id_str] = {
                                'event_id': event_id,
                                'team_code': team_code,
                                'sport': market.get('sport', ''),
                                'condition_id': poly_data.get('condition_id', '')
                            }
                            poly_count += 1
                    else:
                        print(f"  ⚠️  Polymarket token IDs not resolved for {event_id}")
        
        print(f"✓ Queued {poly_count} Polymarket tokens\n")
    
    async def _subscribe_kalshi_markets(self):
        """Subscribe to Kalshi markets after WebSocket is connected"""
        print("Subscribing to Kalshi markets...")
        
        markets = self._load_markets_config()
        kalshi_tickers = []
        
        for market in markets:
            event_id = market['event_id']
            
            # Prepare metadata for orderbook manager with kalshi tickers
            metadata = market.copy()
            kalshi_tickers_for_event = []
            
            # Collect Kalshi tickers (handle both old and new format)
            if 'kalshi_ticker' in market:
                kalshi_tickers.append(market['kalshi_ticker'])
                kalshi_tickers_for_event.append(market['kalshi_ticker'])
            elif 'kalshi' in market and isinstance(market['kalshi'], dict):
                # New nested format
                kalshi_data = market['kalshi']
                if kalshi_data.get('enabled') and 'markets' in kalshi_data:
                    # Collect both team markets if available
                    kalshi_markets = kalshi_data['markets']
                    if 'main' in kalshi_markets:
                        kalshi_tickers.append(kalshi_markets['main'])
                        kalshi_tickers_for_event.append(kalshi_markets['main'])
                    if 'opponent' in kalshi_markets:
                        kalshi_tickers.append(kalshi_markets['opponent'])
                        kalshi_tickers_for_event.append(kalshi_markets['opponent'])
            
            # Add kalshi_tickers to metadata for lookup in callbacks
            metadata['kalshi_tickers'] = kalshi_tickers_for_event
            
            # Register with orderbook manager
            self.orderbook_manager.register_market(event_id, metadata)
        
        # Batch subscribe to all Kalshi markets at once
        if kalshi_tickers:
            await self.kalshi_ws.subscribe_batch(kalshi_tickers)
        
        print(f"✓ Subscribed to {len(kalshi_tickers)} Kalshi markets\n")
    
    async def _subscribe_to_markets(self):
        """Subscribe WebSocket clients to all tracked markets"""
        print("Subscribing to markets...")
        
        markets = self._load_markets_config()
        kalshi_tickers = []
        subscription_count = 0
        
        for market in markets:
            event_id = market['event_id']
            
            # Prepare metadata for orderbook manager with kalshi tickers
            metadata = market.copy()
            kalshi_tickers_for_event = []
            
            # Collect Kalshi tickers (handle both old and new format)
            if 'kalshi_ticker' in market:
                kalshi_tickers.append(market['kalshi_ticker'])
                kalshi_tickers_for_event.append(market['kalshi_ticker'])
                subscription_count += 1
            elif 'kalshi' in market and isinstance(market['kalshi'], dict):
                # New nested format
                kalshi_data = market['kalshi']
                if kalshi_data.get('enabled') and 'markets' in kalshi_data:
                    # Collect both team markets if available
                    kalshi_markets = kalshi_data['markets']
                    if 'main' in kalshi_markets:
                        kalshi_tickers.append(kalshi_markets['main'])
                        kalshi_tickers_for_event.append(kalshi_markets['main'])
                        subscription_count += 1
                    if 'opponent' in kalshi_markets:
                        kalshi_tickers.append(kalshi_markets['opponent'])
                        kalshi_tickers_for_event.append(kalshi_markets['opponent'])
                        subscription_count += 1
            
            # Add kalshi_tickers to metadata for lookup in callbacks
            metadata['kalshi_tickers'] = kalshi_tickers_for_event
            
            # Register with orderbook manager
            self.orderbook_manager.register_market(event_id, metadata)
            
            # Subscribe Polymarket (handle both old and new format)
            if 'poly_token_ids' in market and market['poly_token_ids']:
                # Flat format with token IDs already resolved
                for outcome, token_id in market['poly_token_ids'].items():
                    market_info = {
                        'outcome': outcome,
                        'condition_id': market.get('poly_condition_id', '')
                    }
                    await self.polymarket_ws.subscribe_orderbook(token_id, market_info)
                    subscription_count += 1
            elif 'polymarket' in market and isinstance(market['polymarket'], dict):
                # New nested format - check if token IDs need resolution
                poly_data = market['polymarket']
                if poly_data.get('enabled'):
                    # Check if tokens are nested in polymarket object
                    if 'token_ids' in poly_data and poly_data['token_ids']:
                        for outcome, token_id in poly_data['token_ids'].items():
                            market_info = {
                                'outcome': outcome,
                                'condition_id': poly_data.get('condition_id', '')
                            }
                            await self.polymarket_ws.subscribe_orderbook(token_id, market_info)
                            subscription_count += 1
                    else:
                        print(f"  ⚠️  Polymarket token IDs not resolved for {event_id}")
                        print(f"      Run: ../venv/bin/python3 resolve_polymarket_tokens.py")
        
        # Batch subscribe to all Kalshi markets at once
        if kalshi_tickers:
            await self.kalshi_ws.subscribe_batch(kalshi_tickers)
        
        print(f"✓ Subscribed to {subscription_count} market feeds ({len(markets)} events)\n")
    
    def _load_markets_config(self) -> list:
        """Load markets from config file"""
        config_path = "config/markets.json"
        
        if not os.path.exists(config_path):
            print(f"⚠️  Markets config not found: {config_path}")
            return []
        
        with open(config_path, 'r') as f:
            data = json.load(f)
            return data.get('markets', [])
    
    async def _arbitrage_scan_loop(self):
        """
        Fallback polling loop: scan for arbitrage opportunities.
        
        NOTE: Primary detection is now EVENT-DRIVEN via websocket callbacks.
        This loop acts as a safety net to catch any opportunities missed by callbacks.
        Runs less frequently (every 5s) since callbacks handle real-time detection.
        """
        # Use longer interval since callbacks handle real-time detection
        POLL_INTERVAL_S = 5.0  # Fallback interval (was 1s, now 5s)
        
        print(f"Starting arbitrage scan loop (fallback mode, {POLL_INTERVAL_S}s interval)...\n")
        
        while self.running:
            try:
                # Scan for opportunities
                opportunities = self.arb_detector.scan_for_opportunities()
                
                if opportunities:
                    # Track poll-based detections
                    self.detections_via_poll += len(opportunities)
                    self.opportunities_detected += len(opportunities)
                    
                    # Process best opportunity (Dutch Book)
                    best_opp = opportunities[0]
                    
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] [POLL] Dutch Book Opportunity detected!")
                    print(f"  Event: {best_opp.event_id}")
                    print(f"  Strategy: Buy {best_opp.kalshi_team} on Kalshi + Buy {best_opp.poly_team} on Polymarket")
                    print(f"  Combined cost: ${best_opp.combined_cost:.3f} (guaranteed payout: $1.00)")
                    print(f"  Edge: {best_opp.edge_bps}bps (${best_opp.net_edge:.2f})")
                    print(f"  Confidence: {best_opp.confidence}")
                    
                    # Track opportunity for dashboard
                    opp_record = {
                        'event_id': best_opp.event_id,
                        'edge_bps': best_opp.edge_bps,
                        'confidence': best_opp.confidence,
                        'kalshi_team': best_opp.kalshi_team,
                        'poly_team': best_opp.poly_team,
                        'combined_cost': best_opp.combined_cost,
                        'timestamp': datetime.now().isoformat(),
                        'action': 'detected'
                    }
                    
                    # Check with risk manager
                    current_exposure = self.inventory_tracker.get_total_exposure()
                    
                    opp_dict = {
                        'event_id': best_opp.event_id,
                        'edge_bps': best_opp.edge_bps,
                        'total_slippage_bps': best_opp.total_slippage_bps,
                        'confidence': best_opp.confidence,
                        'combined_p_fill': best_opp.combined_p_fill,
                        'total_cost': best_opp.total_cost  # Dutch Book uses total_cost
                    }
                    
                    approved, reason, size = self.risk_manager.check_trade_approval(
                        opp_dict,
                        current_exposure,
                        self.inventory_tracker
                    )
                    
                    if approved:
                        print(f"  ✓ Approved - Size: ${size:.2f}")
                        opp_record['action'] = 'approved'
                        opp_record['size'] = size
                        
                        # Execute Dutch Book trade
                        await self._execute_dutch_book(best_opp, size)
                        opp_record['action'] = 'executed'
                    else:
                        print(f"  ✗ Rejected - {reason}")
                        opp_record['action'] = 'rejected'
                        opp_record['reason'] = reason
                    
                    # Add to recent opportunities
                    self.recent_opportunities.append(opp_record)
                
                # Wait before next scan (fallback interval - callbacks handle real-time detection)
                await asyncio.sleep(POLL_INTERVAL_S)
                
                # Print stats and export dashboard data periodically
                if time.time() - self.last_stats_print > self.config['stats_interval_s']:
                    self._print_stats()
                    self._export_dashboard_data()
                    self.last_stats_print = time.time()
                
                # Also export dashboard data more frequently (every scan)
                self._export_dashboard_data()
                
            except Exception as e:
                print(f"✗ Error in scan loop: {e}")
                await asyncio.sleep(1)
    
    async def _periodic_rest_refresh_task(self):
        """
        Background task to periodically refresh orderbooks via REST.
        
        This prevents valid-but-inactive markets (like pre-game NFL) from being 
        marked stale just because no trades are happening. It updates the 
        last_update timestamps even when prices are unchanged.
        
        Runs every 30 seconds.
        """
        REFRESH_INTERVAL_SECONDS = 30
        
        print(f"🔄 Starting periodic REST refresh (every {REFRESH_INTERVAL_SECONDS}s)...\n")
        
        await asyncio.sleep(10)  # Initial delay to let WebSocket connections establish
        
        while self.running:
            try:
                # Refresh both platforms in parallel
                refresh_start = time.time()
                
                kalshi_count, poly_count = await asyncio.gather(
                    self.kalshi_ws.refresh_orderbooks_via_rest(quiet=True),
                    self.polymarket_ws.refresh_orderbooks_via_rest(quiet=True),
                    return_exceptions=True
                )
                
                # Handle any exceptions returned
                if isinstance(kalshi_count, Exception):
                    kalshi_count = 0
                if isinstance(poly_count, Exception):
                    poly_count = 0
                
                refresh_time = time.time() - refresh_start
                
                # Log only if significant (to avoid spam)
                total_refreshed = (kalshi_count or 0) + (poly_count or 0)
                if total_refreshed > 0 and refresh_time > 1.0:
                    print(f"  [REST Refresh] {total_refreshed} orderbooks in {refresh_time:.1f}s")
                
            except Exception as e:
                print(f"✗ Error in REST refresh: {e}")
            
            await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
    
    async def _stranded_position_monitor_task(self):
        """
        Background task that monitors for stranded positions and triggers unwind.
        
        Runs every 5 seconds, checks for positions that:
        - Have been unhedged for > max_unhedged_time_s (30s default)
        - Places aggressive market SELL orders to exit
        """
        monitor_interval = self.unwind_config['monitor_interval_s']
        max_age = self.unwind_config['max_unhedged_time_s']
        
        print(f"✓ Stranded position monitor started (interval: {monitor_interval}s, max age: {max_age}s)")
        
        while self.running:
            try:
                # Get unhedged positions that have exceeded max age
                unhedged = self.inventory_tracker.get_unhedged_positions(max_age_s=max_age)
                
                # Update current stranded count
                self.stranded_positions_count = len(unhedged)
                
                if unhedged:
                    print(f"\n⚠️  [UNWIND MONITOR] {len(unhedged)} stranded position(s) detected!")
                    
                    for position_info in unhedged:
                        event_id = position_info['event_id']
                        net_position = position_info['net_position']
                        platforms = position_info['platforms']
                        age_s = position_info['age_s']
                        is_urgent = position_info.get('urgent', False)
                        
                        print(f"  Stranded: {event_id}")
                        print(f"    Net position: {net_position:.2f} contracts")
                        print(f"    Platforms: {platforms}")
                        print(f"    Age: {age_s:.1f}s {'(URGENT)' if is_urgent else ''}")
                        
                        # Attempt unwind
                        await self._unwind_stranded_position(position_info)
                
            except Exception as e:
                print(f"✗ Error in stranded position monitor: {e}")
                import traceback
                traceback.print_exc()
            
            await asyncio.sleep(monitor_interval)
    
    async def _unwind_stranded_position(self, position_info: dict):
        """
        Unwind a stranded position by placing aggressive SELL orders.
        
        Args:
            position_info: Dict from get_unhedged_positions() with:
                - event_id: Event identifier
                - net_position: Net position size (positive = need to sell)
                - platforms: Dict of platform -> position size
                - age_s: How long position has been stranded
        """
        event_id = position_info['event_id']
        net_position = position_info['net_position']
        platforms = position_info['platforms']
        age_s = position_info['age_s']
        
        is_paper = self.config.get('paper_trading', False)
        
        print(f"\n{'='*60}")
        print(f"UNWIND STRANDED POSITION {'(PAPER)' if is_paper else ''}")
        print(f"{'='*60}")
        print(f"Event: {event_id}")
        print(f"Net position: {net_position:.2f}")
        print(f"Time stranded: {age_s:.1f}s")
        
        # Determine which platform has the stranded position
        for platform, pos_size in platforms.items():
            if abs(pos_size) < 1:
                continue  # Skip negligible positions
            
            # Get position details
            positions = self.inventory_tracker.get_all_positions()
            stranded_pos = None
            for pos in positions:
                if pos.event_id == event_id and pos.platform == platform:
                    stranded_pos = pos
                    break
            
            if not stranded_pos:
                print(f"  ⚠️  Could not find position details for {platform}")
                continue
            
            outcome = stranded_pos.outcome
            original_price = stranded_pos.avg_price
            size_to_sell = abs(stranded_pos.size)
            
            print(f"\n  Unwinding: {size_to_sell:.2f} {outcome} on {platform}")
            print(f"  Original price: ${original_price:.4f}")
            
            # Get current best bid for aggressive pricing
            market_key = self._get_market_key_for_unwind(event_id, platform, outcome)
            if not market_key:
                print(f"  ✗ Could not find market key for {platform}/{outcome}")
                continue
            
            orderbook = self.orderbook_manager.get_orderbook(market_key, platform)
            bids = orderbook.get('bids', [])
            
            if not bids:
                print(f"  ✗ No bids available - cannot unwind!")
                self._log_unwind_attempt(event_id, platform, outcome, original_price, 0, size_to_sell, 0, False, "No bids")
                continue
            
            best_bid = bids[0][0]
            slippage_pct = self.unwind_config['slippage_buffer_bps'] / 10000
            unwind_price = best_bid * (1 - slippage_pct)  # Below best bid for aggressive fill
            
            print(f"  Best bid: ${best_bid:.4f}")
            print(f"  Unwind price: ${unwind_price:.4f} (with {slippage_pct:.2%} buffer)")
            
            # Calculate P&L from unwind
            unwind_pnl = (unwind_price - original_price) * size_to_sell
            print(f"  Expected P&L: ${unwind_pnl:.2f}")
            
            if is_paper:
                # PAPER MODE: Simulate unwind
                print(f"  📝 PAPER UNWIND - Simulating sell")
                
                # Simulate fill at unwind price
                self._record_unwind_fill(event_id, platform, outcome, size_to_sell, unwind_price)
                self.unwind_pnl_total += unwind_pnl
                self.stranded_positions_unwound_count += 1
                
                self._log_unwind_attempt(event_id, platform, outcome, original_price, unwind_price, size_to_sell, unwind_pnl, True, "Paper unwind")
                
                print(f"  ✓ Paper unwind complete - P&L: ${unwind_pnl:.2f}")
            else:
                # LIVE MODE: Real unwind
                success = await self._execute_unwind_order(
                    event_id, platform, outcome, size_to_sell, unwind_price, original_price
                )
                
                if not success:
                    # Retry with more aggressive pricing
                    print(f"  ⚠️  First attempt failed - retrying with more aggressive price")
                    
                    retry_slippage_pct = self.unwind_config['retry_slippage_bps'] / 10000
                    retry_price = best_bid * (1 - retry_slippage_pct)
                    
                    success = await self._execute_unwind_order(
                        event_id, platform, outcome, size_to_sell, retry_price, original_price
                    )
                    
                    if not success:
                        # CRITICAL: Trigger kill switch
                        print(f"\n🚨 CRITICAL: Unwind failed twice - triggering KILL SWITCH!")
                        self.risk_manager._trigger_kill_switch("Unwind failed twice")
                        self._log_unwind_attempt(event_id, platform, outcome, original_price, retry_price, size_to_sell, 0, False, "Kill switch triggered")
                        return
        
        print(f"{'='*60}\n")
    
    async def _execute_unwind_order(
        self,
        event_id: str,
        platform: str,
        outcome: str,
        size: float,
        price: float,
        original_price: float
    ) -> bool:
        """
        Execute a real unwind order on the exchange.
        
        Returns:
            True if successful, False if failed
        """
        unwind_timeout = self.unwind_config['unwind_timeout_s']
        
        try:
            if platform == 'kalshi':
                # Kalshi SELL order
                # Need to find ticker from market metadata
                markets = self.orderbook_manager.get_all_markets()
                ticker = None
                for mkt_event_id in markets:
                    if mkt_event_id == event_id:
                        metadata = self.orderbook_manager.get_market_metadata(event_id)
                        tickers = metadata.get('kalshi_tickers', [])
                        for t in tickers:
                            if outcome.upper() in t.upper():
                                ticker = t
                                break
                        break
                
                if not ticker:
                    print(f"  ✗ Could not find Kalshi ticker for {outcome}")
                    return False
                
                # Execute sell order
                price_cents = int(price * 100)
                result = self.kalshi_executor.execute_order(
                    ticker=ticker,
                    side="no",  # Selling YES = buying NO conceptually, or just SELL
                    quantity=int(size),
                    price_cents=price_cents,
                    order_type="limit",
                    wait_for_fill=True,
                    fill_timeout=unwind_timeout
                )
                
                if result.success and result.filled_quantity > 0:
                    filled_price = result.filled_price
                    unwind_pnl = (filled_price - original_price) * result.filled_quantity
                    
                    self._record_unwind_fill(event_id, platform, outcome, result.filled_quantity, filled_price)
                    self.unwind_pnl_total += unwind_pnl
                    self.stranded_positions_unwound_count += 1
                    
                    self._log_unwind_attempt(event_id, platform, outcome, original_price, filled_price, result.filled_quantity, unwind_pnl, True, "Live unwind")
                    
                    print(f"  ✓ Kalshi unwind filled: {result.filled_quantity} @ ${filled_price:.4f}")
                    return True
                else:
                    print(f"  ✗ Kalshi unwind failed: {result.error}")
                    return False
            
            elif platform == 'polymarket':
                # Polymarket SELL order
                # Need to find token_id from market metadata
                metadata = self.orderbook_manager.get_market_metadata(event_id)
                token_ids = metadata.get('poly_token_ids', {})
                token_id = token_ids.get(outcome)
                
                if not token_id:
                    print(f"  ✗ Could not find Polymarket token_id for {outcome}")
                    return False
                
                # Execute sell order
                result = self.polymarket_executor.execute_order(
                    market_id=metadata.get('poly_condition_id', ''),
                    token_id=str(token_id),
                    side="SELL",
                    size=size,
                    max_price=price,  # Willing to sell at this price or better
                    wait_for_fill=True,
                    fill_timeout=unwind_timeout
                )
                
                if result.success and result.filled_size > 0:
                    filled_price = result.filled_price
                    unwind_pnl = (filled_price - original_price) * result.filled_size
                    
                    self._record_unwind_fill(event_id, platform, outcome, result.filled_size, filled_price)
                    self.unwind_pnl_total += unwind_pnl
                    self.stranded_positions_unwound_count += 1
                    
                    self._log_unwind_attempt(event_id, platform, outcome, original_price, filled_price, result.filled_size, unwind_pnl, True, "Live unwind")
                    
                    print(f"  ✓ Polymarket unwind filled: {result.filled_size:.2f} @ ${filled_price:.4f}")
                    return True
                else:
                    print(f"  ✗ Polymarket unwind failed: {result.error}")
                    return False
            
            return False
        
        except Exception as e:
            print(f"  ✗ Unwind order error: {e}")
            return False
    
    def _get_market_key_for_unwind(self, event_id: str, platform: str, outcome: str) -> str:
        """Get the market key for orderbook lookup during unwind."""
        if platform == 'kalshi':
            # Try to find ticker from metadata
            metadata = self.orderbook_manager.get_market_metadata(event_id)
            if metadata:
                tickers = metadata.get('kalshi_tickers', [])
                for ticker in tickers:
                    if outcome.upper() in ticker.upper():
                        return f"kalshi:{ticker}"
        elif platform == 'polymarket':
            return f"{event_id}:polymarket:{outcome}"
        
        return None
    
    def _record_unwind_fill(self, event_id: str, platform: str, outcome: str, size: float, price: float):
        """Record unwind fill in inventory tracker (as a sell)."""
        self.inventory_tracker.record_fill(
            event_id=event_id,
            platform=platform,
            outcome=outcome,
            size=size,
            price=price,
            is_buy=False  # Selling to unwind
        )
    
    def _log_unwind_attempt(
        self,
        event_id: str,
        exchange: str,
        team: str,
        original_price: float,
        unwind_price: float,
        size: float,
        pnl: float,
        success: bool,
        notes: str = ""
    ):
        """Log unwind attempt to CSV file."""
        try:
            from pathlib import Path
            import csv
            
            log_file = Path("data/unwind_log.csv")
            
            # Create file with headers if it doesn't exist
            if not log_file.exists():
                log_file.parent.mkdir(parents=True, exist_ok=True)
                with open(log_file, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        'timestamp', 'event_id', 'exchange', 'team',
                        'original_price', 'unwind_price', 'size', 'pnl', 'success', 'notes'
                    ])
            
            # Append unwind record
            with open(log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    event_id,
                    exchange,
                    team,
                    f"{original_price:.4f}",
                    f"{unwind_price:.4f}",
                    f"{size:.2f}",
                    f"{pnl:.2f}",
                    str(success),
                    notes
                ])
        except Exception as e:
            print(f"  ⚠️  Failed to log unwind attempt: {e}")
    
    async def _execute_dutch_book(self, opportunity: DutchBookOpportunity, size: float):
        """Execute Dutch Book arbitrage (or simulate in paper mode)"""
        try:
            self.trades_executed += 1
            
            # Check if paper trading mode
            is_paper = self.config.get('paper_trading', False)
            
            if is_paper:
                # PAPER TRADING: Simulate the Dutch Book trade
                # 
                # CRITICAL: Dutch Book requires EQUAL CONTRACT COUNTS on both legs!
                # - Combined price = kalshi_ask + poly_ask
                # - num_contracts = total_budget / combined_price
                # - Both legs get the SAME num_contracts
                
                combined_price = opportunity.kalshi_vwap + opportunity.poly_vwap
                if combined_price <= 0:
                    print(f"  ⚠️ Invalid combined price: ${combined_price:.4f}")
                    return
                
                # Calculate equal contracts for both legs
                num_contracts = size / combined_price  # size is TOTAL budget
                kalshi_cost = num_contracts * opportunity.kalshi_vwap
                poly_cost = num_contracts * opportunity.poly_vwap
                total_cost = kalshi_cost + poly_cost  # Should equal 'size'
                
                print(f"  📝 PAPER TRADE - Dutch Book")
                print(f"     Total budget: ${size:.2f}")
                print(f"     Contracts: {num_contracts:.2f} (equal on both legs)")
                print(f"     Buy {opportunity.kalshi_team} @ ${opportunity.kalshi_vwap:.3f} on Kalshi = ${kalshi_cost:.2f}")
                print(f"     Buy {opportunity.poly_team} @ ${opportunity.poly_vwap:.3f} on Polymarket = ${poly_cost:.2f}")
                
                # Calculate P&L correctly for Dutch Book
                guaranteed_payout = num_contracts * 1.0  # $1 per contract at settlement
                gross_profit = guaranteed_payout - total_cost
                
                # Fee calculation: Different rates per venue, on WINNING LEG PROFIT only
                # - Kalshi: 7% on profit when Kalshi leg wins
                # - Polymarket: 2% on profit when Poly leg wins
                kalshi_fee_rate = 0.07  # 7%
                poly_fee_rate = 0.02    # 2%
                
                # Scenario 1: Kalshi team wins
                kalshi_profit = num_contracts - kalshi_cost  # Payout - cost
                kalshi_scenario_fee = kalshi_profit * kalshi_fee_rate
                kalshi_scenario_net = gross_profit - kalshi_scenario_fee
                
                # Scenario 2: Poly team wins
                poly_profit = num_contracts - poly_cost  # Payout - cost
                poly_scenario_fee = poly_profit * poly_fee_rate
                poly_scenario_net = gross_profit - poly_scenario_fee
                
                # Use worst case (minimum net profit) for conservative P&L estimate
                net_profit = min(kalshi_scenario_net, poly_scenario_net)
                estimated_fee = gross_profit - net_profit
                simulated_pnl = net_profit
                self.total_pnl += simulated_pnl
                
                print(f"  📊 Guaranteed payout: ${guaranteed_payout:.2f}")
                print(f"  📊 Gross profit: ${gross_profit:.2f}")
                print(f"  📊 Estimated fees: ${estimated_fee:.2f}")
                print(f"  📊 Net P&L: ${simulated_pnl:.2f}")
                print(f"  💡 Edge: {int((net_profit / total_cost) * 10000)}bps")
                
                # Log to CSV for analysis
                self._log_paper_trade(opportunity, size, simulated_pnl)
                
                # Record as Dutch Book position with EQUAL contract counts
                self.inventory_tracker.record_dutch_book(
                    event_id=opportunity.event_id,
                    kalshi_team=opportunity.kalshi_team,
                    kalshi_size=num_contracts,  # SAME contracts for both legs
                    kalshi_price=opportunity.kalshi_vwap,
                    kalshi_order_id=None,  # Simulated
                    poly_team=opportunity.poly_team,
                    poly_size=num_contracts,  # SAME contracts for both legs
                    poly_price=opportunity.poly_vwap,
                    poly_order_id=None,  # Simulated
                    fees_paid=estimated_fee
                )
                
                return
            
            # LIVE TRADING: Real Dutch Book execution
            market_info = self.orderbook_manager.get_market_metadata(opportunity.event_id)
            
            # Execute via Dutch Book executor
            result = await self.dutch_book_executor.execute_opportunity(
                opportunity, market_info
            )
            
            # Record outcome
            if result.success:
                self.total_pnl += result.net_profit
                print(f"  ✓ Dutch Book complete - Guaranteed profit: ${result.net_profit:.2f}")
                
                # Record Dutch Book position
                self.inventory_tracker.record_dutch_book(
                    event_id=opportunity.event_id,
                    kalshi_team=result.kalshi_team,
                    kalshi_size=result.kalshi_fill_size,
                    kalshi_price=result.kalshi_fill_price,
                    kalshi_order_id=result.kalshi_order_id,
                    poly_team=result.poly_team,
                    poly_size=result.poly_fill_size,
                    poly_price=result.poly_fill_price,
                    poly_order_id=result.poly_order_id,
                    fees_paid=result.fees
                )
            else:
                print(f"  ✗ Trade failed - {result.reason}")
                if result.one_leg_only:
                    print(f"  ⚠️  Directional position taken - not arbitrage!")
            
            # Update risk manager
            self.risk_manager.record_trade_outcome(
                pnl=result.net_profit if result.success else 0,
                success=result.success
            )
            
        except Exception as e:
            print(f"✗ Execution error: {e}")
    
    def _log_paper_trade(self, opportunity: DutchBookOpportunity, size: float, simulated_pnl: float):
        """Log paper trade to CSV for analysis"""
        try:
            from pathlib import Path
            import csv
            
            log_file = Path("data/paper_trades.csv")
            
            # Create file with headers if it doesn't exist
            if not log_file.exists():
                log_file.parent.mkdir(parents=True, exist_ok=True)
                with open(log_file, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        'timestamp', 'event_id', 'strategy', 'edge_bps', 
                        'size_usd', 'simulated_pnl', 'confidence',
                        'kalshi_team', 'kalshi_price', 'poly_team', 'poly_price',
                        'combined_cost', 'guaranteed_payout'
                    ])
            
            # Append trade
            with open(log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    opportunity.event_id,
                    'dutch_book',  # Always Dutch Book now
                    opportunity.edge_bps,
                    f"{size:.2f}",
                    f"{simulated_pnl:.2f}",
                    opportunity.confidence,
                    opportunity.kalshi_team,
                    f"{opportunity.kalshi_vwap:.4f}",
                    opportunity.poly_team,
                    f"{opportunity.poly_vwap:.4f}",
                    f"{opportunity.combined_cost:.4f}",
                    f"{opportunity.guaranteed_payout:.2f}"
                ])
        except Exception as e:
            # Don't crash bot if logging fails
            print(f"  ⚠️  Failed to log paper trade: {e}")
    
    def _print_stats(self):
        """Print bot statistics"""
        runtime = time.time() - self.start_time if self.start_time else 0
        is_paper = self.config.get('paper_trading', False)
        
        print(f"\n{'='*60}")
        print(f"BOT STATISTICS ({runtime/60:.1f} minutes)")
        if is_paper:
            print(f"📝 PAPER TRADING MODE (Simulated)")
        print(f"{'='*60}")
        
        print(f"\nOpportunities:")
        print(f"  Detected: {self.opportunities_detected}")
        print(f"    Via callback (real-time): {self.detections_via_callback}")
        print(f"    Via poll (fallback): {self.detections_via_poll}")
        print(f"  Filtered (stale/no-edge): {self.arb_detector.opportunities_filtered}")
        print(f"  Confidence overrides: {self.arb_detector.confidence_overrides}")
        print(f"  {'Simulated' if is_paper else 'Real'} trades: {self.trades_executed}")
        print(f"  {'Simulated' if is_paper else 'Total'} P&L: ${self.total_pnl:.2f}")
        
        # Callback latency
        if self.callback_latency_samples:
            avg_latency = sum(self.callback_latency_samples) / len(self.callback_latency_samples)
            print(f"  Callback latency (avg): {avg_latency:.1f}ms")
        
        # Diagnostic: Show orderbook status
        print(f"\nOrderbook Status:")
        markets = self.orderbook_manager.get_all_markets()
        print(f"  Registered markets: {len(markets)}")
        
        # Count orderbooks with data
        kalshi_with_data = 0
        poly_with_data = 0
        for event_id in markets:
            metadata = self.orderbook_manager.get_market_metadata(event_id)
            if not metadata:
                continue
            
            # Check Kalshi
            kalshi_tickers = metadata.get('kalshi_tickers', [])
            for ticker in kalshi_tickers:
                key = f"kalshi:{ticker}"
                book = self.orderbook_manager.get_orderbook(key, 'kalshi')
                if book.get('bids') or book.get('asks'):
                    kalshi_with_data += 1
            
            # Check Polymarket
            poly_tokens = metadata.get('poly_token_ids', {})
            for team_code, token_id in poly_tokens.items():
                key = f"{event_id}:polymarket:{team_code}"
                book = self.orderbook_manager.get_orderbook(key, 'polymarket')
                if book.get('bids') or book.get('asks'):
                    poly_with_data += 1
        
        print(f"  Kalshi orderbooks with data: {kalshi_with_data}")
        print(f"  Polymarket orderbooks with data: {poly_with_data}")
        
        # Arb scan diagnostics
        print(f"\nArb Scan Diagnostics (last scan):")
        stats = self.arb_detector.scan_stats
        print(f"  Teams checked: {stats.get('teams_checked', 0)}")
        print(f"  Filtered - stale: {stats.get('filtered_stale', 0)}")
        print(f"  Filtered - no liquidity: {stats.get('filtered_no_liquidity', 0)}")
        print(f"  Filtered - no edge: {stats.get('filtered_no_edge', 0)}")
        print(f"  Filtered - edge too small: {stats.get('filtered_edge_too_small', 0)}")
        
        # Show config
        print(f"\nArb Config:")
        print(f"  Min edge: {self.arb_detector.config['min_edge_bps']} bps ({self.arb_detector.config['min_edge_bps']/100:.2f}%)")
        print(f"  Max staleness: {self.arb_detector.config['max_staleness_ms']} ms")
        
        print(f"\nRisk Manager:")
        risk_stats = self.risk_manager.get_stats()
        print(f"  Approval rate: {risk_stats['approval_rate_pct']:.1f}%")
        print(f"  Daily P&L: ${risk_stats['daily_pnl']:.2f}")
        print(f"  Consecutive losses: {risk_stats['consecutive_losses']}")
        
        print(f"\nInventory:")
        inv_stats = self.inventory_tracker.get_stats()
        print(f"  Positions: {inv_stats['num_positions']}")
        print(f"  Gross exposure: ${inv_stats['total_gross_exposure']:.2f}")
        
        print(f"\nStranded Position Unwind:")
        print(f"  Current stranded: {self.stranded_positions_count}")
        print(f"  Total unwound (lifetime): {self.stranded_positions_unwound_count}")
        print(f"  Unwind P&L: ${self.unwind_pnl_total:.2f}")
        
        print(f"\nWebSockets:")
        kalshi_stats = self.kalshi_ws.get_stats()
        poly_stats = self.polymarket_ws.get_stats()
        print(f"  Kalshi: {kalshi_stats}")
        print(f"  Polymarket: {poly_stats}")
        
        print(f"{'='*60}\n")
    
    def _export_dashboard_data(self):
        """Export current bot state to JSON files for dashboard consumption"""
        try:
            # Create data directory if needed
            from pathlib import Path
            Path("data").mkdir(exist_ok=True)
            
            # 1. Export orderbooks with proper team labels
            self._export_orderbooks_with_labels("data/orderbooks.json")
            
            # 2. Export bot state
            runtime = time.time() - self.start_time if self.start_time else 0
            risk_stats = self.risk_manager.get_stats()
            
            bot_state = {
                'running': self.running,
                'mode': self.config['mode'],
                'uptime_s': runtime,
                'opportunities_detected': self.opportunities_detected,
                'trades_executed': self.trades_executed,
                'total_pnl': self.total_pnl,
                'timestamp': datetime.now().isoformat(),
                'kalshi_ws': self.kalshi_ws.get_stats() if hasattr(self, 'kalshi_ws') else {'connected': False},
                'polymarket_ws': self.polymarket_ws.get_stats() if hasattr(self, 'polymarket_ws') else {'connected': False},
                'risk_manager': {
                    'approval_rate_pct': risk_stats.get('approval_rate_pct', 0),
                    'daily_pnl': risk_stats.get('daily_pnl', 0),
                    'consecutive_losses': risk_stats.get('consecutive_losses', 0)
                }
            }
            
            with open("data/bot_state.json", 'w') as f:
                json.dump(bot_state, f, indent=2)
            
            # 3. Export recent opportunities
            with open("data/recent_opportunities.json", 'w') as f:
                json.dump({'opportunities': self.recent_opportunities[-50:]}, f, indent=2)
            
            # 4. Export positions (including Dutch Book positions)
            inv_stats = self.inventory_tracker.get_stats()
            
            # Standard positions
            positions = []
            for key, pos in self.inventory_tracker.positions.items():
                positions.append({
                    'event_id': pos.event_id,
                    'platform': pos.platform,
                    'outcome': pos.outcome,
                    'size': pos.size,
                    'avg_price': pos.avg_price,
                    'realized_pnl': pos.realized_pnl
                })
            
            # Dutch Book positions
            dutch_book_positions = []
            for db_pos in self.inventory_tracker.get_dutch_book_positions():
                dutch_book_positions.append({
                    'event_id': db_pos.event_id,
                    'kalshi_team': db_pos.kalshi_team,
                    'kalshi_size': db_pos.kalshi_size,
                    'kalshi_price': db_pos.kalshi_price,
                    'poly_team': db_pos.poly_team,
                    'poly_size': db_pos.poly_size,
                    'poly_price': db_pos.poly_price,
                    'combined_cost': db_pos.combined_cost,
                    'locked_profit': db_pos.locked_profit,
                    'is_settled': db_pos.is_settled,
                    'settlement_pnl': db_pos.settlement_pnl
                })
            
            with open("data/positions.json", 'w') as f:
                json.dump({
                    'positions': positions,
                    'dutch_book_positions': dutch_book_positions,
                    'total_exposure': inv_stats['total_gross_exposure'],
                    'dutch_book_summary': self.inventory_tracker.get_dutch_book_summary()
                }, f, indent=2)
            
        except Exception as e:
            # Don't let dashboard export crash the bot
            pass
    
    async def start(self):
        """Start the bot"""
        self.running = True
        self.start_time = time.time()
        
        # Initial dashboard data export
        self._export_dashboard_data()
        
        print(f"\n{'='*60}")
        print(f"STARTING BOT")
        print(f"Mode: {self.config['mode']}")
        
        # Show paper trading status prominently
        if self.config.get('paper_trading', False):
            print(f"{'='*60}")
            print(f"🔔 PAPER TRADING MODE - NO REAL ORDERS 🔔")
            print(f"{'='*60}")
            print(f"✓ Simulated trades will be logged to: data/paper_trades.csv")
        
        print(f"{'='*60}\n")
        
        try:
            # CRITICAL: Queue Polymarket subscriptions BEFORE starting WebSocket
            # This allows the initial batch subscription to include all tokens
            await self._queue_polymarket_subscriptions()
            
            # Seed Polymarket orderbooks via REST for immediate price availability
            if self.polymarket_ws.subscribed_tokens:
                token_list = [str(t) for t in self.polymarket_ws.subscribed_tokens]
                await self.polymarket_ws.seed_orderbooks_via_rest(token_list)
            
            # Start WebSocket clients (Polymarket will now send batch subscription)
            kalshi_task = asyncio.create_task(self.kalshi_ws.start())
            poly_task = asyncio.create_task(self.polymarket_ws.start())
            
            # Wait for connections
            await asyncio.sleep(2)
            
            # Subscribe to Kalshi markets
            await self._subscribe_kalshi_markets()
            
            # Wait for initial orderbook data
            await asyncio.sleep(3)
            
            # Start arbitrage scan loop
            scan_task = asyncio.create_task(self._arbitrage_scan_loop())
            
            # Start periodic REST refresh task (keeps inactive markets fresh)
            refresh_task = asyncio.create_task(self._periodic_rest_refresh_task())
            
            # Start stranded position monitor (auto-unwind for one-leg fills)
            unwind_task = asyncio.create_task(self._stranded_position_monitor_task())
            
            print("✓ Bot is running!\n")
            
            # Keep running
            await asyncio.gather(kalshi_task, poly_task, scan_task, refresh_task, unwind_task)
            
        except KeyboardInterrupt:
            print("\n\n⏸️  Interrupted by user")
            await self.stop()
        except Exception as e:
            print(f"\n✗ Fatal error: {e}")
            await self.stop()
    
    async def stop(self):
        """Stop the bot"""
        print(f"\n{'='*60}")
        print("STOPPING BOT")
        print(f"{'='*60}\n")
        
        self.running = False
        
        # Stop WebSocket clients
        await self.kalshi_ws.stop()
        await self.polymarket_ws.stop()
        
        # Print final stats
        self._print_stats()
        
        print("✓ Bot stopped cleanly\n")


async def main():
    """Main entry point"""
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Kalshi <> Polymarket Arbitrage Bot')
    parser.add_argument('--config', type=str, default='config/bot_config.json',
                       help='Path to configuration file (default: config/bot_config.json)')
    args = parser.parse_args()
    
    # Create bot with specified config
    bot = ArbBot(config_path=args.config)
    
    # Setup signal handlers
    def signal_handler(sig, frame):
        print("\n\nReceived interrupt signal...")
        asyncio.create_task(bot.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start bot
    await bot.start()


if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     KALSHI <> POLYMARKET ARBITRAGE BOT                    ║
║     Production Execution System                           ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete.")

