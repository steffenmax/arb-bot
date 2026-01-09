"""
Database Setup for Prediction Market Data Logger

This module creates and manages the SQLite database for storing:
- Tracked markets (which markets we're monitoring)
- Price snapshots (price data collected over time)
- Arbitrage opportunities (detected opportunities for later analysis)
- Collection logs (health monitoring)

Usage:
    python db_setup.py  # Creates database with test data
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path


class DatabaseManager:
    """Manages all database operations for the data logger"""
    
    def __init__(self, db_path="data/market_data.db"):
        """Initialize database connection
        
        Args:
            db_path: Path to SQLite database file (relative to this file)
        """
        # Make path relative to this file's location
        base_dir = Path(__file__).parent
        self.db_path = base_dir / db_path
        
        # Ensure data directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.conn = None
        self.connect()
    
    def connect(self):
        """Connect to database"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # Access columns by name
        print(f"✓ Connected to database: {self.db_path}")
    
    def create_tables(self):
        """Create all required tables"""
        cursor = self.conn.cursor()
        
        # Table 1: Tracked Markets
        # Stores which markets we're actively monitoring
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tracked_markets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                description TEXT NOT NULL,
                sport TEXT,
                event_date TEXT,
                teams TEXT,  -- JSON: {"team_a": "Lakers", "team_b": "Celtics"}
                kalshi_markets TEXT,  -- JSON: {"team_a_yes": "...", ...}
                polymarket_markets TEXT,  -- JSON: {"team_a": "...", "team_b": "..."}
                enabled INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table 2: Price Snapshots
        # Stores all price data collected over time
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                platform TEXT NOT NULL,  -- 'kalshi' or 'polymarket'
                market_id TEXT NOT NULL,
                market_side TEXT,  -- 'team_a', 'team_b', 'yes', 'no'
                
                -- Price data
                yes_price REAL,
                no_price REAL,
                yes_bid REAL,
                yes_ask REAL,
                no_bid REAL,
                no_ask REAL,
                
                -- Volume and liquidity
                volume REAL,
                liquidity REAL,
                
                -- Metadata
                timestamp TEXT NOT NULL,
                collection_time TEXT DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (event_id) REFERENCES tracked_markets(event_id)
            )
        """)
        
        # Index for fast time-based queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_price_snapshots_time 
            ON price_snapshots(timestamp, event_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_price_snapshots_event 
            ON price_snapshots(event_id, platform)
        """)
        
        # Table 3: Arbitrage Opportunities
        # Stores detected arbitrage opportunities for later analysis
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS arbitrage_opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                
                -- Kalshi side
                kalshi_market_id TEXT NOT NULL,
                kalshi_side TEXT NOT NULL,
                kalshi_price REAL NOT NULL,
                
                -- Polymarket side (opposite)
                polymarket_market_id TEXT NOT NULL,
                polymarket_side TEXT NOT NULL,
                polymarket_price REAL NOT NULL,
                
                -- Arbitrage calculation
                total_cost REAL NOT NULL,  -- kalshi_cost + poly_cost
                profit_before_fees REAL NOT NULL,
                profit_after_fees REAL NOT NULL,
                kalshi_fee_pct REAL DEFAULT 0.07,
                polymarket_fee_pct REAL DEFAULT 0.02,
                
                -- Timing
                detected_at TEXT NOT NULL,
                kalshi_snapshot_id INTEGER,
                polymarket_snapshot_id INTEGER,
                time_diff_seconds REAL,  -- Time between snapshots
                
                FOREIGN KEY (event_id) REFERENCES tracked_markets(event_id),
                FOREIGN KEY (kalshi_snapshot_id) REFERENCES price_snapshots(id),
                FOREIGN KEY (polymarket_snapshot_id) REFERENCES price_snapshots(id)
            )
        """)
        
        # Table 4: Orderbook Snapshots
        # Stores orderbook depth data (bids/asks at each level)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orderbook_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER NOT NULL,  -- Links to price_snapshots.id
                event_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                market_id TEXT NOT NULL,
                side TEXT NOT NULL,  -- 'yes' or 'no'
                order_type TEXT NOT NULL,  -- 'bid' or 'ask'
                level INTEGER NOT NULL,  -- 1 = best, 2 = second best, etc.
                price REAL NOT NULL,
                size REAL NOT NULL,
                order_count INTEGER,
                timestamp TEXT NOT NULL,
                
                FOREIGN KEY (snapshot_id) REFERENCES price_snapshots(id),
                FOREIGN KEY (event_id) REFERENCES tracked_markets(event_id)
            )
        """)
        
        # Index for fast orderbook queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_orderbook_snapshot 
            ON orderbook_snapshots(snapshot_id, side, order_type, level)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_orderbook_time 
            ON orderbook_snapshots(timestamp, event_id)
        """)
        
        # Table 5: Collection Logs
        # Health monitoring - tracks each collection cycle
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS collection_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_number INTEGER,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                duration_seconds REAL,
                
                -- Statistics
                markets_attempted INTEGER DEFAULT 0,
                kalshi_success INTEGER DEFAULT 0,
                kalshi_failed INTEGER DEFAULT 0,
                polymarket_success INTEGER DEFAULT 0,
                polymarket_failed INTEGER DEFAULT 0,
                
                -- Errors
                errors TEXT,  -- JSON array of error messages
                
                status TEXT DEFAULT 'running'  -- 'running', 'completed', 'failed'
            )
        """)
        
        self.conn.commit()
        print("✓ All tables created successfully")
    
    def add_tracked_market(self, event_id, description, sport=None, event_date=None,
                          teams=None, kalshi_markets=None, polymarket_markets=None):
        """Add a market to track
        
        Args:
            event_id: Unique identifier for this event
            description: Human-readable description (e.g., "Lakers vs Celtics")
            sport: Sport type (e.g., "NBA", "NFL")
            event_date: ISO format date string
            teams: Dict with team_a and team_b
            kalshi_markets: Dict with Kalshi market IDs
            polymarket_markets: Dict with Polymarket market IDs
        
        Returns:
            int: ID of inserted/updated market
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO tracked_markets 
            (event_id, description, sport, event_date, teams, kalshi_markets, polymarket_markets, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            event_id,
            description,
            sport,
            event_date,
            json.dumps(teams) if teams else None,
            json.dumps(kalshi_markets) if kalshi_markets else None,
            json.dumps(polymarket_markets) if polymarket_markets else None
        ))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def log_price_snapshot(self, event_id, platform, market_id, market_side,
                          yes_price=None, no_price=None, yes_bid=None, yes_ask=None,
                          no_bid=None, no_ask=None, volume=None, liquidity=None,
                          timestamp=None):
        """Log a price snapshot
        
        Args:
            event_id: Event identifier
            platform: 'kalshi' or 'polymarket'
            market_id: Market identifier on the platform
            market_side: Which side (e.g., 'team_a', 'team_b', 'yes', 'no')
            yes_price, no_price: Current prices
            yes_bid, yes_ask, no_bid, no_ask: Order book data
            volume: Trading volume
            liquidity: Available liquidity
            timestamp: ISO timestamp (defaults to now)
        
        Returns:
            int: ID of inserted snapshot
        """
        if timestamp is None:
            timestamp = datetime.utcnow().isoformat()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO price_snapshots
            (event_id, platform, market_id, market_side, yes_price, no_price,
             yes_bid, yes_ask, no_bid, no_ask, volume, liquidity, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event_id, platform, market_id, market_side,
            yes_price, no_price, yes_bid, yes_ask, no_bid, no_ask,
            volume, liquidity, timestamp
        ))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def log_orderbook_snapshot(self, snapshot_id, event_id, platform, market_id, 
                              side, order_type, orderbook_levels, timestamp):
        """Log orderbook depth data
        
        Args:
            snapshot_id: ID from price_snapshots table
            event_id: Event identifier
            platform: 'kalshi' or 'polymarket'
            market_id: Market identifier
            side: 'yes' or 'no'
            order_type: 'bid' or 'ask'
            orderbook_levels: List of (price, size, [count]) tuples
            timestamp: ISO timestamp
        
        Returns:
            int: Number of levels inserted
        """
        cursor = self.conn.cursor()
        
        for level, data in enumerate(orderbook_levels, 1):
            if len(data) == 2:
                price, size = data
                count = None
            elif len(data) == 3:
                price, size, count = data
            else:
                continue
            
            cursor.execute("""
                INSERT INTO orderbook_snapshots
                (snapshot_id, event_id, platform, market_id, side, order_type, 
                 level, price, size, order_count, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (snapshot_id, event_id, platform, market_id, side, order_type,
                  level, price, size, count, timestamp))
        
        self.conn.commit()
        return len(orderbook_levels)
    
    def log_arbitrage_opportunity(self, event_id, kalshi_market_id, kalshi_side, kalshi_price,
                                  polymarket_market_id, polymarket_side, polymarket_price,
                                  total_cost, profit_before_fees, profit_after_fees,
                                  kalshi_snapshot_id=None, polymarket_snapshot_id=None,
                                  time_diff_seconds=None):
        """Log a detected arbitrage opportunity
        
        Args:
            event_id: Event identifier
            kalshi_market_id, kalshi_side, kalshi_price: Kalshi side details
            polymarket_market_id, polymarket_side, polymarket_price: Polymarket side details
            total_cost: Total cost of both positions
            profit_before_fees: Profit before fees
            profit_after_fees: Profit after fees
            kalshi_snapshot_id, polymarket_snapshot_id: Links to price snapshots
            time_diff_seconds: Time between snapshots
        
        Returns:
            int: ID of logged opportunity
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO arbitrage_opportunities
            (event_id, kalshi_market_id, kalshi_side, kalshi_price,
             polymarket_market_id, polymarket_side, polymarket_price,
             total_cost, profit_before_fees, profit_after_fees,
             detected_at, kalshi_snapshot_id, polymarket_snapshot_id, time_diff_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event_id, kalshi_market_id, kalshi_side, kalshi_price,
            polymarket_market_id, polymarket_side, polymarket_price,
            total_cost, profit_before_fees, profit_after_fees,
            datetime.utcnow().isoformat(),
            kalshi_snapshot_id, polymarket_snapshot_id, time_diff_seconds
        ))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def start_collection_cycle(self, cycle_number):
        """Start a new collection cycle
        
        Args:
            cycle_number: Sequential cycle number
        
        Returns:
            int: Collection log ID
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO collection_logs (cycle_number, started_at, status)
            VALUES (?, ?, 'running')
        """, (cycle_number, datetime.utcnow().isoformat()))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def complete_collection_cycle(self, log_id, kalshi_success, kalshi_failed,
                                  polymarket_success, polymarket_failed, errors=None):
        """Complete a collection cycle with statistics
        
        Args:
            log_id: Collection log ID
            kalshi_success, kalshi_failed: Kalshi collection stats
            polymarket_success, polymarket_failed: Polymarket collection stats
            errors: List of error messages (optional)
        """
        completed_at = datetime.utcnow().isoformat()
        
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE collection_logs
            SET completed_at = ?,
                duration_seconds = (julianday(?) - julianday(started_at)) * 86400,
                markets_attempted = ?,
                kalshi_success = ?,
                kalshi_failed = ?,
                polymarket_success = ?,
                polymarket_failed = ?,
                errors = ?,
                status = 'completed'
            WHERE id = ?
        """, (
            completed_at, completed_at,
            kalshi_success + kalshi_failed + polymarket_success + polymarket_failed,
            kalshi_success, kalshi_failed,
            polymarket_success, polymarket_failed,
            json.dumps(errors) if errors else None,
            log_id
        ))
        
        self.conn.commit()
    
    def get_latest_prices(self, event_id, since_minutes=5):
        """Get latest prices for an event
        
        Args:
            event_id: Event identifier
            since_minutes: Only include prices from last N minutes
        
        Returns:
            list: List of price snapshots
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM price_snapshots
            WHERE event_id = ?
            AND datetime(timestamp) > datetime('now', '-' || ? || ' minutes')
            ORDER BY timestamp DESC
        """, (event_id, since_minutes))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_tracked_markets(self, enabled_only=True):
        """Get list of tracked markets
        
        Args:
            enabled_only: Only return enabled markets
        
        Returns:
            list: List of tracked markets
        """
        cursor = self.conn.cursor()
        query = "SELECT * FROM tracked_markets"
        if enabled_only:
            query += " WHERE enabled = 1"
        
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            print("✓ Database connection closed")


