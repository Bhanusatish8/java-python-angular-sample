# Supabase Integration Guide

## Overview
This guide explains how to integrate Supabase (PostgreSQL + pgvector) with the Java-Python-Angular monorepo for address embedding storage and retrieval.

## Supabase Setup

### 1. Create Supabase Project
1. Go to [Supabase Console](https://app.supabase.com)
2. Click "New Project"
3. Fill in project details:
   - **Name**: `java-python-angular-embeddings`
   - **Database Password**: Generate strong password
   - **Region**: Select closest to your location
4. Click "Create new project"

### 2. Enable pgvector Extension
Once project is created:

1. Go to **SQL Editor**
2. Click **New Query**
3. Paste and run:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 3. Get Connection Details
From **Project Settings → Database**:
- **Host**: `db.xxxxxxxxxxxx.supabase.co`
- **Port**: `5432`
- **Database**: `postgres`
- **User**: `postgres`
- **Password**: Your database password

## Database Setup

### Create Tables in Supabase

Run these SQL queries in Supabase SQL Editor:

#### Create Addresses Table
```sql
-- Create addresses table with vector embeddings
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

-- Create index for fast similarity search
CREATE INDEX IF NOT EXISTS idx_address_embedding 
ON addresses USING ivfflat (address_embedding vector_cosine_ops)
WITH (lists = 100);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_addresses_created_at 
ON addresses(created_at DESC);

-- Enable Row Level Security
ALTER TABLE addresses ENABLE ROW LEVEL SECURITY;

-- Create RLS policy (allow all for now, restrict in production)
CREATE POLICY "Allow public access" 
ON addresses FOR ALL 
USING (true);
```

#### Create Address History Table
```sql
-- Track address embedding history
CREATE TABLE IF NOT EXISTS address_history (
    id BIGSERIAL PRIMARY KEY,
    address_id BIGINT REFERENCES addresses(id) ON DELETE CASCADE,
    previous_embedding vector(768),
    previous_metadata JSONB,
    change_reason TEXT,
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    changed_by UUID REFERENCES auth.users(id) ON DELETE SET NULL
);

-- Index for fast history lookup
CREATE INDEX IF NOT EXISTS idx_address_history_address_id 
ON address_history(address_id);
```

#### Create Similarity Search Cache Table
```sql
-- Cache for frequently searched addresses
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

-- Index for cache expiration cleanup
CREATE INDEX IF NOT EXISTS idx_similarity_search_cache_expires 
ON similarity_search_cache(expires_at);
```

#### Create Audit Log Table
```sql
-- Log all operations for compliance
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL, -- INSERT, UPDATE, DELETE
    record_id BIGINT,
    old_values JSONB,
    new_values JSONB,
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ip_address INET
);

-- Index for audit queries
CREATE INDEX IF NOT EXISTS idx_audit_logs_table_operation 
ON audit_logs(table_name, operation, timestamp DESC);
```

## Environment Configuration

### Python Service (.env)
```bash
# Supabase Configuration
DB_HOST=db.xxxxxxxxxxxx.supabase.co
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=your_supabase_password
DB_SSL_MODE=require

# Embedding Configuration
EMBEDDING_MODEL=all-mpnet-base-v2
EMBEDDING_DIMENSION=768

# Flask Configuration
FLASK_ENV=production
FLASK_DEBUG=false

# Security
ENCRYPTION_SALT_LENGTH=16
PBKDF2_ITERATIONS=100000
```

### Java Backend (application.yml)
```yaml
spring:
  datasource:
    url: jdbc:postgresql://db.xxxxxxxxxxxx.supabase.co:5432/postgres?sslmode=require
    username: postgres
    password: ${DB_PASSWORD}
    driver-class-name: org.postgresql.Driver
  jpa:
    hibernate:
      ddl-auto: update
    properties:
      hibernate:
        dialect: org.hibernate.dialect.PostgreSQL10Dialect
        jdbc:
          batch_size: 20
        order_inserts: true
        order_updates: true

embedding:
  service:
    url: http://python-worker:5000/api/v1
    timeout: 30000
    max-retries: 3
```

### Angular Frontend (environment.ts)
```typescript
export const environment = {
  production: false,
  apiUrl: 'http://localhost:8080/api',
  embeddingServiceUrl: 'http://localhost:5000/api/v1',
  supabaseUrl: 'https://xxxxxxxxxxxx.supabase.co',
  supabaseAnonKey: 'your_anon_key'
};
```

## Testing Connection

### Test Python Service Connection
```bash
cd python-service

# Create test script
cat > test_supabase_connection.py << 'EOF'
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'port': os.getenv('DB_PORT', '5432'),
    'sslmode': 'require'
}

try:
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    # Check pgvector extension
    cursor.execute("SELECT extname FROM pg_extension WHERE extname='vector';")
    result = cursor.fetchone()
    if result:
        print("✓ pgvector extension is installed")
    else:
        print("✗ pgvector extension not found")
    
    # Check addresses table
    cursor.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_name = 'addresses'
    """)
    result = cursor.fetchone()
    if result:
        print("✓ addresses table exists")
    else:
        print("✗ addresses table not found")
    
    # Show table structure
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'addresses'
        ORDER BY ordinal_position
    """)
    columns = cursor.fetchall()
    print("\nAddress table schema:")
    for col_name, col_type in columns:
        print(f"  - {col_name}: {col_type}")
    
    cursor.close()
    conn.close()
    print("\n✓ Successfully connected to Supabase!")
    
except Exception as e:
    print(f"✗ Connection failed: {e}")
EOF

# Run test
python test_supabase_connection.py
```

### Test Java Backend Connection
```java
// Add to Spring Boot application
@Component
public class SupabaseConnectionTest {
    
    @Autowired
    private DataSource dataSource;
    
    @PostConstruct
    public void testConnection() {
        try (Connection conn = dataSource.getConnection()) {
            DatabaseMetaData metadata = conn.getMetaData();
            System.out.println("✓ Connected to: " + metadata.getDatabaseProductName());
            System.out.println("✓ Version: " + metadata.getDatabaseProductVersion());
            
            // Check pgvector
            try (Statement stmt = conn.createStatement()) {
                ResultSet rs = stmt.executeQuery(
                    "SELECT extname FROM pg_extension WHERE extname='vector'"
                );
                if (rs.next()) {
                    System.out.println("✓ pgvector extension available");
                }
            }
            
        } catch (SQLException e) {
            System.err.println("✗ Connection failed: " + e.getMessage());
        }
    }
}
```

## Migration from Local PostgreSQL to Supabase

### Using pg_dump
```bash
# Dump from local database
pg_dump -h localhost -U postgres -d myappdb > backup.sql

# Restore to Supabase
psql -h db.xxxxxxxxxxxx.supabase.co -U postgres -d postgres < backup.sql
```

### Using Python Migration Script
```python
# migrate_to_supabase.py
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

LOCAL_DB = {
    'host': 'localhost',
    'database': 'myappdb',
    'user': 'postgres',
    'password': 'postgres',
    'port': '5432'
}

SUPABASE_DB = {
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'port': os.getenv('DB_PORT', '5432'),
    'sslmode': 'require'
}

def migrate_data():
    # Connect to local database
    local_conn = psycopg2.connect(**LOCAL_DB)
    local_cursor = local_conn.cursor()
    
    # Connect to Supabase
    supabase_conn = psycopg2.connect(**SUPABASE_DB)
    supabase_cursor = supabase_conn.cursor()
    
    # Fetch all data from local addresses table
    local_cursor.execute("SELECT * FROM addresses")
    rows = local_cursor.fetchall()
    
    print(f"Migrating {len(rows)} records...")
    
    # Insert into Supabase
    for row in rows:
        supabase_cursor.execute("""
            INSERT INTO addresses 
            (original_address_encrypted, address_embedding, encryption_salt, metadata)
            VALUES (%s, %s, %s, %s)
        """, row[:4])
    
    supabase_conn.commit()
    print("✓ Migration complete!")
    
    # Cleanup
    local_cursor.close()
    local_conn.close()
    supabase_cursor.close()
    supabase_conn.close()

if __name__ == '__main__':
    migrate_data()
```

## API Endpoints with Supabase

### Python Service Endpoints (No changes needed)
- `POST /api/v1/embeddings` - Generate and store embedding
- `POST /api/v1/embeddings/batch` - Batch generate embeddings
- `POST /api/v1/search/similar` - Search similar addresses
- `GET /api/v1/stats` - Get statistics

### Java Backend Endpoints (New)
```java
@RestController
@RequestMapping("/api/addresses")
public class AddressController {
    
    @Autowired
    private AddressService addressService;
    
    @PostMapping
    public ResponseEntity<?> createAddress(@RequestBody AddressRequest request) {
        return ResponseEntity.ok(addressService.create(request));
    }
    
    @GetMapping("/{id}")
    public ResponseEntity<?> getAddress(@PathVariable Long id) {
        return ResponseEntity.ok(addressService.findById(id));
    }
    
    @PostMapping("/search/similar")
    public ResponseEntity<?> searchSimilar(@RequestBody SearchRequest request) {
        return ResponseEntity.ok(addressService.findSimilar(request));
    }
    
    @GetMapping("/stats")
    public ResponseEntity<?> getStats() {
        return ResponseEntity.ok(addressService.getStatistics());
    }
}
```

## Monitoring and Logging

### Enable Supabase Logging
```sql
-- Check logs
SELECT * FROM pg_stat_statements 
ORDER BY total_time DESC 
LIMIT 10;

-- Slow query analysis
SELECT query, calls, mean_time 
FROM pg_stat_statements 
WHERE mean_time > 100 
ORDER BY mean_time DESC;
```

### Application Monitoring
```bash
# Check Python service health
curl http://localhost:5000/health

# Check Java backend health
curl http://localhost:8080/actuator/health

# Monitor database connections
docker-compose exec db psql -U postgres -c "\du"
```

## Security Best Practices

1. **Never commit credentials**
   ```bash
   # Add to .gitignore
   .env
   .env.local
   secrets/
   ```

2. **Use environment variables**
   ```bash
   export DB_HOST=your_host
   export DB_PASSWORD=your_password
   ```

3. **Enable SSL/TLS**
   - Supabase enforces SSL by default
   - Set `sslmode=require` in connection strings

4. **Implement RLS (Row Level Security)**
   ```sql
   -- Only allow authenticated users to see their data
   CREATE POLICY "Users can view their own addresses" 
   ON addresses 
   FOR SELECT 
   USING (auth.uid() = created_by);
   ```

5. **Rotate credentials regularly**
   - Update database passwords monthly
   - Rotate API keys in Supabase console

## Troubleshooting

### Connection Issues
```bash
# Test SSL connection
psql -h db.xxxxxxxxxxxx.supabase.co \
     -U postgres \
     -d postgres \
     -c "SELECT version();"

# Check DNS resolution
nslookup db.xxxxxxxxxxxx.supabase.co
```

### pgvector Issues
```sql
-- Verify pgvector installation
SELECT * FROM pg_available_extensions WHERE name = 'vector';

-- Check vector type
SELECT typname FROM pg_type WHERE typname = 'vector';
```

### Performance Issues
```sql
-- Analyze query performance
EXPLAIN ANALYZE
SELECT id, (1 - (address_embedding <=> '[0.1, 0.2, ...]')) as similarity
FROM addresses
ORDER BY address_embedding <=> '[0.1, 0.2, ...]'
LIMIT 5;

-- Rebuild indexes
REINDEX INDEX idx_address_embedding;
```

## Docker Compose with Supabase

Update docker-compose.yml:
```yaml
version: '3.8'
services:
  backend:
    build: ./backend
    environment:
      SPRING_DATASOURCE_URL: jdbc:postgresql://db.xxxxxxxxxxxx.supabase.co:5432/postgres?sslmode=require
      SPRING_DATASOURCE_USERNAME: postgres
      SPRING_DATASOURCE_PASSWORD: ${DB_PASSWORD}
    ports:
      - "8080:8080"

  python-worker:
    build: ./python-service
    environment:
      DB_HOST: db.xxxxxxxxxxxx.supabase.co
      DB_NAME: postgres
      DB_USER: postgres
      DB_PASSWORD: ${DB_PASSWORD}
      DB_SSL_MODE: require
    ports:
      - "5000:5000"

  frontend:
    build: ./frontend
    ports:
      - "4200:80"
    environment:
      API_URL: http://localhost:8080
      EMBEDDING_SERVICE_URL: http://localhost:5000
```

## Next Steps

1. ✅ Set up Supabase project
2. ✅ Enable pgvector extension
3. ✅ Create database tables
4. ✅ Configure environment variables
5. ✅ Test connections
6. ✅ Run migrations if needed
7. ✅ Deploy to production

## Support

For issues:
- Check [Supabase Documentation](https://supabase.com/docs)
- Review [pgvector Documentation](https://github.com/pgvector/pgvector)
- Check application logs: `docker-compose logs`
