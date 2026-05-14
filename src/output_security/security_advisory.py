"""
Security Advisory Database Module.

Provides a database for storing and querying security advisories with version-specific
vulnerability information. Uses SQLite for local storage.

Supports:
- Multiple package managers (npm, PyPI, Maven, RubyGems, Go)
- Version range specifications
- Severity levels and CVSS scores
- Automatic updates from external sources
"""
import sqlite3
import json
import time
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from config.settings import settings
from src.proxy.logging import get_logger

logger = get_logger("security_advisory")


@dataclass
class Advisory:
    """Represents a security advisory."""
    id: str
    package_name: str
    package_manager: str
    affected_versions: str       # Stored as JSON list of version ranges
    fixed_versions: str         # Stored as JSON list of fixed versions
    severity: str
    cvss_score: float
    summary: str
    published_date: str
    references_url: str             # Stored as JSON list of reference URLs
    source: str                 # "OSV", "CVE", "NVD", etc.
    
    @property
    def references(self) -> str:
        """Alias for references_url for backward compatibility."""
        return self.references_url
    
    def get_affected_versions_list(self) -> List[str]:
        """Get affected versions as a list."""
        try:
            return json.loads(self.affected_versions) if self.affected_versions else []
        except json.JSONDecodeError:
            return []
    
    def get_fixed_versions_list(self) -> List[str]:
        """Get fixed versions as a list."""
        try:
            return json.loads(self.fixed_versions) if self.fixed_versions else []
        except json.JSONDecodeError:
            return []
    
    def get_references_list(self) -> List[str]:
        """Get references as a list."""
        try:
            return json.loads(self.references_url) if self.references_url else []
        except json.JSONDecodeError:
            return []


