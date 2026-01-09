"""
Fill Rate Logging and Empirical Model

Logs all execution attempts and outcomes to build empirical fill rate model.
This data feeds back into the race_model to improve fill probability estimates.

Key metrics logged:
- Orderbook age at execution time
- Price level used
- Fill outcome (full/partial/none)
- Time to fill
- Actual vs expected fill size

This is how you turn guesses into data-driven decisions.
"""

import sqlite3
import time
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import threading


@dataclass
class FillAttempt:
    """Record of a single fill attempt"""
    attempt_id: str
    timestamp: float
    event_id: str
    platform: str
    side: str  # 'buy' or 'sell'
    
    # Order details
    order_type: str  # 'maker' or 'taker'
    target_size: float
    limit_price: Optional[float]
    
    # Orderbook state at attempt time
    orderbook_age_ms: float
    best_price: float
    best_size: float
    level_index: int  # 0 = best, 1 = second best, etc.
    
    # Outcome
    filled: bool
    fill_size: float
    fill_price: float
    fill_time_ms: float  # Time from order to fill
    partial: bool
    
    # Predicted vs actual
    predicted_p_fill: Optional[float]
    actual_fill_ratio: float  # fill_size / target_size
    
    # Error info
    error: Optional[str]
    
    def to_dict(self) -> Dict:
        """Convert to dict for storage"""
        return asdict(self)


