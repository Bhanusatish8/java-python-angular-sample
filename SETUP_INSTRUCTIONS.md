# Complete Setup Guide - Supabase Integration

## 📋 Table of Contents
1. [Supabase Configuration](#supabase-configuration)
2. [Python Service Setup](#python-service-setup)
3. [Java Backend Setup](#java-backend-setup)
4. [Verify Tables in Supabase](#verify-tables-in-supabase)
5. [Testing](#testing)

---

## 🔧 Supabase Configuration

### Your Supabase Project Details
```
Project Name: Bhanusatish8's Project
Project ID: iaruucdgusynylnqwtru
Database Host: db.iaruucdgusynylnqwtru.supabase.co
Database Port: 5432
Database Name: postgres
Database User: postgres
```

### Get Your Password
1. Go to https://app.supabase.com
2. Select your project: **Bhanusatish8's Project**
3. Click **Settings** → **Database** → Copy your password
4. Or click **Project Settings** → **Reveal Database Password**

---

## 🐍 Python Service Setup

### Step 1: Configure Environment

```bash
cd python-service

# Copy template
cp .env.supabase .env

# Edit .env with your password
nano .env
```

**Update these values:**
```bash
DB_HOST=db.iaruucdgusynylnqwtru.supabase.co
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=YOUR_SUPABASE_PASSWORD  # ← Replace this
DB_SSL_MODE=require
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Run Python Service

```bash
# This will automatically create tables
python app_supabase.py
```

**Expected Output:**
```
✓ Connection pool created: 2-10 connections
✓ pgvector extension available
✓ Database initialization complete
* Running on http://0.0.0.0:5000
```

---

## ☕ Java Backend Setup

### Step 1: Configure Environment

```bash
cd backend

# Create .env file
cat > .env.supabase << 'EOF'
SPRING_DATASOURCE_URL=jdbc:postgresql://db.iaruucdgusynylnqwtru.supabase.co:5432/postgres?sslmode=require
SPRING_DATASOURCE_USERNAME=postgres
SPRING_DATASOURCE_PASSWORD=YOUR_SUPABASE_PASSWORD
EOF
```

**Edit file and replace:**
```bash
SPRING_DATASOURCE_PASSWORD=YOUR_SUPABASE_PASSWORD
```

### Step 2: Update application.yml

Edit `backend/src/main/resources/application.yml`:

```yaml
spring:
  datasource:
    url: jdbc:postgresql://db.iaruucdgusynylnqwtru.supabase.co:5432/postgres?sslmode=require
    username: postgres
    password: ${SPRING_DATASOURCE_PASSWORD:YOUR_PASSWORD}
    driver-class-name: org.postgresql.Driver
server:
  port: 8080
```

### Step 3: Run Java Backend

**Option A: With environment variables**
```bash
export SPRING_DATASOURCE_URL="jdbc:postgresql://db.iaruucdgusynylnqwtru.supabase.co:5432/postgres?sslmode=require"
export SPRING_DATASOURCE_USERNAME="postgres"
export SPRING_DATASOURCE_PASSWORD="YOUR_SUPABASE_PASSWORD"

./gradlew bootRun
```

**Option B: Direct command**
```bash
./gradlew bootRun --args='--spring.datasource.password=YOUR_PASSWORD'
```

**Expected Output:**
```
╔═══════════════════════════════════════╗
║  Initializing Supabase Tables         ║
╚═══════════════════════════════════════╝

✓ Connected to PostgreSQL: PostgreSQL 15.1 on x86_64-pc-linux-gnu...
✓ pgvector extension enabled: 0.5.0

📋 Creating tables...
  ✓ Created 'addresses' table
  ✓ Created 'idx_address_embedding' index
  ✓ Created 'idx_addresses_created_at' index
  ✓ Created 'address_history' table
  ✓ Created 'idx_address_history_address_id' index
  ✓ Created 'similarity_search_cache' table
  ✓ Created 'idx_similarity_search_cache_expires' index
  ✓ Created 'audit_logs' table
  ✓ Created 'idx_audit_logs_table_operation' index

🔍 Verifying tables...

📊 Tables in Supabase:
  ✓ addresses (rows: 0)
      - id: bigint
      - original_address_encrypted: text
      - address_embedding: vector
      - encryption_salt: bytea
      - created_at: timestamp with time zone
      - updated_at: timestamp with time zone
      - created_by: uuid
      - metadata: jsonb
  ✓ address_history (rows: 0)
  ✓ similarity_search_cache (rows: 0)
  ✓ audit_logs (rows: 0)

🔑 Indexes:
  ✓ idx_address_embedding (on addresses)
  ✓ idx_addresses_created_at (on addresses)
  ✓ idx_address_history_address_id (on address_history)
  ✓ idx_similarity_search_cache_expires (on similarity_search_cache)
  ✓ idx_audit_logs_table_operation (on audit_logs)

╔═══════════════════════════════════════╗
║  ✓ Database Setup Complete!           ║
╚═══════════════════════════════════════╝
```

---

## 🔍 Verify Tables in Supabase

### Method 1: Check in Supabase Console

1. Go to https://app.supabase.com
2. Select **Bhanusatish8's Project**
3. Click **SQL Editor** (left sidebar)
4. Run this query:

```sql
-- See all tables
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public'
ORDER BY table_name;
```

**Expected Result:**
```
| table_name                    |
|-------------------------------|
| addresses                     |
| address_history               |
| audit_logs                    |
| similarity_search_cache       |
```

### Method 2: Check Table Structure

```sql
-- See addresses table columns
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'addresses'
ORDER BY ordinal_position;
```

### Method 3: See Row Count

```sql
-- Row counts
SELECT 'addresses' as table_name, COUNT(*) as rows FROM addresses
UNION ALL
SELECT 'address_history', COUNT(*) FROM address_history
UNION ALL
SELECT 'similarity_search_cache', COUNT(*) FROM similarity_search_cache
UNION ALL
SELECT 'audit_logs', COUNT(*) FROM audit_logs;
```

### Method 4: View Indexes

```sql
-- See all indexes
SELECT indexname, tablename 
FROM pg_indexes 
WHERE tablename IN ('addresses', 'address_history', 'similarity_search_cache', 'audit_logs')
ORDER BY tablename, indexname;
```

### Method 5: Check pgvector

```sql
-- Verify pgvector
SELECT extname, extversion 
FROM pg_extension 
WHERE extname = 'vector';
```

---

## 🧪 Testing

### Test Python Service

```bash
# Health check
curl http://localhost:5000/health

# Create embedding
curl -X POST http://localhost:5000/api/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "address": "123 Main St, New York, NY 10001",
    "encryption_password": "secure-pass"
  }'

# Check stats
curl http://localhost:5000/api/v1/stats
```

### Test Java Backend

```bash
# Health check
curl http://localhost:8080/api/v1/health

# Get stats
curl http://localhost:8080/api/v1/stats

# Insert address (using embedding from Python)
curl -X POST http://localhost:8080/api/v1/addresses \
  -H "Content-Type: application/json" \
  -d '{
    "encrypted_address": "gAAAAABmXXXX...",
    "embedding": [0.1, 0.2, ...768 values...],
    "salt": "base64-salt-value"
  }'
```

### Verify Data in Supabase

After running tests, check in SQL Editor:

```sql
-- See inserted records
SELECT id, created_at, metadata 
FROM addresses 
ORDER BY created_at DESC 
LIMIT 10;

-- Count total records
SELECT COUNT(*) as total_addresses FROM addresses;
```

---

## 🚀 Full Stack Running

Once everything works, you can run all services:

```bash
# Terminal 1: Python Service
cd python-service
python app_supabase.py

# Terminal 2: Java Backend
cd backend
./gradlew bootRun

# Terminal 3: Frontend
cd frontend
ng serve
```

**Access:**
- Frontend: http://localhost:4200
- Backend: http://localhost:8080
- Python Service: http://localhost:5000

---

## ❌ Troubleshooting

### "password authentication failed"
```bash
# Check password
# Make sure SPRING_DATASOURCE_PASSWORD = your actual Supabase password
```

### "sslmode requires SSL"
```yaml
# Make sure URL includes: ?sslmode=require
url: jdbc:postgresql://db.iaruucdgusynylnqwtru.supabase.co:5432/postgres?sslmode=require
```

### "Table already exists"
This is fine! The code uses `CREATE TABLE IF NOT EXISTS`

### "pgvector extension not found"
```sql
-- Run in Supabase SQL Editor:
CREATE EXTENSION IF NOT EXISTS vector;
```

### "Cannot connect to database"
1. Check host: `db.iaruucdgusynylnqwtru.supabase.co`
2. Check port: `5432`
3. Test manually:
```bash
psql -h db.iaruucdgusynylnqwtru.supabase.co -U postgres -d postgres -c "SELECT 1"
```

---

## 📊 Database Schema Overview

### addresses table
- `id` - Unique identifier
- `original_address_encrypted` - Encrypted address text
- `address_embedding` - 768-dimensional vector (pgvector)
- `encryption_salt` - Salt for encryption
- `created_at` - Timestamp
- `metadata` - JSON metadata

### address_history table
- Tracks changes to addresses
- Foreign key to addresses table

### similarity_search_cache table
- Caches frequent searches
- Expires in 24 hours

### audit_logs table
- Compliance logging
- Tracks INSERT, UPDATE, DELETE operations

---

## ✅ Final Checklist

- [ ] Supabase project created
- [ ] Password retrieved
- [ ] Python service `.env` configured
- [ ] Python service running (`http://localhost:5000/health` works)
- [ ] Java backend `.env` configured
- [ ] Java backend running (`http://localhost:8080/api/v1/health` works)
- [ ] Tables visible in Supabase SQL Editor
- [ ] Can insert records from both services
- [ ] Can query records in Supabase

**All done! 🎉**