def create_test_data(db):
    """Create test data for demonstration"""
    print("\nCreating test data...")
    
    # Add a test market
    market_id = db.add_tracked_market(
        event_id="lakers_celtics_2025_01_15",
        description="Lakers vs Celtics",
        sport="NBA",
        event_date="2025-01-15T19:30:00Z",
        teams={"team_a": "Lakers", "team_b": "Celtics"},
        kalshi_markets={
            "team_a_yes": "KALSHI-LAKERS-YES",
            "team_a_no": "KALSHI-LAKERS-NO",
            "team_b_yes": "KALSHI-CELTICS-YES",
            "team_b_no": "KALSHI-CELTICS-NO"
        },
        polymarket_markets={
            "team_a": "POLY-LAKERS-WIN",
            "team_b": "POLY-CELTICS-WIN"
        }
    )
    print(f"  ✓ Added test market (ID: {market_id})")
    
    # Add some test price snapshots
    snapshot1 = db.log_price_snapshot(
        event_id="lakers_celtics_2025_01_15",
        platform="kalshi",
        market_id="KALSHI-LAKERS-YES",
        market_side="team_a",
        yes_price=0.55,
        no_price=0.45,
        yes_bid=0.54,
        yes_ask=0.56,
        volume=15000
    )
    print(f"  ✓ Added Kalshi price snapshot (ID: {snapshot1})")
    
    snapshot2 = db.log_price_snapshot(
        event_id="lakers_celtics_2025_01_15",
        platform="polymarket",
        market_id="POLY-LAKERS-WIN",
        market_side="team_a",
        yes_price=0.48,
        no_price=0.52,
        volume=25000
    )
    print(f"  ✓ Added Polymarket price snapshot (ID: {snapshot2})")
    
    # Log a test arbitrage opportunity
    # If Kalshi Lakers YES is 0.55 and Polymarket Lakers NO is 0.52
    # Total cost = 0.55 + 0.52 = 1.07 (no arbitrage in this example)
    # Let's create a profitable one:
    total_cost = 0.55 + 0.42  # = 0.97
    profit_before_fees = 1.00 - total_cost  # = 0.03
    profit_after_fees = profit_before_fees - (0.55 * 0.07) - (0.42 * 0.02)  # Account for fees
    
    arb_id = db.log_arbitrage_opportunity(
        event_id="lakers_celtics_2025_01_15",
        kalshi_market_id="KALSHI-LAKERS-YES",
        kalshi_side="yes",
        kalshi_price=0.55,
        polymarket_market_id="POLY-CELTICS-WIN",  # Opposite side
        polymarket_side="yes",
        polymarket_price=0.42,
        total_cost=total_cost,
        profit_before_fees=profit_before_fees,
        profit_after_fees=profit_after_fees,
        kalshi_snapshot_id=snapshot1,
        polymarket_snapshot_id=snapshot2,
        time_diff_seconds=2.5
    )
    print(f"  ✓ Added arbitrage opportunity (ID: {arb_id})")
    
    # Log a collection cycle
    log_id = db.start_collection_cycle(cycle_number=1)
    db.complete_collection_cycle(
        log_id=log_id,
        kalshi_success=4,
        kalshi_failed=0,
        polymarket_success=2,
        polymarket_failed=0
    )
    print(f"  ✓ Added collection log (ID: {log_id})")


if __name__ == "__main__":
    print("=" * 60)
    print("Database Setup for Prediction Market Data Logger")
    print("=" * 60)
    
    # Create database
    db = DatabaseManager()
    
    # Create tables
    db.create_tables()
    
    # Create test data
    create_test_data(db)
    
    # Display summary
    print("\n" + "=" * 60)
    print("Database created successfully!")
    print("=" * 60)
    print(f"Database location: {db.db_path}")
    print(f"Tables created: tracked_markets, price_snapshots,")
    print(f"                arbitrage_opportunities, collection_logs")
    
    # Show test data
    print("\nTest data inserted:")
    markets = db.get_tracked_markets()
    print(f"  - {len(markets)} tracked market(s)")
    
    prices = db.get_latest_prices("lakers_celtics_2025_01_15", since_minutes=60)
    print(f"  - {len(prices)} price snapshot(s)")
    
    db.close()
    
    print("\n✓ Setup complete! You can now use this database with data_logger.py")

