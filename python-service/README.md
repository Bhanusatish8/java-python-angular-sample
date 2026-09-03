# Python Embedding Service

A Flask-based microservice that generates 768-dimensional embeddings for addresses using open-source models and encrypts them before storing in PostgreSQL with pgvector support.

## Directory Structure

```
python-service/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker configuration
├── .env.example          # Environment variables template
├── tests.py             # Unit tests
├── scripts.sh           # Development helper scripts
└── README.md            # Documentation
```

## Quick Start

### Option 1: Local Development

```bash
cd python-service

# Setup virtual environment
bash scripts.sh setup

# Run Flask app
bash scripts.sh run

# Run tests
bash scripts.sh test

# Test API
bash scripts.sh test-api
```

### Option 2: Docker (Recommended)

```bash
# Build image
docker build -t python-embedding-service:latest .

# Run container
docker run -p 5000:5000 \
  -e DB_HOST=db \
  -e DB_NAME=myappdb \
  -e DB_USER=postgres \
  -e DB_PASSWORD=postgres \
  python-embedding-service:latest
```

### Option 3: Docker Compose (Full Stack)

```bash
# From repository root
docker-compose up

# Access services:
# - Frontend: http://localhost:4200
# - Backend API: http://localhost:8080
# - Python Service: http://localhost:5000
# - Database: localhost:5432
```

## Features

✅ **768-Dimensional Embeddings** - Using `all-mpnet-base-v2` model
✅ **Address Encryption** - Fernet symmetric encryption with PBKDF2 key derivation
✅ **pgvector Integration** - Vector similarity search with IVFFlat indexing
✅ **Batch Processing** - Generate embeddings for multiple addresses
✅ **REST API** - Full RESTful interface
✅ **Data Persistence** - PostgreSQL with pgvector extension

## API Reference

### 1. Health Check
```bash
curl http://localhost:5000/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "python-embedding-service",
  "embedding_dimension": 768,
  "model": "all-mpnet-base-v2"
}
```

### 2. Generate Single Embedding
```bash
curl -X POST http://localhost:5000/api/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "address": "123 Main St, New York, NY 10001",
    "encryption_password": "your-secure-password"
  }'
```

**Request Parameters:**
- `address` (required): The address to embed
- `encryption_password` (optional): Password for encryption (default: "default-password")

**Response:**
```json
{
  "id": 1,
  "address": "123 Main St, New York, NY 10001",
  "embedding": [0.123, 0.456, ...],
  "embedding_dimension": 768,
  "encrypted": true,
  "created_at": "2024-01-01T12:00:00Z"
}
```

### 3. Batch Generate Embeddings
```bash
curl -X POST http://localhost:5000/api/v1/embeddings/batch \
  -H "Content-Type: application/json" \
  -d '{
    "addresses": [
      "123 Main St, New York, NY 10001",
      "456 Oak Ave, Los Angeles, CA 90001"
    ],
    "encryption_password": "your-secure-password"
  }'
```

**Response:**
```json
{
  "total_processed": 2,
  "rows_inserted": 2,
  "embedding_dimension": 768,
  "encrypted": true
}
```

### 4. Search Similar Addresses
```bash
curl -X POST http://localhost:5000/api/v1/search/similar \
  -H "Content-Type: application/json" \
  -d '{
    "address": "123 Main St, New York",
    "limit": 5
  }'
```

**Response:**
```json
{
  "query": "123 Main St, New York",
  "results": [
    {
      "id": 1,
      "similarity_score": 0.98,
      "created_at": "2024-01-01T12:00:00Z"
    }
  ],
  "total_results": 1
}
```

### 5. Get Statistics
```bash
curl http://localhost:5000/api/v1/stats
```

**Response:**
```json
{
  "total_addresses": 42,
  "embedding_dimension": 768,
  "model": "all-mpnet-base-v2",
  "database": "myappdb"
}
```

## Architecture

### Data Flow
```
┌────────────────────────────┐
│   User/Frontend            │
└────────────┬───────────────┘
             │
             v
┌────────────────────────────┐
│  Java Backend (REST API)   │
│  (Spring Boot 8080)        │
└────────────┬───────────────┘
             │
             v
┌────────────────────────────┐
│  Python Service (5000)     │
│  - Embedding Generation    │
│  - Address Encryption      │
│  - Vector Storage          │
└────────────┬───────────────┘
             │
             v
┌────────────────────────────┐
│  PostgreSQL + pgvector     │
│  - Encrypted Addresses     │
│  - 768-dim Vectors         │
│  - IVFFlat Index           │
└────────────────────────────┘
```

