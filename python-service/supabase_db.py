"""
Supabase Database Connection Module
Handles all database operations with Supabase PostgreSQL + pgvector
"""

import os
import logging
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2 import sql
from contextlib import contextmanager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class SupabaseConnection:
    """Manages Supabase PostgreSQL connection pool"""
    
    def __init__(self):
        """Initialize connection pool"""
        self.pool = None
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Create connection pool"""
        try:
            db_config = {
                'host': os.getenv('DB_HOST'),
                'port': int(os.getenv('DB_PORT', '5432')),
                'database': os.getenv('DB_NAME', 'postgres'),
                'user': os.getenv('DB_USER', 'postgres'),
                'password': os.getenv('DB_PASSWORD'),
                'sslmode': os.getenv('DB_SSL_MODE', 'require'),
                'connect_timeout': int(os.getenv('DB_CONNECTION_TIMEOUT', '10'))
            }
            
            min_size = int(os.getenv('DB_POOL_MIN_SIZE', '2'))
            max_size = int(os.getenv('DB_POOL_MAX_SIZE', '10'))
            
            self.pool = SimpleConnectionPool(
                min_size,
                max_size,
                **db_config
            )
            
            logger.info(f"✓ Connection pool created: {min_size}-{max_size} connections")
            self._verify_pgvector()
            
        except Exception as e:
            logger.error(f"✗ Failed to create connection pool: {e}")
            raise
    
    def _verify_pgvector(self):
        """Verify pgvector extension is available"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT extversion FROM pg_extension WHERE extname='vector';")
                result = cursor.fetchone()
                
                if result:
                    logger.info(f"✓ pgvector extension available: {result[0]}")
                else:
                    logger.warning("⚠ pgvector extension not found. Installing...")
                    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                    conn.commit()
                    logger.info("✓ pgvector extension installed")
                
                cursor.close()
        except Exception as e:
            logger.error(f"✗ pgvector verification failed: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Get connection from pool"""
        conn = None
        try:
            conn = self.pool.getconn()
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                self.pool.putconn(conn)
    
    @contextmanager
    def get_cursor(self):
        """Get cursor from pool"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                yield cursor
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"Database operation error: {e}")
                raise
            finally:
                cursor.close()
    
    def close_all(self):
        """Close all connections in pool"""
        if self.pool:
            self.pool.closeall()
            logger.info("All database connections closed")


class SupabaseDB:
    """Supabase database operations"""
    
    def __init__(self):
        """Initialize database manager"""
        self.connection = SupabaseConnection()
    
    def create_tables(self):
        """Create all required tables"""
        logger.info("Creating tables...")
        
        create_queries = [
            # Addresses table
            """
            CREATE TABLE IF NOT EXISTS addresses (
                id BIGSERIAL PRIMARY KEY,
                original_address_encrypted TEXT NOT NULL,
                address_embedding vector(768) NOT NULL,
                encryption_salt BYTEA NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
                metadata JSONB DEFAULT '{}'::jsonb
            );
            """,
            
            # Indexes
            """
            CREATE INDEX IF NOT EXISTS idx_address_embedding 
            ON addresses USING ivfflat (address_embedding vector_cosine_ops)
            WITH (lists = 100);
            """,
            
            """
            CREATE INDEX IF NOT EXISTS idx_addresses_created_at 
            ON addresses(created_at DESC);
            """,
            
            # Address history table
            """
            CREATE TABLE IF NOT EXISTS address_history (
                id BIGSERIAL PRIMARY KEY,
                address_id BIGINT REFERENCES addresses(id) ON DELETE CASCADE,
                previous_embedding vector(768),
                previous_metadata JSONB,
                change_reason TEXT,
                changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                changed_by UUID REFERENCES auth.users(id) ON DELETE SET NULL
            );
            """,
            
            """
            CREATE INDEX IF NOT EXISTS idx_address_history_address_id 
            ON address_history(address_id);
            """,
            
            # Similarity cache table
            """
            CREATE TABLE IF NOT EXISTS similarity_search_cache (
                id BIGSERIAL PRIMARY KEY,
                query_address TEXT NOT NULL,
                similar_address_ids BIGINT[] NOT NULL,
                similarity_scores FLOAT8[] NOT NULL,
                search_limit INT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP + INTERVAL '24 hours'),
                hit_count INT DEFAULT 1
            );
            """,
            
            """
            CREATE INDEX IF NOT EXISTS idx_similarity_search_cache_expires 
            ON similarity_search_cache(expires_at);
            """,
            
            # Audit logs table
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id BIGSERIAL PRIMARY KEY,
                table_name TEXT NOT NULL,
                operation TEXT NOT NULL,
                record_id BIGINT,
                old_values JSONB,
                new_values JSONB,
                user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                ip_address INET
            );
            """,
            
            """
            CREATE INDEX IF NOT EXISTS idx_audit_logs_table_operation 
            ON audit_logs(table_name, operation, timestamp DESC);
            """
        ]
        
        try:
            with self.connection.get_cursor() as cursor:
                for query in create_queries:
                    cursor.execute(query)
                    logger.info(f"✓ Executed: {query.strip()[:50]}...")
            
            logger.info("✓ All tables created successfully")
            return True
            
        except Exception as e:
            logger.error(f"✗ Failed to create tables: {e}")
            return False
    
    def verify_tables(self):
        """Verify all tables exist"""
        logger.info("Verifying tables...")
        
        required_tables = [
            'addresses',
            'address_history',
            'similarity_search_cache',
            'audit_logs'
        ]
        
        try:
            with self.connection.get_cursor() as cursor:
                cursor.execute("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                existing_tables = [row[0] for row in cursor.fetchall()]
            
            for table in required_tables:
                if table in existing_tables:
                    logger.info(f"✓ Table '{table}' exists")
                else:
                    logger.error(f"✗ Table '{table}' not found")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"✗ Failed to verify tables: {e}")
            return False
    
    def test_connection(self):
        """Test database connection"""
        try:
            with self.connection.get_cursor() as cursor:
                cursor.execute("SELECT version();")
                version = cursor.fetchone()
                logger.info(f"✓ Connected to: {version[0][:50]}...")
                
                cursor.execute("SELECT COUNT(*) FROM addresses;")
                count = cursor.fetchone()[0]
                logger.info(f"✓ Addresses table has {count} records")
                
            return True
            
        except Exception as e:
            logger.error(f"✗ Connection test failed: {e}")
            return False
    
    def insert_address(self, encrypted_address, embedding, salt, metadata=None):
        """Insert address record"""
        try:
            with self.connection.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO addresses 
                    (original_address_encrypted, address_embedding, encryption_salt, metadata)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, created_at;
                """, (encrypted_address, embedding, salt, metadata or {}))
                
                result = cursor.fetchone()
                logger.info(f"✓ Address inserted with ID: {result[0]}")
                return result
                
        except Exception as e:
            logger.error(f"✗ Insert failed: {e}")
            raise
    
    def search_similar(self, embedding, limit=5):
        """Search for similar addresses"""
        try:
            with self.connection.get_cursor() as cursor:
                cursor.execute("""
                    SELECT id, address_embedding, created_at,
                           (1 - (address_embedding <=> %s)) as similarity_score
                    FROM addresses
                    ORDER BY address_embedding <=> %s
                    LIMIT %s;
                """, (embedding, embedding, limit))
                
                results = cursor.fetchall()
                logger.info(f"✓ Found {len(results)} similar addresses")
                return results
                
        except Exception as e:
            logger.error(f"✗ Search failed: {e}")
            raise
    
    def get_stats(self):
        """Get database statistics"""
        try:
            with self.connection.get_cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM addresses;")
                total_addresses = cursor.fetchone()[0]
                
                return {
                    'total_addresses': total_addresses,
                    'embedding_dimension': 768,
                    'model': 'all-mpnet-base-v2',
                    'database': 'supabase'
                }
                
        except Exception as e:
            logger.error(f"✗ Stats retrieval failed: {e}")
            raise
    
    def cleanup(self):
        """Clean up resources"""
        self.connection.close_all()
        logger.info("Database cleanup complete")


# Global instance
_db_instance = None

def get_db():
    """Get database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = SupabaseDB()
    return _db_instance