class FillLogger:
    """
    Log fill attempts and build empirical fill rate model
    
    Stores data in SQLite database for analysis and feeds into race_model
    for continuous improvement of fill probability estimates.
    """
    
    def __init__(self, db_path: str = "data/fill_history.db"):
        """
        Initialize fill logger
        
        Args:
            db_path: Path to SQLite database for fill history
        """
        self.db_path = db_path
        self.lock = threading.Lock()
        
        # Initialize database
        self._init_database()
        
        # In-memory statistics for quick access
        self.stats = {
            'total_attempts': 0,
            'total_fills': 0,
            'total_partials': 0,
            'total_failures': 0
        }
        
        # Load existing stats
        self._load_stats()
        
        print(f"✓ Fill logger initialized (db: {db_path})")
    
    def _init_database(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS fill_attempts (
                    attempt_id TEXT PRIMARY KEY,
                    timestamp REAL,
                    event_id TEXT,
                    platform TEXT,
                    side TEXT,
                    order_type TEXT,
                    target_size REAL,
                    limit_price REAL,
                    orderbook_age_ms REAL,
                    best_price REAL,
                    best_size REAL,
                    level_index INTEGER,
                    filled INTEGER,
                    fill_size REAL,
                    fill_price REAL,
                    fill_time_ms REAL,
                    partial INTEGER,
                    predicted_p_fill REAL,
                    actual_fill_ratio REAL,
                    error TEXT
                )
            """)
            
            # Create indices for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON fill_attempts(timestamp)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_platform_orderbook_age
                ON fill_attempts(platform, orderbook_age_ms)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_filled
                ON fill_attempts(filled)
            """)
            
            conn.commit()
    
    def _load_stats(self):
        """Load existing statistics from database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN filled = 1 AND partial = 0 THEN 1 ELSE 0 END) as fills,
                    SUM(CASE WHEN partial = 1 THEN 1 ELSE 0 END) as partials,
                    SUM(CASE WHEN filled = 0 THEN 1 ELSE 0 END) as failures
                FROM fill_attempts
            """)
            
            row = cursor.fetchone()
            if row and row[0] > 0:
                self.stats = {
                    'total_attempts': row[0],
                    'total_fills': row[1] or 0,
                    'total_partials': row[2] or 0,
                    'total_failures': row[3] or 0
                }
    
    def log_attempt(self, attempt: FillAttempt):
        """
        Log a fill attempt
        
        Args:
            attempt: FillAttempt object with execution details
        """
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO fill_attempts VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                """, (
                    attempt.attempt_id,
                    attempt.timestamp,
                    attempt.event_id,
                    attempt.platform,
                    attempt.side,
                    attempt.order_type,
                    attempt.target_size,
                    attempt.limit_price,
                    attempt.orderbook_age_ms,
                    attempt.best_price,
                    attempt.best_size,
                    attempt.level_index,
                    1 if attempt.filled else 0,
                    attempt.fill_size,
                    attempt.fill_price,
                    attempt.fill_time_ms,
                    1 if attempt.partial else 0,
                    attempt.predicted_p_fill,
                    attempt.actual_fill_ratio,
                    attempt.error
                ))
                
                conn.commit()
            
            # Update in-memory stats
            self.stats['total_attempts'] += 1
            if attempt.filled and not attempt.partial:
                self.stats['total_fills'] += 1
            elif attempt.partial:
                self.stats['total_partials'] += 1
            else:
                self.stats['total_failures'] += 1
    
    def get_fill_rate_by_age(
        self,
        platform: str,
        age_buckets_ms: List[Tuple[float, float]]
    ) -> Dict:
        """
        Calculate fill rates bucketed by orderbook age
        
        Args:
            platform: 'kalshi' or 'polymarket'
            age_buckets_ms: List of (min_age, max_age) tuples in milliseconds
        
        Returns:
            Dict with fill rates per bucket
        """
        with sqlite3.connect(self.db_path) as conn:
            results = {}
            
            for min_age, max_age in age_buckets_ms:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN filled = 1 THEN 1 ELSE 0 END) as fills
                    FROM fill_attempts
                    WHERE platform = ?
                    AND orderbook_age_ms >= ?
                    AND orderbook_age_ms < ?
                """, (platform, min_age, max_age))
                
                row = cursor.fetchone()
                total = row[0] if row else 0
                fills = row[1] if row else 0
                
                fill_rate = fills / total if total > 0 else 0
                
                results[f"{int(min_age)}-{int(max_age)}ms"] = {
                    'attempts': total,
                    'fills': fills,
                    'fill_rate': fill_rate
                }
            
            return results
    
    def get_fill_rate_by_level(self, platform: str) -> Dict:
        """
        Calculate fill rates by orderbook level
        
        Args:
            platform: 'kalshi' or 'polymarket'
        
        Returns:
            Dict with fill rates per level
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    level_index,
                    COUNT(*) as total,
                    SUM(CASE WHEN filled = 1 THEN 1 ELSE 0 END) as fills,
                    AVG(actual_fill_ratio) as avg_fill_ratio
                FROM fill_attempts
                WHERE platform = ?
                GROUP BY level_index
                ORDER BY level_index
            """, (platform,))
            
            results = {}
            for row in cursor.fetchall():
                level_index = row[0]
                total = row[1]
                fills = row[2]
                avg_ratio = row[3]
                
                results[f"level_{level_index}"] = {
                    'attempts': total,
                    'fills': fills,
                    'fill_rate': fills / total if total > 0 else 0,
                    'avg_fill_ratio': avg_ratio
                }
            
            return results
    
    def get_prediction_accuracy(self) -> Dict:
        """
        Calculate how accurate our fill probability predictions are
        
        Returns:
            Dict with prediction accuracy metrics
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    AVG(ABS(predicted_p_fill - actual_fill_ratio)) as mean_abs_error,
                    AVG(predicted_p_fill) as avg_predicted,
                    AVG(actual_fill_ratio) as avg_actual
                FROM fill_attempts
                WHERE predicted_p_fill IS NOT NULL
            """)
            
            row = cursor.fetchone()
            
            if row and row[0] > 0:
                return {
                    'samples': row[0],
                    'mean_absolute_error': row[1],
                    'avg_predicted_fill_rate': row[2],
                    'avg_actual_fill_rate': row[3],
                    'calibrated': abs(row[2] - row[3]) < 0.1  # Within 10%
                }
            
            return {
                'samples': 0,
                'mean_absolute_error': None,
                'avg_predicted_fill_rate': None,
                'avg_actual_fill_rate': None,
                'calibrated': False
            }
    
    def get_recent_fill_rate(self, minutes: int = 60) -> float:
        """
        Get fill rate for recent attempts
        
        Args:
            minutes: Look back window in minutes
        
        Returns:
            Fill rate as decimal (0.0 - 1.0)
        """
        cutoff_time = time.time() - (minutes * 60)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN filled = 1 THEN 1 ELSE 0 END) as fills
                FROM fill_attempts
                WHERE timestamp >= ?
            """, (cutoff_time,))
            
            row = cursor.fetchone()
            total = row[0] if row else 0
            fills = row[1] if row else 0
            
            return fills / total if total > 0 else 0
    
    def get_stats(self) -> Dict:
        """Get overall statistics"""
        fill_rate = self.stats['total_fills'] / self.stats['total_attempts'] if self.stats['total_attempts'] > 0 else 0
        
        return {
            **self.stats,
            'fill_rate': fill_rate,
            'recent_fill_rate_1h': self.get_recent_fill_rate(60),
            'recent_fill_rate_10m': self.get_recent_fill_rate(10)
        }
    
    def export_for_analysis(self, output_path: str, limit: int = 10000):
        """
        Export recent attempts to CSV for offline analysis
        
        Args:
            output_path: Path to output CSV file
            limit: Number of recent attempts to export
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT * FROM fill_attempts
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            
            import csv
            
            with open(output_path, 'w', newline='') as f:
                writer = csv.writer(f)
                
                # Write header
                writer.writerow([desc[0] for desc in cursor.description])
                
                # Write data
                writer.writerows(cursor.fetchall())
        
        print(f"✓ Exported {limit} attempts to {output_path}")
    
    def analyze_fill_patterns(self) -> Dict:
        """
        Analyze fill patterns to identify opportunities for improvement
        
        Returns:
            Dict with analysis insights
        """
        age_buckets = [
            (0, 100),
            (100, 500),
            (500, 1000),
            (1000, 2000),
            (2000, 5000)
        ]
        
        insights = {
            'kalshi': {},
            'polymarket': {}
        }
        
        for platform in ['kalshi', 'polymarket']:
            insights[platform] = {
                'by_age': self.get_fill_rate_by_age(platform, age_buckets),
                'by_level': self.get_fill_rate_by_level(platform)
            }
        
        insights['prediction_accuracy'] = self.get_prediction_accuracy()
        
        return insights


