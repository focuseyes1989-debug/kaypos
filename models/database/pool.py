# models/database/pool.py
"""
Connection pool implementation with thread safety.
"""

import os
import sys
import sqlite3
import threading
import weakref
from queue import Queue, Empty
from loguru import logger
from utils.db_compat import database_url, is_postgres_backend

# 🔥 Dynamic DB_NAME based on execution context
def get_db_path():
    """Get the correct database path."""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    db_dir = os.path.join(base_dir, 'database')
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, 'pos.db')

DB_NAME = get_db_path()
POOL_SIZE = 5  # ✅ Reduced for stability


class ConnectionPool:
    """Simple connection pool for SQLite with automatic return on close."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._pool = Queue(maxsize=POOL_SIZE)
                cls._instance._size = POOL_SIZE
                cls._instance._initialized = False
                cls._instance._initialize_pool()
        return cls._instance

    def _initialize_pool(self):
        """Create initial connections."""
        try:
            # 🔥 Ensure database directory exists
            if is_postgres_backend():
                if not database_url():
                    logger.warning("PostgreSQL backend selected, but no ZAY_POS_DATABASE_URL/DATABASE_URL is configured yet")
                    self._initialized = True
                    return
                try:
                    for _ in range(self._size):
                        conn = self._create_connection()
                        self._pool.put(conn)
                    logger.info(f"PostgreSQL connection pool initialized with {self._pool.qsize()} connection(s)")
                except Exception as e:
                    logger.warning(f"Failed to create initial PostgreSQL connection: {e}")
                self._initialized = True
                return

            db_dir = os.path.dirname(DB_NAME)
            os.makedirs(db_dir, exist_ok=True)
            
            # 🔥 Test write permissions
            test_file = os.path.join(db_dir, '.write_test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            
            # ✅ Create at least ONE connection immediately
            try:
                conn = self._create_connection()
                self._pool.put(conn)
                logger.info(f"✅ Created initial connection (pool size: {self._pool.qsize()})")
            except Exception as e:
                logger.warning(f"Failed to create initial connection: {e}")
            
            self._initialized = True
            logger.info(f"✅ Connection pool initialized with {self._pool.qsize()} connections")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize connection pool: {e}")
            # 🔥 Try emergency connection
            try:
                conn = self._create_connection()
                self._pool.put(conn)
                self._initialized = True
                logger.info("✅ Created emergency connection")
            except Exception as e2:
                logger.error(f"❌ Emergency connection failed: {e2}")
                # 🔥 Last resort: create a direct connection on demand
                self._initialized = False

    def _create_connection(self):
        """Create a new database connection."""
        try:
            if is_postgres_backend():
                from models.database.postgres_adapter import connect_postgres

                url = database_url()
                if not url:
                    raise RuntimeError(
                        "ZAY_POS_DB_BACKEND=postgres requires ZAY_POS_DATABASE_URL or DATABASE_URL."
                    )
                conn = connect_postgres(url)
                conn.execute("SELECT 1").fetchone()
                logger.debug("New PostgreSQL database connection created")
                return conn

            db_dir = os.path.dirname(DB_NAME)
            os.makedirs(db_dir, exist_ok=True)
            
            # ✅ Simple connection without WAL for better stability
            conn = sqlite3.connect(
                DB_NAME,
                timeout=60,  # ✅ Increased timeout
                check_same_thread=False,
                isolation_level=None  # ✅ Auto-commit mode
            )
            
            # ✅ Configure connection
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-1000000")
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA busy_timeout=60000")  # ✅ 60 second busy timeout
            
            # ✅ Test connection
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            
            logger.debug(f"✅ New database connection created")
            return conn
            
        except sqlite3.OperationalError as e:
            logger.error(f"❌ SQLite operational error: {e}")
            # 🔥 Try to recover
            try:
                # Try without WAL
                conn = sqlite3.connect(DB_NAME, timeout=60, check_same_thread=False)
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("PRAGMA busy_timeout=60000")
                return conn
            except:
                raise
            
        except Exception as e:
            logger.error(f"❌ Failed to create database connection: {e}")
            raise

    def get_connection(self, timeout=5.0, max_retries=3):
        """Get a connection from the pool with retry logic."""
        retries = 0
        last_error = None
        
        while retries < max_retries:
            try:
                # ✅ If pool is empty, create a new connection directly
                if self._pool.empty():
                    logger.warning("Pool is empty, creating direct connection")
                    try:
                        conn = self._create_connection()
                        return _PooledConnection(conn, self)
                    except Exception as e:
                        logger.error(f"Failed to create direct connection: {e}")
                        retries += 1
                        import time
                        time.sleep(0.5)
                        continue
                
                # Try to get connection from pool
                try:
                    conn = self._pool.get(timeout=timeout)
                except Empty:
                    logger.warning(f"Connection pool empty after timeout, retry {retries + 1}/{max_retries}")
                    retries += 1
                    import time
                    time.sleep(0.5)
                    continue
                
                # Check if connection is still alive
                try:
                    conn.execute("SELECT 1").fetchone()
                except (sqlite3.OperationalError, sqlite3.DatabaseError, AttributeError):
                    logger.warning("Connection is dead, creating new one")
                    try:
                        conn.close()
                    except:
                        pass
                    conn = self._create_connection()
                
                # Rollback any pending transaction
                try:
                    conn.rollback()
                except:
                    pass
                
                return _PooledConnection(conn, self)
                
            except Exception as e:
                last_error = e
                retries += 1
                logger.warning(f"Error getting connection (retry {retries}/{max_retries}): {e}")
                import time
                time.sleep(0.5)
        
        # 🔥 If all retries failed, create a direct connection
        logger.error(f"All retries failed, creating direct connection: {last_error}")
        try:
            conn = self._create_connection()
            return _PooledConnection(conn, self)
        except Exception as e:
            logger.error(f"Direct connection also failed: {e}")
            raise

    def return_connection(self, conn):
        """Return a connection to the pool."""
        if conn:
            try:
                # Rollback any pending transaction
                try:
                    conn.rollback()
                except:
                    pass
                
                # Check if connection is still alive before returning
                try:
                    conn.execute("SELECT 1").fetchone()
                    self._pool.put(conn)
                except:
                    logger.warning("Connection is dead, closing instead of returning")
                    try:
                        conn.close()
                    except:
                        pass
                    
            except Exception as e:
                logger.error(f"Failed to return connection to pool: {e}")
                try:
                    conn.close()
                except:
                    pass

    def close_all(self):
        """Close all connections in the pool."""
        closed_count = 0
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                try:
                    conn.close()
                    closed_count += 1
                except:
                    pass
            except:
                pass
        logger.info(f"✅ Closed {closed_count} pooled connections")


class _PooledConnection:
    """Wrapper that returns the connection to the pool when closed."""
    def __init__(self, conn, pool):
        self._conn = conn
        self._pool = pool
        self._finalizer = weakref.finalize(self, self._close_and_return)

    def _close_and_return(self):
        if self._conn:
            try:
                self._pool.return_connection(self._conn)
            except:
                try:
                    self._conn.close()
                except:
                    pass
            self._conn = None

    def close(self):
        self._close_and_return()
        self._finalizer.detach()

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __enter__(self):
        return self._conn.__enter__()

    def __exit__(self, *args):
        self.close()


# 🔥 Global pool instance
_pool = None

def get_pool():
    """Get or create the connection pool."""
    global _pool
    if _pool is None:
        try:
            _pool = ConnectionPool()
            logger.info("✅ Connection pool created")
        except Exception as e:
            logger.error(f"❌ Failed to create connection pool: {e}")
            # 🔥 Create a minimal pool
            _pool = ConnectionPool()
    return _pool

# 🔥 Initialize pool on import
get_pool()


def get_pool_stats():
    """Get connection pool statistics."""
    try:
        pool = get_pool()
        with pool._lock:
            return {
                "pool_size": pool._pool.qsize(),
                "max_size": POOL_SIZE,
                "available": pool._pool.qsize(),
                "usage_percentage": ((POOL_SIZE - pool._pool.qsize()) / POOL_SIZE * 100) if POOL_SIZE > 0 else 0
            }
    except Exception as e:
        logger.error(f"Failed to get pool stats: {e}")
        return {}


def is_connection_healthy(conn):
    """Check if a database connection is still alive."""
    try:
        if conn is None:
            return False
        conn.execute("SELECT 1").fetchone()
        return True
    except Exception:
        return False
