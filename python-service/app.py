"""
Python Flask Service for Address Embedding Generation and Encryption
Uses open-source SentenceTransformers for generating 768-dimensional embeddings
"""

import os
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import execute_values
import numpy as np
from sentence_transformers import SentenceTransformer
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import base64

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the embedding model (768-dimensional output)
# Using 'all-mpnet-base-v2' which produces 768-dim embeddings
logger.info("Loading SentenceTransformers model...")
embedding_model = SentenceTransformer('all-mpnet-base-v2')
logger.info("Model loaded successfully")

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'db'),
    'database': os.getenv('DB_NAME', 'myappdb'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres'),
    'port': os.getenv('DB_PORT', '5432')
}

# Encryption key derivation
def derive_encryption_key(password: str, salt: bytes = None) -> tuple:
    """
    Derive a Fernet-compatible encryption key from a password using PBKDF2.
    Returns (key, salt) tuple for encryption/decryption.
    """
    if salt is None:
        salt = os.urandom(16)
    
    kdf = PBKDF2(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key, salt


def encrypt_address(address: str, encryption_key: bytes) -> str:
    """Encrypt address using Fernet symmetric encryption."""
    cipher = Fernet(encryption_key)
    encrypted = cipher.encrypt(address.encode())
    return encrypted.decode()


def decrypt_address(encrypted_address: str, encryption_key: bytes) -> str:
    """Decrypt address using Fernet symmetric encryption."""
    cipher = Fernet(encryption_key)
    decrypted = cipher.decrypt(encrypted_address.encode())
    return decrypted.decode()


def get_embedding(text: str) -> np.ndarray:
    """
    Generate 768-dimensional embedding for given text using SentenceTransformers.
    Returns numpy array of shape (768,)
    """
    embedding = embedding_model.encode(text)
    return embedding


def get_db_connection():
    """Create and return a database connection."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"Database connection failed: {e}")
        raise


def init_db():
    """Initialize database tables and pgvector extension."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Enable pgvector extension
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        
        # Create addresses table with 768-dimensional vector column
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS addresses (
                id SERIAL PRIMARY KEY,
                original_address_encrypted TEXT NOT NULL,
                address_embedding vector(768) NOT NULL,
                encryption_salt BYTEA NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Create index on embedding column for similarity search
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_address_embedding 
            ON addresses USING ivfflat (address_embedding vector_cosine_ops)
            WITH (lists = 100);
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'python-embedding-service',
        'embedding_dimension': 768,
        'model': 'all-mpnet-base-v2'
    }), 200