## Database Schema

```sql
-- Addresses table with vector embeddings
CREATE TABLE addresses (
    id SERIAL PRIMARY KEY,
    original_address_encrypted TEXT NOT NULL,     -- Encrypted address
    address_embedding vector(768) NOT NULL,       -- 768-dimensional vector
    encryption_salt BYTEA NOT NULL,               -- Salt for key derivation
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Fast similarity search index
CREATE INDEX idx_address_embedding 
ON addresses USING ivfflat (address_embedding vector_cosine_ops)
WITH (lists = 100);
```

## Environment Variables

```bash
# Database
DB_HOST=db                              # PostgreSQL host
DB_PORT=5432                            # PostgreSQL port
DB_NAME=myappdb                         # Database name
DB_USER=postgres                        # Database user
DB_PASSWORD=postgres                    # Database password

# Embedding Model
EMBEDDING_MODEL=all-mpnet-base-v2      # Sentence Transformers model
EMBEDDING_DIMENSION=768                 # Vector dimension

# Flask
FLASK_ENV=production                    # Flask environment
FLASK_DEBUG=false                       # Debug mode
```

## Encryption Details

### Algorithm: Fernet (Symmetric)
- **Base**: AES-128 in CBC mode
- **Authentication**: HMAC-SHA256
- **Key Derivation**: PBKDF2 with SHA256 (100,000 iterations)

### Security Features
- Passwords never stored
- Unique salt per address
- HMAC prevents tampering
- Safe for database storage

## Performance

### Embedding Generation
- Model loading: ~40 seconds (first time)
- Single address: ~100-200ms
- Batch (32 addresses): ~200ms
- Memory: ~2GB for model

### Vector Search
- IVFFlat with 100 clusters
- Query time: 50-100ms for 10K+ vectors
- Supports 1M+ vectors efficiently

### Database
- Connection pooling supported
- Batch inserts optimized
- Auto-partitioning for large datasets

## Testing

```bash
# Run all tests
bash scripts.sh test

# Specific test
python -m pytest tests.py::EmbeddingServiceTestCase -v

# With coverage
pip install pytest-cov
pytest tests.py --cov=app --cov-report=html
```

## Integration Examples

### From Java Backend
```java
RestTemplate restTemplate = new RestTemplate();
HttpHeaders headers = new HttpHeaders();
headers.setContentType(MediaType.APPLICATION_JSON);

Map<String, String> request = new HashMap<>();
request.put("address", "123 Main St, New York");
request.put("encryption_password", "secure-pass");

ResponseEntity<Map> response = restTemplate.postForEntity(
    "http://python-worker:5000/api/v1/embeddings",
    new HttpEntity<>(request, headers),
    Map.class
);
```

### From Angular Frontend
```typescript
addAddress(address: string) {
  const payload = {
    address: address,
    encryption_password: 'your-password'
  };
  
  return this.http.post<EmbeddingResponse>(
    'http://localhost:5000/api/v1/embeddings',
    payload
  );
}
```

## Troubleshooting

### Model Download Issue
```bash
# Pre-download model
python -c "from sentence_transformers import SentenceTransformer; \
  SentenceTransformer('all-mpnet-base-v2')"
```

### Database Connection Failed
```bash
# Check PostgreSQL is running
docker ps | grep pgvector

# Verify credentials
docker-compose logs db
```

### Out of Memory
```bash
# Increase Docker memory
docker update --memory 4g <container-id>

# Or reduce batch size in requests
```

### Slow Vector Search
```sql
-- Rebuild index
REINDEX INDEX idx_address_embedding;

-- Check index statistics
SELECT * FROM pg_stat_user_indexes 
WHERE relname = 'addresses';
```

## Contributing

1. Create a feature branch
2. Add tests for new functionality
3. Ensure all tests pass: `bash scripts.sh test`
4. Submit pull request

## License

MIT License - See LICENSE file in repository root

## Support

For issues or questions:
1. Check [README.md](README.md) for detailed documentation
2. Review [tests.py](tests.py) for usage examples
3. Check Docker logs: `docker-compose logs python-worker`
4. Review application logs: `docker-compose logs python-worker --follow`
