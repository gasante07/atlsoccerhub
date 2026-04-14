"""Database models and setup - SQLite and PostgreSQL support"""
import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, List, Dict, Any, Iterator, Union

# Import logger if available
try:
    from api.utils.logger import get_logger, log_database_operation
    logger = get_logger(__name__)
except ImportError:
    logger = None
    def log_database_operation(*args, **kwargs):
        pass

try:
    import psycopg2
    from psycopg2 import IntegrityError as PgIntegrityError
    from psycopg2.extras import RealDictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False
    PgIntegrityError = Exception  # no-op for isinstance


def _row_to_dict(row) -> Dict[str, Any]:
    """Convert a row (sqlite3.Row or RealDictRow) to a plain dict."""
    if hasattr(row, "keys"):
        return dict(row)
    return row


class Database:
    def __init__(self, db_path: Optional[str] = None, database_url: Optional[str] = None):
        if database_url and HAS_PSYCOPG2:
            self.use_pg = True
            self.database_url = database_url
            self.db_path = None
        elif db_path:
            self.use_pg = False
            self.db_path = db_path
            self.database_url = None
        else:
            raise ValueError("Provide either db_path or database_url (with psycopg2 installed)")
        self.init_database()

    def _sql(self, sql: str) -> str:
        """Convert ? placeholders to %s for PostgreSQL."""
        return sql.replace("?", "%s") if self.use_pg else sql

    @contextmanager
    def get_connection(self) -> Iterator[Union[sqlite3.Connection, "psycopg2.extensions.connection"]]:
        """
        Get database connection with automatic cleanup.
        Use as context manager: with db.get_connection() as conn: ...
        """
        conn = None
        try:
            if self.use_pg:
                conn = psycopg2.connect(self.database_url)
                yield conn
                conn.commit()
            else:
                conn = sqlite3.connect(self.db_path, timeout=10.0)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                yield conn
                conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            if logger:
                log_database_operation("ERROR", "connection", False, error=str(e))
            raise
        finally:
            if conn:
                conn.close()

    def _cursor(self, conn):
        """Return a cursor; for PostgreSQL use RealDictCursor so rows are dict-like."""
        if self.use_pg:
            return conn.cursor(cursor_factory=RealDictCursor)
        return conn.cursor()

    def _execute(self, cursor, sql: str, params: tuple = ()):
        """Execute SQL with correct placeholders."""
        cursor.execute(self._sql(sql), params)

    def _fetchone_dict(self, cursor) -> Optional[Dict[str, Any]]:
        row = cursor.fetchone()
        return _row_to_dict(row) if row else None

    def _fetchall_dict(self, cursor) -> List[Dict[str, Any]]:
        return [_row_to_dict(row) for row in cursor.fetchall()]

    def init_database(self):
        """Initialize database tables."""
        with self.get_connection() as conn:
            cur = self._cursor(conn)
            if self.use_pg:
                self._init_pg(cur)
            else:
                self._init_sqlite(cur)
            log_database_operation("INIT", "database", True)

    def _init_sqlite(self, cur):
        cur.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                email TEXT NOT NULL,
                city TEXT NOT NULL,
                name TEXT,
                phone TEXT,
                skill_level TEXT,
                organizer_interest TEXT,
                preferred_times TEXT,
                page_url TEXT,
                utm_json TEXT,
                ip TEXT,
                user_agent TEXT,
                consent INTEGER DEFAULT 0,
                honeypot TEXT,
                referral_code TEXT,
                referred_by TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS referral_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL UNIQUE,
                referral_code TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_email TEXT NOT NULL,
                referee_email TEXT NOT NULL,
                referral_code TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_badges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                badge_type TEXT NOT NULL,
                earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)
        self._execute(cur, "CREATE INDEX IF NOT EXISTS idx_referral_code ON referral_codes(referral_code)")
        self._execute(cur, "CREATE INDEX IF NOT EXISTS idx_referrer_email ON referrals(referrer_email)")
        self._execute(cur, "CREATE INDEX IF NOT EXISTS idx_referee_email ON referrals(referee_email)")
        self._execute(cur, "CREATE INDEX IF NOT EXISTS idx_user_email_badges ON user_badges(user_email)")
        self._execute(cur, "CREATE INDEX IF NOT EXISTS idx_leads_referral_code ON leads(referral_code)")
        self._execute(cur, "CREATE INDEX IF NOT EXISTS idx_leads_referred_by ON leads(referred_by)")

    def _init_pg(self, cur):
        cur.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                email TEXT NOT NULL,
                city TEXT NOT NULL,
                name TEXT,
                phone TEXT,
                skill_level TEXT,
                organizer_interest TEXT,
                preferred_times TEXT,
                page_url TEXT,
                utm_json TEXT,
                ip TEXT,
                user_agent TEXT,
                consent INTEGER DEFAULT 0,
                honeypot TEXT,
                referral_code TEXT,
                referred_by TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS referral_codes (
                id SERIAL PRIMARY KEY,
                user_email TEXT NOT NULL UNIQUE,
                referral_code TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id SERIAL PRIMARY KEY,
                referrer_email TEXT NOT NULL,
                referee_email TEXT NOT NULL,
                referral_code TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_badges (
                id SERIAL PRIMARY KEY,
                user_email TEXT NOT NULL,
                badge_type TEXT NOT NULL,
                earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)
        for idx, tbl_col in [("idx_referral_code", "referral_codes (referral_code)"),
                             ("idx_referrer_email", "referrals (referrer_email)"),
                             ("idx_referee_email", "referrals (referee_email)"),
                             ("idx_user_email_badges", "user_badges (user_email)"),
                             ("idx_leads_referral_code", "leads (referral_code)"),
                             ("idx_leads_referred_by", "leads (referred_by)")]:
            cur.execute(f"CREATE INDEX IF NOT EXISTS {idx} ON {tbl_col}")

    def insert_lead(self, data: Dict[str, Any]) -> int:
        """Insert a new lead"""
        try:
            with self.get_connection() as conn:
                cur = self._cursor(conn)
                if self.use_pg:
                    cur.execute("""
                        INSERT INTO leads (
                            email, city, name, phone, skill_level, organizer_interest,
                            preferred_times, page_url, utm_json, ip, user_agent, consent, honeypot,
                            referral_code, referred_by
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        data.get("email"), data.get("city"), data.get("name"), data.get("phone"),
                        data.get("skill_level"), data.get("organizer_interest"), data.get("preferred_times"),
                        data.get("page_url"), data.get("utm_json"), data.get("ip"), data.get("user_agent"),
                        1 if data.get("consent") else 0, data.get("honeypot"),
                        data.get("referral_code"), data.get("referred_by")
                    ))
                    row = cur.fetchone()
                    lead_id = row["id"] if row else 0
                else:
                    self._execute(cur, """
                        INSERT INTO leads (
                            email, city, name, phone, skill_level, organizer_interest,
                            preferred_times, page_url, utm_json, ip, user_agent, consent, honeypot,
                            referral_code, referred_by
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        data.get("email"), data.get("city"), data.get("name"), data.get("phone"),
                        data.get("skill_level"), data.get("organizer_interest"), data.get("preferred_times"),
                        data.get("page_url"), data.get("utm_json"), data.get("ip"), data.get("user_agent"),
                        1 if data.get("consent") else 0, data.get("honeypot"),
                        data.get("referral_code"), data.get("referred_by")
                    ))
                    lead_id = cur.lastrowid
                log_database_operation("INSERT", "leads", True, lead_id=lead_id)
                return lead_id
        except Exception as e:
            log_database_operation("INSERT", "leads", False, error=str(e))
            raise

    def get_leads(
        self,
        city: Optional[str] = None,
        organizer_interest: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get leads with filters"""
        with self.get_connection() as conn:
            cur = self._cursor(conn)
            query = "SELECT * FROM leads WHERE 1=1"
            params = []
            if city:
                query += " AND city = ?"
                params.append(city)
            if organizer_interest:
                query += " AND organizer_interest = ?"
                params.append(organizer_interest)
            if date_from:
                query += " AND DATE(created_at) >= ?"
                params.append(date_from)
            if date_to:
                query += " AND DATE(created_at) <= ?"
                params.append(date_to)
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            self._execute(cur, query, tuple(params))
            result = self._fetchall_dict(cur)
            log_database_operation("SELECT", "leads", True, count=len(result))
            return result

    def count_leads(
        self,
        city: Optional[str] = None,
        organizer_interest: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> int:
        """Count leads with filters"""
        with self.get_connection() as conn:
            cur = self._cursor(conn)
            query = "SELECT COUNT(*) as count FROM leads WHERE 1=1"
            params = []
            if city:
                query += " AND city = ?"
                params.append(city)
            if organizer_interest:
                query += " AND organizer_interest = ?"
                params.append(organizer_interest)
            if date_from:
                query += " AND DATE(created_at) >= ?"
                params.append(date_from)
            if date_to:
                query += " AND DATE(created_at) <= ?"
                params.append(date_to)
            self._execute(cur, query, tuple(params))
            row = self._fetchone_dict(cur)
            count = row["count"] if row else 0
            log_database_operation("COUNT", "leads", True, count=count)
            return count

    def get_stats(self) -> Dict[str, Any]:
        """Get community statistics including leads_today, leads_this_week, week_over_week."""
        with self.get_connection() as conn:
            cur = self._cursor(conn)
            stats = {}
            self._execute(cur, "SELECT COUNT(*) as count FROM leads")
            stats["total_members"] = self._fetchone_dict(cur)["count"]
            self._execute(cur, "SELECT COUNT(*) as count FROM leads WHERE organizer_interest = 'yes'")
            stats["organizers"] = self._fetchone_dict(cur)["count"]
            self._execute(cur, """
                SELECT city, COUNT(*) as count FROM leads GROUP BY city ORDER BY count DESC
            """)
            stats["by_city"] = self._fetchall_dict(cur)
            if self.use_pg:
                cur.execute("""
                    SELECT COUNT(*) as count FROM leads
                    WHERE (created_at AT TIME ZONE 'UTC')::date = CURRENT_DATE
                """)
                stats["leads_today"] = cur.fetchone()["count"]
                cur.execute("""
                    SELECT COUNT(*) as count FROM leads
                    WHERE date_trunc('week', (created_at AT TIME ZONE 'UTC')) = date_trunc('week', CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
                """)
                stats["leads_this_week"] = cur.fetchone()["count"]
                cur.execute("""
                    SELECT COUNT(*) as count FROM leads
                    WHERE date_trunc('week', (created_at AT TIME ZONE 'UTC')) = date_trunc('week', (CURRENT_TIMESTAMP AT TIME ZONE 'UTC') - interval '7 days')
                """)
                stats["leads_last_week"] = cur.fetchone()["count"]
            else:
                self._execute(cur, "SELECT COUNT(*) as count FROM leads WHERE DATE(created_at) = date('now')")
                stats["leads_today"] = (self._fetchone_dict(cur) or {}).get("count", 0)
                self._execute(cur, """
                    SELECT COUNT(*) as count FROM leads
                    WHERE strftime('%%Y-%%W', created_at) = strftime('%%Y-%%W', 'now')
                """)
                stats["leads_this_week"] = (self._fetchone_dict(cur) or {}).get("count", 0)
                self._execute(cur, """
                    SELECT COUNT(*) as count FROM leads
                    WHERE strftime('%%Y-%%W', created_at) = strftime('%%Y-%%W', datetime('now', '-7 days'))
                """)
                stats["leads_last_week"] = (self._fetchone_dict(cur) or {}).get("count", 0)
            last = stats.get("leads_last_week", 0)
            this = stats.get("leads_this_week", 0)
            if last and last > 0:
                stats["week_over_week_pct"] = round((this - last) / last * 100, 1)
            else:
                stats["week_over_week_pct"] = None
            log_database_operation("SELECT", "stats", True)
            return stats

    def create_referral_code(self, user_email: str, referral_code: str) -> bool:
        """Create a referral code for a user"""
        try:
            with self.get_connection() as conn:
                cur = self._cursor(conn)
                self._execute(cur, """
                    INSERT INTO referral_codes (user_email, referral_code, is_active)
                    VALUES (?, ?, 1)
                """, (user_email, referral_code))
                log_database_operation("INSERT", "referral_codes", True, email=user_email)
                return True
        except (sqlite3.IntegrityError, PgIntegrityError):
            log_database_operation("INSERT", "referral_codes", False, reason="duplicate")
            return False

    def get_referral_code(self, user_email: str) -> Optional[Dict[str, Any]]:
        """Get referral code for a user"""
        with self.get_connection() as conn:
            cur = self._cursor(conn)
            self._execute(cur, "SELECT * FROM referral_codes WHERE user_email = ? AND is_active = 1", (user_email,))
            return self._fetchone_dict(cur)

    def get_referral_code_by_code(self, referral_code: str) -> Optional[Dict[str, Any]]:
        """Get referral code info by code"""
        with self.get_connection() as conn:
            cur = self._cursor(conn)
            self._execute(cur, "SELECT * FROM referral_codes WHERE referral_code = ? AND is_active = 1", (referral_code,))
            return self._fetchone_dict(cur)

    def create_referral(self, referrer_email: str, referee_email: str, referral_code: str) -> int:
        """Create a referral record"""
        with self.get_connection() as conn:
            cur = self._cursor(conn)
            if self.use_pg:
                cur.execute("""
                    INSERT INTO referrals (referrer_email, referee_email, referral_code, status)
                    VALUES (%s, %s, %s, 'active') RETURNING id
                """, (referrer_email, referee_email, referral_code))
                row = cur.fetchone()
                referral_id = row["id"] if row else 0
            else:
                self._execute(cur, """
                    INSERT INTO referrals (referrer_email, referee_email, referral_code, status)
                    VALUES (?, ?, ?, 'active')
                """, (referrer_email, referee_email, referral_code))
                referral_id = cur.lastrowid
            log_database_operation("INSERT", "referrals", True, referral_id=referral_id)
            return referral_id

    def get_referral_count(self, user_email: str) -> int:
        """Get total referral count for a user"""
        with self.get_connection() as conn:
            cur = self._cursor(conn)
            self._execute(cur, """
                SELECT COUNT(*) as count FROM referrals
                WHERE referrer_email = ? AND status = 'active'
            """, (user_email,))
            row = self._fetchone_dict(cur)
            return row["count"] if row else 0

    def get_user_badges(self, user_email: str) -> List[Dict[str, Any]]:
        """Get badges for a user"""
        with self.get_connection() as conn:
            cur = self._cursor(conn)
            self._execute(cur, "SELECT * FROM user_badges WHERE user_email = ? ORDER BY earned_at DESC", (user_email,))
            return self._fetchall_dict(cur)

    def award_badge(self, user_email: str, badge_type: str, metadata: Optional[str] = None) -> int:
        """Award a badge to a user"""
        with self.get_connection() as conn:
            cur = self._cursor(conn)
            self._execute(cur, "SELECT id FROM user_badges WHERE user_email = ? AND badge_type = ?", (user_email, badge_type))
            if self._fetchone_dict(cur):
                return 0
            if self.use_pg:
                cur.execute("""
                    INSERT INTO user_badges (user_email, badge_type, metadata)
                    VALUES (%s, %s, %s) RETURNING id
                """, (user_email, badge_type, metadata))
                row = cur.fetchone()
                badge_id = row["id"] if row else 0
            else:
                self._execute(cur, """
                    INSERT INTO user_badges (user_email, badge_type, metadata) VALUES (?, ?, ?)
                """, (user_email, badge_type, metadata))
                badge_id = cur.lastrowid
            log_database_operation("INSERT", "user_badges", True, badge_id=badge_id)
            return badge_id

    def get_leaderboard(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get referral leaderboard"""
        with self.get_connection() as conn:
            cur = self._cursor(conn)
            if self.use_pg:
                cur.execute("""
                    SELECT referrer_email, COUNT(*) as referral_count,
                           STRING_AGG(DISTINCT badge_type, ',') as badges
                    FROM referrals r
                    LEFT JOIN user_badges ub ON r.referrer_email = ub.user_email
                    WHERE r.status = 'active'
                    GROUP BY referrer_email
                    ORDER BY referral_count DESC
                    LIMIT %s
                """, (limit,))
            else:
                self._execute(cur, """
                    SELECT referrer_email, COUNT(*) as referral_count,
                           GROUP_CONCAT(DISTINCT badge_type) as badges
                    FROM referrals r
                    LEFT JOIN user_badges ub ON r.referrer_email = ub.user_email
                    WHERE r.status = 'active'
                    GROUP BY referrer_email
                    ORDER BY referral_count DESC
                    LIMIT ?
                """, (limit,))
            rows = self._fetchall_dict(cur)
            leaderboard = []
            for idx, row in enumerate(rows, 1):
                badges_val = row.get("badges")
                leaderboard.append({
                    "rank": idx,
                    "email": row["referrer_email"],
                    "referral_count": row["referral_count"],
                    "badges": badges_val.split(",") if badges_val else []
                })
            log_database_operation("SELECT", "leaderboard", True, count=len(leaderboard))
            return leaderboard

    def get_user_rank(self, user_email: str) -> Optional[int]:
        """Get user's rank on leaderboard"""
        with self.get_connection() as conn:
            cur = self._cursor(conn)
            self._execute(cur, """
                SELECT COUNT(*) + 1 as rank
                FROM (
                    SELECT referrer_email, COUNT(*) as count
                    FROM referrals
                    WHERE status = 'active'
                    GROUP BY referrer_email
                    HAVING count > (
                        SELECT COUNT(*) FROM referrals
                        WHERE referrer_email = ? AND status = 'active'
                    )
                )
            """, (user_email,))
            row = self._fetchone_dict(cur)
            return row["rank"] if row else None


# Single shared instance: use PostgreSQL when DATABASE_URL is set, else SQLite
def _create_db():
    from api.utils.config import DATABASE_URL, DATABASE_PATH
    if DATABASE_URL and HAS_PSYCOPG2:
        return Database(database_url=DATABASE_URL)
    return Database(db_path=DATABASE_PATH)


db = _create_db()