class SecurityAdvisoryDatabase:
    """SQLite-based security advisory database."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize the database with an optional custom path."""
        self.db_path = db_path or getattr(settings, 'VERSION_ADVISORY_DB_PATH', 'security_advisories.db')
        self.init_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create advisories table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS advisories (
                    id TEXT PRIMARY KEY,
                    package_name TEXT NOT NULL,
                    package_manager TEXT NOT NULL,
                    affected_versions TEXT,
                    fixed_versions TEXT,
                    severity TEXT,
                    cvss_score REAL,
                    summary TEXT,
                    published_date TEXT,
                    references_url TEXT,
                    source TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create index for package lookup
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_package_lookup 
                ON advisories(package_name, package_manager)
            ''')
            
            # Create index for severity filtering
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_severity 
                ON advisories(severity)
            ''')
            
            # Create metadata table for tracking updates
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS update_metadata (
                    source TEXT PRIMARY KEY,
                    last_updated TIMESTAMP,
                    update_count INTEGER DEFAULT 0
                )
            ''')
            
            conn.commit()
            logger.info("database_initialized", extra={"path": self.db_path})
    
    def add_advisory(self, advisory: Advisory) -> bool:
        """Add or update an advisory."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO advisories 
                    (id, package_name, package_manager, affected_versions, 
                     fixed_versions, severity, cvss_score, summary, 
                     published_date, references_url, source, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (
                    advisory.id,
                    advisory.package_name,
                    advisory.package_manager,
                    advisory.affected_versions,
                    advisory.fixed_versions,
                    advisory.severity,
                    advisory.cvss_score,
                    advisory.summary,
                    advisory.published_date,
                    advisory.references,
                    advisory.source
                ))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error("advisory_insert_error", extra={"error": str(e)})
            return False
    
    def get_advisories_for_package(self, package_name: str,
                                   package_manager: str) -> List[Advisory]:
        """Get all advisories for a specific package."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, package_name, package_manager, affected_versions,
                           fixed_versions, severity, cvss_score, summary,
                           published_date, references_url, source
                    FROM advisories
                    WHERE package_name = ? AND package_manager = ?
                    ORDER BY cvss_score DESC, published_date DESC
                ''', (package_name, package_manager))

                rows = cursor.fetchall()
                return [Advisory(**dict(row)) for row in rows]
        except sqlite3.Error as e:
            logger.error("advisory_fetch_error", extra={"error": str(e)})
            return []
    
    def get_advisory_by_id(self, advisory_id: str) -> Optional[Advisory]:
        """Get a specific advisory by ID."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM advisories WHERE id = ?
                ''', (advisory_id,))
                
                row = cursor.fetchone()
                return Advisory(**dict(row)) if row else None
        except sqlite3.Error as e:
            logger.error("advisory_fetch_error", extra={"error": str(e)})
            return None
    
    def get_advisories_by_severity(self, severity: str) -> List[Advisory]:
        """Get all advisories of a specific severity."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, package_name, package_manager, affected_versions,
                           fixed_versions, severity, cvss_score, summary,
                           published_date, references_url, source
                    FROM advisories
                    WHERE severity = ?
                    ORDER BY cvss_score DESC
                ''', (severity.upper(),))

                rows = cursor.fetchall()
                return [Advisory(**dict(row)) for row in rows]
        except sqlite3.Error as e:
            logger.error("advisory_fetch_error", extra={"error": str(e)})
            return []
    
    def get_critical_advisories(self) -> List[Advisory]:
        """Get all critical severity advisories."""
        return self.get_advisories_by_severity("CRITICAL")
    
    def get_recent_advisories(self, days: int = 30) -> List[Advisory]:
        """Get advisories published in the last N days."""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM advisories 
                    WHERE published_date >= ?
                    ORDER BY published_date DESC
                ''', (cutoff_date,))
                
                rows = cursor.fetchall()
                return [Advisory(**dict(row)) for row in rows]
        except sqlite3.Error as e:
            logger.error("advisory_fetch_error", extra={"error": str(e)})
            return []
    
    def update_metadata(self, source: str) -> None:
        """Update the last update timestamp for a source."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO update_metadata (source, last_updated, update_count)
                    VALUES (?, CURRENT_TIMESTAMP, 
                            COALESCE((SELECT update_count FROM update_metadata WHERE source = ?), 0) + 1)
                ''', (source, source))
                conn.commit()
        except sqlite3.Error as e:
            logger.error("metadata_update_error", extra={"error": str(e)})
    
    def get_last_update_time(self, source: str) -> Optional[datetime]:
        """Get the last update time for a source."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT last_updated FROM update_metadata WHERE source = ?
                ''', (source,))
                
                row = cursor.fetchone()
                return datetime.fromisoformat(row['last_updated']) if row else None
        except sqlite3.Error as e:
            logger.error("metadata_fetch_error", extra={"error": str(e)})
            return None
    
    def get_advisory_count(self) -> int:
        """Get total number of advisories in the database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) as count FROM advisories')
                row = cursor.fetchone()
                return row['count'] if row else 0
        except sqlite3.Error as e:
            logger.error("count_error", extra={"error": str(e)})
            return 0
    
    def get_packages_with_advisories(self) -> List[Dict[str, any]]:
        """Get all packages that have advisories, with counts."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT package_name, package_manager, COUNT(*) as advisory_count,
                           MAX(cvss_score) as max_cvss
                    FROM advisories
                    GROUP BY package_name, package_manager
                    ORDER BY advisory_count DESC
                ''')
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error("packages_fetch_error", extra={"error": str(e)})
            return []
    
    def delete_advisory(self, advisory_id: str) -> bool:
        """Delete an advisory by ID."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM advisories WHERE id = ?', (advisory_id,))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error("advisory_delete_error", extra={"error": str(e)})
            return False
    
    def clear_all_advisories(self) -> bool:
        """Clear all advisories from the database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM advisories')
                conn.commit()
                logger.warning("all_advisories_cleared")
                return True
        except sqlite3.Error as e:
            logger.error("clear_error", extra={"error": str(e)})
            return False
    
    def bulk_insert_advisories(self, advisories: List[Advisory]) -> int:
        """Bulk insert advisories."""
        count = 0
        for advisory in advisories:
            if self.add_advisory(advisory):
                count += 1
        logger.info("bulk_insert_complete", extra={"count": count})
        return count


# Global database instance
_db_instance: Optional[SecurityAdvisoryDatabase] = None


def get_advisory_database() -> SecurityAdvisoryDatabase:
    """Get or create the global database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = SecurityAdvisoryDatabase()
    return _db_instance
