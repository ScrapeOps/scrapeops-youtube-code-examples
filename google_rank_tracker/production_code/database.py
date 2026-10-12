#!/usr/bin/env python3
"""
Database layer for Google Rank Tracker

SQLite for simplicity, easily swapped for PostgreSQL in production.
"""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from pathlib import Path


@dataclass
class Keyword:
    """A keyword being tracked."""
    id: Optional[int]
    keyword: str
    target_url: str
    location: str
    language: str
    created_at: Optional[datetime] = None


@dataclass
class Ranking:
    """A single ranking snapshot."""
    id: Optional[int]
    keyword_id: int
    position: Optional[int]  # None if not in top 100
    url: Optional[str]
    title: Optional[str]
    date: date
    serp_features: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None


class RankTrackerDB:
    """Database manager for rank tracking."""
    
    def __init__(self, db_path: str = "rank_tracker.db"):
        self.db_path = db_path
        self._init_db()
    
    @contextmanager
    def _get_conn(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_db(self):
        """Initialize database schema."""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT NOT NULL,
                    target_url TEXT NOT NULL,
                    location TEXT DEFAULT 'us',
                    language TEXT DEFAULT 'en',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(keyword, target_url, location)
                );
                
                CREATE TABLE IF NOT EXISTS rankings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword_id INTEGER NOT NULL,
                    position INTEGER,
                    url TEXT,
                    title TEXT,
                    date DATE NOT NULL,
                    serp_features TEXT,  -- JSON
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (keyword_id) REFERENCES keywords(id),
                    UNIQUE(keyword_id, date)
                );
                
                CREATE INDEX IF NOT EXISTS idx_rankings_date ON rankings(date);
                CREATE INDEX IF NOT EXISTS idx_rankings_keyword_date ON rankings(keyword_id, date);
            """)
    
    # Keyword operations
    
    def add_keyword(self, keyword: str, target_url: str, 
                    location: str = "us", language: str = "en") -> int:
        """Add a keyword to track. Returns keyword ID."""
        with self._get_conn() as conn:
            cursor = conn.execute("""
                INSERT OR IGNORE INTO keywords (keyword, target_url, location, language)
                VALUES (?, ?, ?, ?)
            """, (keyword, target_url, location, language))
            
            if cursor.lastrowid:
                return cursor.lastrowid
            
            # Already exists, get ID
            row = conn.execute("""
                SELECT id FROM keywords 
                WHERE keyword = ? AND target_url = ? AND location = ?
            """, (keyword, target_url, location)).fetchone()
            return row["id"]
    
    def get_keywords(self, active_only: bool = True) -> List[Keyword]:
        """Get all tracked keywords."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM keywords ORDER BY created_at DESC
            """).fetchall()
            
            return [
                Keyword(
                    id=row["id"],
                    keyword=row["keyword"],
                    target_url=row["target_url"],
                    location=row["location"],
                    language=row["language"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]
    
    # Ranking operations
    
    def save_ranking(self, keyword_id: int, position: Optional[int],
                     url: Optional[str], title: Optional[str],
                     ranking_date: Optional[date] = None,
                     serp_features: Optional[Dict] = None) -> int:
        """Save a ranking snapshot. Returns ranking ID."""
        if ranking_date is None:
            ranking_date = date.today()
        
        import json
        features_json = json.dumps(serp_features) if serp_features else None
        
        with self._get_conn() as conn:
            cursor = conn.execute("""
                INSERT OR REPLACE INTO rankings 
                (keyword_id, position, url, title, date, serp_features)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (keyword_id, position, url, title, ranking_date.isoformat(), features_json))
            
            return cursor.lastrowid
    
    def get_ranking_history(self, keyword_id: int, 
                            days: int = 30) -> List[Ranking]:
        """Get ranking history for a keyword."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM rankings 
                WHERE keyword_id = ? 
                AND date >= date('now', '-{} days')
                ORDER BY date DESC
            """.format(days), (keyword_id,)).fetchall()
            
            import json
            return [
                Ranking(
                    id=row["id"],
                    keyword_id=row["keyword_id"],
                    position=row["position"],
                    url=row["url"],
                    title=row["title"],
                    date=date.fromisoformat(row["date"]),
                    serp_features=json.loads(row["serp_features"]) if row["serp_features"] else None,
                    created_at=row["created_at"],
                )
                for row in rows
            ]
    
    def get_latest_rankings(self, days: int = 1) -> List[Dict[str, Any]]:
        """Get latest rankings for all keywords."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT 
                    k.keyword,
                    k.target_url,
                    k.location,
                    r.position,
                    r.url as ranked_url,
                    r.date
                FROM keywords k
                LEFT JOIN rankings r ON k.id = r.keyword_id
                WHERE r.date >= date('now', '-{} days')
                ORDER BY k.keyword, r.date DESC
            """.format(days)).fetchall()
            
            return [dict(row) for row in rows]
    
    def get_position_changes(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get keywords with significant position changes."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                WITH ranked AS (
                    SELECT 
                        k.keyword,
                        k.target_url,
                        r.position,
                        r.date,
                        ROW_NUMBER() OVER (PARTITION BY k.id ORDER BY r.date DESC) as rn
                    FROM keywords k
                    JOIN rankings r ON k.id = r.keyword_id
                    WHERE r.date >= date('now', '-{} days')
                ),
                current AS (
                    SELECT keyword, target_url, position as current_pos
                    FROM ranked WHERE rn = 1
                ),
                previous AS (
                    SELECT keyword, target_url, position as prev_pos
                    FROM ranked WHERE rn = {}
                )
                SELECT 
                    c.keyword,
                    c.target_url,
                    p.prev_pos,
                    c.current_pos,
                    (p.prev_pos - c.current_pos) as change
                FROM current c
                JOIN previous p ON c.keyword = p.keyword AND c.target_url = p.target_url
                WHERE ABS(p.prev_pos - c.current_pos) >= 3
                ORDER BY ABS(p.prev_pos - c.current_pos) DESC
            """.format(days, days + 1)).fetchall()
            
            return [dict(row) for row in rows]


# Convenience functions for common operations

def init_tracker(db_path: str = "rank_tracker.db") -> RankTrackerDB:
    """Initialize and return a tracker instance."""
    return RankTrackerDB(db_path)


def track_keyword(db: RankTrackerDB, keyword: str, target_url: str,
                  location: str = "us") -> int:
    """Add a keyword to track."""
    return db.add_keyword(keyword, target_url, location)


def record_ranking(db: RankTrackerDB, keyword_id: int,
                   position: Optional[int], url: Optional[str] = None,
                   title: Optional[str] = None,
                   ranking_date: Optional[date] = None,
                   serp_features: Optional[Dict] = None) -> int:
    """Record a ranking snapshot."""
    return db.save_ranking(
        keyword_id,
        position,
        url,
        title,
        ranking_date=ranking_date,
        serp_features=serp_features,
    )


# Example usage
if __name__ == "__main__":
    db = init_tracker("example_tracker.db")
    
    # Add keywords
    kw1 = track_keyword(db, "proxy api", "https://scrapeops.com")
    kw2 = track_keyword(db, "web scraping api", "https://scrapeops.com")
    kw3 = track_keyword(db, "serp api", "https://scrapeops.com")
    
    print(f"Tracking {len(db.get_keywords())} keywords")
    
    # Simulate recording rankings
    from datetime import date, timedelta
    
    for i in range(7):
        record_date = date.today() - timedelta(days=6-i)
        record_ranking(db, kw1, 3 + (i % 2), "https://scrapeops.com",
                      ranking_date=record_date)
        record_ranking(db, kw2, 5 + (i % 3), "https://scrapeops.com",
                      ranking_date=record_date)
    
    # Check history
    history = db.get_ranking_history(kw1, days=7)
    print(f"\nRanking history for 'proxy api':")
    for r in history:
        print(f"  {r.date}: position {r.position}")
    
    # Check changes
    changes = db.get_position_changes(days=7)
    print(f"\nSignificant changes (7 days):")
    for c in changes:
        print(f"  {c['keyword']}: {c['prev_pos']} → {c['current_pos']} "
              f"({'↑' if c['change'] > 0 else '↓'} {abs(c['change'])})")
