"""SQLite location knowledge base."""

import os
import sqlite3
import logging
import json
from dataclasses import dataclass, asdict
from config.constants import MEMORY_DB_FILE

logger = logging.getLogger(__name__)


@dataclass
class LocationRecord:
    """A stored location in the knowledge base."""
    city: str
    country: str
    region: str = ''
    landmark: str = ''
    aliases: list[str] = None
    gps_lat: float = 0.0
    gps_lon: float = 0.0
    gps_samples: int = 0
    ai_landmarks: list[str] = None

    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []
        if self.ai_landmarks is None:
            self.ai_landmarks = []


SCHEMA = """
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    country TEXT NOT NULL,
    region TEXT DEFAULT '',
    landmark TEXT DEFAULT '',
    aliases TEXT DEFAULT '[]',
    gps_lat REAL DEFAULT 0.0,
    gps_lon REAL DEFAULT 0.0,
    gps_samples INTEGER DEFAULT 0,
    ai_landmarks TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(city, country)
);

CREATE INDEX IF NOT EXISTS idx_locations_city ON locations(city);
CREATE INDEX IF NOT EXISTS idx_locations_country ON locations(country);
"""


class LocationMemory:
    """Persistent location knowledge base using SQLite."""

    def __init__(self, db_path: str = MEMORY_DB_FILE):
        self._db_path = db_path
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else '.', exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize database schema."""
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        logger.info(f"Location memory initialized at {self._db_path}")

    def lookup(self, city: str, country: str = '') -> LocationRecord | None:
        """Look up a location by city and optionally country."""
        query = "SELECT * FROM locations WHERE city = ?"
        params: list = [city.lower()]

        if country:
            query += " AND country = ?"
            params.append(country.lower())

        cursor = self._conn.execute(query, params)
        row = cursor.fetchone()
        if not row:
            return None

        return self._row_to_record(row)

    def lookup_by_any(self, city: str) -> LocationRecord | None:
        """Look up by city name (case-insensitive, any country)."""
        cursor = self._conn.execute(
            "SELECT * FROM locations WHERE LOWER(city) = ?",
            (city.lower(),)
        )
        row = cursor.fetchone()
        return self._row_to_record(row) if row else None

    def learn(self, record: LocationRecord) -> bool:
        """Learn or update a location record.

        Returns True if the record was new, False if updated.
        """
        existing = self.lookup(record.city, record.country)

        if existing:
            # Update existing record
            if record.region and not existing.region:
                existing.region = record.region
            if record.landmark and not existing.landmark:
                existing.landmark = record.landmark
            if record.gps_lat and not existing.gps_lat:
                existing.gps_lat = record.gps_lat
                existing.gps_lon = record.gps_lon

            # Merge aliases
            for alias in record.aliases:
                if alias.lower() not in [a.lower() for a in existing.aliases]:
                    existing.aliases.append(alias)

            # Merge AI landmarks
            for lm in record.ai_landmarks:
                if lm.lower() not in [l.lower() for l in existing.ai_landmarks]:
                    existing.ai_landmarks.append(lm)

            existing.gps_samples += record.gps_samples

            self._conn.execute("""
                UPDATE locations SET
                    region = ?, landmark = ?, aliases = ?,
                    gps_lat = ?, gps_lon = ?, gps_samples = ?,
                    ai_landmarks = ?, updated_at = CURRENT_TIMESTAMP
                WHERE city = ? AND country = ?
            """, (
                existing.region, existing.landmark,
                json.dumps(existing.aliases),
                existing.gps_lat, existing.gps_lon,
                existing.gps_samples,
                json.dumps(existing.ai_landmarks),
                record.city.lower(), record.country.lower(),
            ))
            self._conn.commit()
            return False
        else:
            # Insert new record
            self._conn.execute("""
                INSERT INTO locations
                    (city, country, region, landmark, aliases,
                     gps_lat, gps_lon, gps_samples, ai_landmarks)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.city.lower(), record.country.lower(),
                record.region, record.landmark,
                json.dumps(record.aliases),
                record.gps_lat, record.gps_lon,
                record.gps_samples,
                json.dumps(record.ai_landmarks),
            ))
            self._conn.commit()
            return True

    def get_all(self) -> list[LocationRecord]:
        """Return all stored locations."""
        cursor = self._conn.execute("SELECT * FROM locations ORDER BY updated_at DESC")
        return [self._row_to_record(row) for row in cursor.fetchall()]

    def search(self, query: str) -> list[LocationRecord]:
        """Search locations by partial match on city, country, or region."""
        pattern = f"%{query.lower()}%"
        cursor = self._conn.execute("""
            SELECT * FROM locations
            WHERE LOWER(city) LIKE ? OR LOWER(country) LIKE ? OR LOWER(region) LIKE ?
            ORDER BY gps_samples DESC
            LIMIT 10
        """, (pattern, pattern, pattern))
        return [self._row_to_record(row) for row in cursor.fetchall()]

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()

    def _row_to_record(self, row: sqlite3.Row) -> LocationRecord:
        """Convert a database row to a LocationRecord."""
        d = dict(row)
        return LocationRecord(
            city=d['city'],
            country=d['country'],
            region=d.get('region', '') or '',
            landmark=d.get('landmark', '') or '',
            aliases=json.loads(d.get('aliases', '[]')),
            gps_lat=float(d.get('gps_lat', 0.0) or 0.0),
            gps_lon=float(d.get('gps_lon', 0.0) or 0.0),
            gps_samples=int(d.get('gps_samples', 0) or 0),
            ai_landmarks=json.loads(d.get('ai_landmarks', '[]')),
        )
