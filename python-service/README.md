# Python Embedding Service

A Flask-based service that generates 768-dimensional embeddings for addresses and encrypts them before storing in PostgreSQL with pgvector support.

## Features

- **768-Dimensional Embeddings**: Uses `all-mpnet-base-v2` model from Sentence Transformers for high-quality embeddings
- **Address Encryption**: Encrypts addresses using Fernet symmetric encryption with PBKDF2 key derivation
- **pgvector Integration**: Stores embeddings in PostgreSQL with pgvector for fast similarity search
- **Batch Processing**: Support for processing multiple addresses simultaneously
- **Vector Similarity Search**: Find similar addresses using cosine distance
- **REST API**: Full RESTful interface for embedding generation and search

## Architecture

```
┌─────────────────┐
│  Angular Front  │
└────────┬────────┘
         │
         v
┌─────────────────┐         ┌──────────────────┐
│ Java Backend    │◄───────►│ Python Service   │
│ (Spring Boot)   │         │ (Flask)          │
└────────┬────────┘         └────────┬─────────┘
         │                           │
         └───────────┬───────────────┘
                     v
         ┌──────────────────────┐
         │  PostgreSQL + pgvector
         │  (Address Embeddings)
         └──────────────────────┘
```

## API Endpoints

### 1. Health Check
```bash
GET /health

Response:
{
  "status": "healthy",
  "service": "python-embedding-service",
  "embedding_dimension": 768,
  "model": "all-mpnet-base-v2"
}
```

### 2. Generate Single Embedding
```bash
POST /api/v1/embeddings

Request:
{
  "address": "123 Main St, New York, NY 10001",
  "encryption_password": "your-secure-password"
}

Response:
{
  "id": 1,
  "address": "123 Main St, New York, NY 10001",
  "embedding": [0.123, 0.456, ...],  // 768-dimensional array
  "embedding_dimension": 768,
  "encrypted": true,
  "created_at": "2024-01-01T12:00:00Z"
}
```

### 3. Batch Generate Embeddings
```bash
POST /api/v1/embeddings/batch

Request:
{
  "addresses": [
    "123 Main St, New York, NY 10001",
    "456 Oak Ave, Los Angeles, CA 90001"
  ],
  "encryption_password": "your-secure-password"
}

Response:
{
  "total_processed": 2,
  "rows_inserted": 2,
  "embedding_dimension": 768,
  "encrypted": true
}
```

### 4. Search Similar Addresses
```bash
POST /api/v1/search/similar

Request:
{
  "address": "123 Main St, New York",
  "limit": 5
}

Response:
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

### 5. Get Service Statistics
```bash
GET /api/v1/stats

Response:
{
  "total_addresses": 42,
  "embedding_dimension": 768,
  "model": "all-mpnet-base-v2",
  "database": "myappdb"
}
```

## Database Schema

```sql
CREATE TABLE addresses (
    id SERIAL PRIMARY KEY,
    original_address_encrypted TEXT NOT NULL,           -- Encrypted address
    address_embedding vector(768) NOT NULL,             -- 768-dimensional vector
    encryption_salt BYTEA NOT NULL,                     -- Salt for key derivation
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast similarity search
CREATE INDEX idx_address_embedding 
ON addresses USING ivfflat (address_embedding vector_cosine_ops);
```

## Setup Instructions

### Environment Variables
Copy `.env.example` to `.env` and configure:
```bash
DB_HOST=db
DB_PORT=5432
DB_NAME=myappdb
DB_USER=postgres
DB_PASSWORD=postgres
EMBEDDING_MODEL=all-mpnet-base-v2
EMBEDDING_DIMENSION=768
```

### Docker Compose
The service is configured in the main `docker-compose.yml`:
```yaml
python-worker:
  build: ./python-service
  environment:
    DB_HOST: db
    DB_NAME: myappdb
    DB_USER: postgres
    DB_PASSWORD: postgres
  depends_on:
    - db
```

### Local Development

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Set up PostgreSQL with pgvector:**
```bash
# Using Docker
docker run --name pgvector-db \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=myappdb \
  -p 5432:5432 \
  ankane/pgvector:latest
```

3. **Run the service:**
```bash
python app.py
```

4. **Test the API:**
```bash
curl -X POST http://localhost:5000/api/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "address": "123 Main St, New York, NY 10001",
    "encryption_password": "test-password"
  }'
```

## Embedding Model Details

### all-mpnet-base-v2
- **Dimensions**: 768
- **Parameters**: 110M
- **Use Cases**: 
  - Semantic search
  - Address similarity matching
  - Geographic clustering
  - High-quality representation

### Why 768 Dimensions?
- Captures fine-grained semantic information
- Suitable for address and location data
- Balanced between accuracy and performance
- Supported by pgvector IVFFlat indexing

## Encryption Details

### Method: Fernet (Symmetric Encryption)
- **Algorithm**: AES-128 in CBC mode
- **Authentication**: HMAC for integrity verification
- **Key Derivation**: PBKDF2 with SHA256 (100,000 iterations)

### Security Considerations
- Each address encrypted with password-derived key
- Salt stored with address for key re-derivation
- Safe for database storage with pgvector support

## Performance Considerations

### Embedding Generation
- First call (~40s): Model downloading and initialization
- Subsequent calls (~100-200ms per address)
- Batch processing: ~200ms per 32 addresses

### Vector Similarity Search
- IVFFlat index with 100 clusters
- Query time: ~50-100ms for 10K+ vectors
- Configurable via `lists` parameter

### Database
- Auto-partitioning enabled for large datasets
- pgvector version: 0.5.0+

## Integration with Java Backend

### Call Python Service from Java:
```java
// Spring RestTemplate example
RestTemplate restTemplate = new RestTemplate();

HttpHeaders headers = new HttpHeaders();
headers.setContentType(MediaType.APPLICATION_JSON);

Map<String, String> requestBody = new HashMap<>();
requestBody.put("address", "123 Main St, New York");
requestBody.put("encryption_password", "your-password");

HttpEntity<Map> entity = new HttpEntity<>(requestBody, headers);

ResponseEntity<Map> response = restTemplate.postForEntity(
    "http://python-worker:5000/api/v1/embeddings",
    entity,
    Map.class
);
```

## Troubleshooting

### Model Download Issues
- The first run downloads ~500MB model
- Set `SENTENCE_TRANSFORMERS_HOME` to cache location
- Pre-download with: `python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-mpnet-base-v2')"`

### Database Connection Issues
- Ensure pgvector service is running
- Check `DB_HOST` and port configuration
- Verify PostgreSQL credentials

### Memory Issues
- Reduce batch size if processing large datasets
- Increase Docker memory allocation
- Use streaming/pagination for large result sets

## License
MIT License
