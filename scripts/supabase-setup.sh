#!/bin/bash

# Supabase Database Setup Script
# This script creates all required tables in Supabase PostgreSQL

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Functions
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Check prerequisites
check_requirements() {
    print_status "Checking requirements..."
    
    if ! command -v psql &> /dev/null; then
        print_error "PostgreSQL client (psql) not found. Please install it."
        exit 1
    fi
    
    print_status "PostgreSQL client found"
}

# Load environment
load_env() {
    print_status "Loading environment variables..."
    
    if [ -f ".env" ]; then
        export $(cat .env | grep -v '#' | xargs)
        print_status ".env file loaded"
    else
        print_warning ".env file not found. Using command line arguments or defaults."
    fi
}

# Validate database connection
validate_connection() {
    print_status "Validating database connection..."
    
    local DB_HOST="${1:-$DB_HOST}"
    local DB_USER="${2:-$DB_USER:-postgres}"
    local DB_NAME="${3:-$DB_NAME:-postgres}"
    
    if psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" &> /dev/null; then
        print_status "Database connection successful"
        return 0
    else
        print_error "Failed to connect to database"
        return 1
    fi
}

# Enable pgvector extension
enable_pgvector() {
    print_status "Enabling pgvector extension..."
    
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;" || {
        print_warning "Could not create pgvector extension. It may already exist."
    }
    
    # Verify
    if psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "SELECT extversion FROM pg_extension WHERE extname='vector';" &> /dev/null; then
        print_status "pgvector extension verified"
    else
        print_error "pgvector extension not available"
        exit 1
    fi
}

# Create addresses table
create_addresses_table() {
    print_status "Creating addresses table..."
    
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" << EOF
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
DROP POLICY IF EXISTS "Allow public access" ON addresses;
CREATE POLICY "Allow public access" 
ON addresses FOR ALL 
USING (true);

GRANT ALL PRIVILEGES ON addresses TO postgres;
GRANT ALL PRIVILEGES ON addresses TO authenticated;
GRANT ALL PRIVILEGES ON addresses TO anon;
EOF
    
    print_status "Addresses table created"
}

# Create address history table
create_history_table() {
    print_status "Creating address history table..."
    
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" << EOF
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

CREATE INDEX IF NOT EXISTS idx_address_history_changed_at 
ON address_history(changed_at DESC);

-- Enable RLS
ALTER TABLE address_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow public access" ON address_history;
CREATE POLICY "Allow public access" 
ON address_history FOR ALL 
USING (true);

GRANT ALL PRIVILEGES ON address_history TO postgres;
EOF
    
    print_status "Address history table created"
}

# Create similarity search cache table
create_cache_table() {
    print_status "Creating similarity search cache table..."
    
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" << EOF
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

CREATE INDEX IF NOT EXISTS idx_similarity_search_cache_query 
ON similarity_search_cache(query_address);

-- Enable RLS
ALTER TABLE similarity_search_cache ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow public access" ON similarity_search_cache;
CREATE POLICY "Allow public access" 
ON similarity_search_cache FOR ALL 
USING (true);

GRANT ALL PRIVILEGES ON similarity_search_cache TO postgres;
EOF
    
    print_status "Similarity search cache table created"
}

# Create audit log table
create_audit_table() {
    print_status "Creating audit log table..."
    
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" << EOF
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

-- Enable RLS
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow public access" ON audit_logs;
CREATE POLICY "Allow public access" 
ON audit_logs FOR ALL 
USING (true);

GRANT ALL PRIVILEGES ON audit_logs TO postgres;
EOF
    
    print_status "Audit log table created"
}

# Verify all tables
verify_tables() {
    print_status "Verifying all tables..."
    
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" << EOF
\echo '===== TABLE STRUCTURE ====='
\dt+ addresses
\echo ''
\echo '===== INDEXES ====='
SELECT indexname, tablename FROM pg_indexes WHERE tablename IN ('addresses', 'address_history', 'similarity_search_cache', 'audit_logs');
\echo ''
\echo '===== RECORD COUNT ====='
SELECT 'addresses' as table_name, COUNT(*) as record_count FROM addresses
UNION ALL
SELECT 'address_history', COUNT(*) FROM address_history
UNION ALL
SELECT 'similarity_search_cache', COUNT(*) FROM similarity_search_cache
UNION ALL
SELECT 'audit_logs', COUNT(*) FROM audit_logs;
EOF
    
    print_status "Table verification complete"
}

# Main execution
main() {
    echo -e "${GREEN}╔═══════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  Supabase Database Setup Script       ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"
    echo ""
    
    # Get database connection details
    if [ -z "$DB_HOST" ]; then
        read -p "Enter Supabase host (db.xxxxxxxxxxxx.supabase.co): " DB_HOST
    fi
    
    if [ -z "$DB_USER" ]; then
        read -p "Enter database user (postgres): " DB_USER
        DB_USER=${DB_USER:-postgres}
    fi
    
    if [ -z "$DB_NAME" ]; then
        read -p "Enter database name (postgres): " DB_NAME
        DB_NAME=${DB_NAME:-postgres}
    fi
    
    if [ -z "$DB_PASSWORD" ]; then
        read -s -p "Enter database password: " DB_PASSWORD
        echo ""
    fi
    
    # Export for psql
    export PGPASSWORD="$DB_PASSWORD"
    
    echo ""
    echo "Configuration:"
    echo "  Host: $DB_HOST"
    echo "  User: $DB_USER"
    echo "  Database: $DB_NAME"
    echo ""
    
    # Run setup steps
    check_requirements
    validate_connection "$DB_HOST" "$DB_USER" "$DB_NAME" || exit 1
    enable_pgvector
    create_addresses_table
    create_history_table
    create_cache_table
    create_audit_table
    verify_tables
    
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  Setup Complete!                      ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"
    echo ""
    print_status "All tables created successfully"
    print_status "pgvector extension is enabled"
    print_status "RLS policies configured"
    echo ""
    echo "Next steps:"
    echo "1. Update your .env file with Supabase credentials"
    echo "2. Run Python service: cd python-service && python app.py"
    echo "3. Run Java backend: ./gradlew bootRun"
    echo "4. Access frontend: http://localhost:4200"
}

# Run main function
main "$@"