# Test/Example usage
def test_fill_logger():
    """Test the fill logger"""
    import uuid
    
    logger = FillLogger(db_path="data/fill_history_test.db")
    
    print("\n" + "="*60)
    print("Test: Fill Logger")
    print("="*60)
    
    # Log some test attempts
    for i in range(10):
        attempt = FillAttempt(
            attempt_id=str(uuid.uuid4()),
            timestamp=time.time(),
            event_id=f"test-event-{i % 3}",
            platform='kalshi' if i % 2 == 0 else 'polymarket',
            side='buy',
            order_type='taker',
            target_size=100,
            limit_price=0.55,
            orderbook_age_ms=i * 200,  # Varying ages
            best_price=0.55,
            best_size=150,
            level_index=0,
            filled=i % 3 != 0,  # 2/3 fill rate
            fill_size=100 if i % 3 != 0 else 0,
            fill_price=0.55 if i % 3 != 0 else 0,
            fill_time_ms=500,
            partial=False,
            predicted_p_fill=0.7,
            actual_fill_ratio=1.0 if i % 3 != 0 else 0.0,
            error=None if i % 3 != 0 else "Timeout"
        )
        logger.log_attempt(attempt)
    
    print(f"\n✓ Logged 10 test attempts")
    
    # Get stats
    stats = logger.get_stats()
    print(f"\nStats:")
    print(f"  Total attempts: {stats['total_attempts']}")
    print(f"  Total fills: {stats['total_fills']}")
    print(f"  Fill rate: {stats['fill_rate']:.1%}")
    
    # Analyze patterns
    print(f"\n--- Fill Patterns Analysis ---")
    patterns = logger.analyze_fill_patterns()
    
    for platform in ['kalshi', 'polymarket']:
        print(f"\n{platform.upper()}:")
        print(f"  By age:")
        for bucket, data in patterns[platform]['by_age'].items():
            if data['attempts'] > 0:
                print(f"    {bucket}: {data['fill_rate']:.1%} ({data['fills']}/{data['attempts']})")
    
    # Prediction accuracy
    print(f"\nPrediction accuracy:")
    acc = patterns['prediction_accuracy']
    if acc['samples'] > 0:
        print(f"  Samples: {acc['samples']}")
        print(f"  Mean abs error: {acc['mean_absolute_error']:.2%}")
        print(f"  Predicted: {acc['avg_predicted_fill_rate']:.1%}")
        print(f"  Actual: {acc['avg_actual_fill_rate']:.1%}")
        print(f"  Calibrated: {acc['calibrated']}")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    test_fill_logger()