@app.route('/api/v1/embeddings', methods=['POST'])
def generate_embeddings():
    """
    Generate embeddings and encrypt addresses.
    
    Request JSON:
    {
        "address": "123 Main St, New York, NY 10001",
        "encryption_password": "your-secure-password"
    }
    
    Response:
    {
        "id": 1,
        "embedding": [0.123, 0.456, ...],  # 768-dimensional vector
        "embedding_dimension": 768,
        "encrypted": true,
        "created_at": "2024-01-01T12:00:00Z"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'address' not in data:
            return jsonify({'error': 'Missing required field: address'}), 400
        
        address = data['address'].strip()
        encryption_password = data.get('encryption_password', 'default-password')
        
        if not address:
            return jsonify({'error': 'Address cannot be empty'}), 400
        
        # Derive encryption key from password
        encryption_key, salt = derive_encryption_key(encryption_password)
        
        # Encrypt the address
        encrypted_address = encrypt_address(address, encryption_key)
        
        # Generate 768-dimensional embedding
        logger.info(f"Generating embedding for address: {address[:50]}...")
        embedding = get_embedding(address)
        
        # Convert numpy array to list for JSON serialization
        embedding_list = embedding.tolist()
        
        # Store in database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO addresses (original_address_encrypted, address_embedding, encryption_salt)
            VALUES (%s, %s, %s)
            RETURNING id, created_at;
        """, (
            encrypted_address,
            embedding_list,  # pgvector accepts list format
            salt
        ))
        
        result = cursor.fetchone()
        record_id, created_at = result
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Successfully stored embedding for address ID: {record_id}")
        
        return jsonify({
            'id': record_id,
            'address': address,
            'embedding': embedding_list,
            'embedding_dimension': len(embedding_list),
            'encrypted': True,
            'created_at': created_at.isoformat() if created_at else None
        }), 201
        
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/embeddings/batch', methods=['POST'])
def generate_batch_embeddings():
    """
    Generate embeddings for multiple addresses in batch.
    
    Request JSON:
    {
        "addresses": ["123 Main St, NY", "456 Oak Ave, LA"],
        "encryption_password": "your-secure-password"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'addresses' not in data:
            return jsonify({'error': 'Missing required field: addresses'}), 400
        
        addresses = data.get('addresses', [])
        encryption_password = data.get('encryption_password', 'default-password')
        
        if not isinstance(addresses, list) or len(addresses) == 0:
            return jsonify({'error': 'addresses must be a non-empty list'}), 400
        
        # Derive encryption key
        encryption_key, salt = derive_encryption_key(encryption_password)
        
        # Generate embeddings for all addresses
        logger.info(f"Generating embeddings for {len(addresses)} addresses...")
        embeddings = embedding_model.encode(addresses)
        
        # Prepare batch insert data
        insert_data = []
        for address, embedding in zip(addresses, embeddings):
            encrypted_address = encrypt_address(address, encryption_key)
            insert_data.append((
                encrypted_address,
                embedding.tolist(),
                salt
            ))
        
        # Batch insert to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.executemany("""
            INSERT INTO addresses (original_address_encrypted, address_embedding, encryption_salt)
            VALUES (%s, %s, %s)
        """, insert_data)
        
        conn.commit()
        rows_inserted = cursor.rowcount
        
        cursor.close()
        conn.close()
        
        logger.info(f"Successfully inserted {rows_inserted} address embeddings")
        
        return jsonify({
            'total_processed': len(addresses),
            'rows_inserted': rows_inserted,
            'embedding_dimension': 768,
            'encrypted': True
        }), 201
        
    except Exception as e:
        logger.error(f"Error in batch embedding generation: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/search/similar', methods=['POST'])
def search_similar_addresses():
    """
    Search for similar addresses using vector similarity.
    
    Request JSON:
    {
        "address": "123 Main St, New York",
        "limit": 5
    }
    
    Response returns top-k similar addresses by cosine similarity.
    """
    try:
        data = request.get_json()
        
        if not data or 'address' not in data:
            return jsonify({'error': 'Missing required field: address'}), 400
        
        search_address = data['address'].strip()
        limit = data.get('limit', 5)
        
        # Generate embedding for search query
        search_embedding = get_embedding(search_address).tolist()
        
        # Query database for similar vectors
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, address_embedding, created_at,
                   (1 - (address_embedding <=> %s)) as similarity_score
            FROM addresses
            ORDER BY address_embedding <=> %s
            LIMIT %s;
        """, (search_embedding, search_embedding, limit))
        
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return jsonify({
            'query': search_address,
            'results': [
                {
                    'id': row[0],
                    'similarity_score': float(row[3]),
                    'created_at': row[2].isoformat() if row[2] else None
                }
                for row in results
            ],
            'total_results': len(results)
        }), 200
        
    except Exception as e:
        logger.error(f"Error searching similar addresses: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/stats', methods=['GET'])
def get_stats():
    """Get database statistics."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM addresses;")
        total_addresses = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'total_addresses': total_addresses,
            'embedding_dimension': 768,
            'model': 'all-mpnet-base-v2',
            'database': DB_CONFIG['database']
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return jsonify({'error': str(e)}), 500


@app.before_request
def initialize():
    """Initialize database on first request."""
    if not hasattr(app, 'db_initialized'):
        try:
            init_db()
            app.db_initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
