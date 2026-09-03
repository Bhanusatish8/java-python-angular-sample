"""
Updated Flask app with Supabase integration
"""

import os
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import numpy as np
from sentence_transformers import SentenceTransformer
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import base64
from supabase_db import get_db

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the embedding model (768-dimensional output)
logger.info("Loading SentenceTransformers model...")
embedding_model = SentenceTransformer('all-mpnet-base-v2')
logger.info("✓ Model loaded successfully")

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


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    try:
        db = get_db()
        db.test_connection()
        
        return jsonify({
            'status': 'healthy',
            'service': 'python-embedding-service',
            'embedding_dimension': 768,
            'model': 'all-mpnet-base-v2',
            'database': 'supabase',
            'pgvector': 'enabled'
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500


@app.route('/api/v1/embeddings', methods=['POST'])
def generate_embeddings():
    """
    Generate embeddings and encrypt addresses.
    Stores in Supabase with pgvector support.
    """
    try:
        data = request.get_json()
        
        if not data or 'address' not in data:
            return jsonify({'error': 'Missing required field: address'}), 400
        
        address = data['address'].strip()
        encryption_password = data.get('encryption_password', 'default-password')
        metadata = data.get('metadata', {})
        
        if not address:
            return jsonify({'error': 'Address cannot be empty'}), 400
        
        # Derive encryption key from password
        encryption_key, salt = derive_encryption_key(encryption_password)
        
        # Encrypt the address
        encrypted_address = encrypt_address(address, encryption_key)
        
        # Generate 768-dimensional embedding
        logger.info(f"Generating embedding for address: {address[:50]}...")
        embedding = get_embedding(address)
        embedding_list = embedding.tolist()
        
        # Store in Supabase
        db = get_db()
        record_id, created_at = db.insert_address(
            encrypted_address,
            embedding_list,
            salt,
            metadata
        )
        
        logger.info(f"✓ Successfully stored embedding for address ID: {record_id}")
        
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
    Stores in Supabase.
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
        
        # Insert to Supabase
        db = get_db()
        rows_inserted = 0
        
        for address, embedding in zip(addresses, embeddings):
            encrypted_address = encrypt_address(address, encryption_key)
            try:
                db.insert_address(
                    encrypted_address,
                    embedding.tolist(),
                    salt
                )
                rows_inserted += 1
            except Exception as e:
                logger.warning(f"Failed to insert {address}: {e}")
        
        logger.info(f"✓ Successfully inserted {rows_inserted} address embeddings")
        
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
    Uses pgvector IVFFlat index for fast retrieval.
    """
    try:
        data = request.get_json()
        
        if not data or 'address' not in data:
            return jsonify({'error': 'Missing required field: address'}), 400
        
        search_address = data['address'].strip()
        limit = data.get('limit', 5)
        
        # Generate embedding for search query
        search_embedding = get_embedding(search_address).tolist()
        
        # Query Supabase
        db = get_db()
        results = db.search_similar(search_embedding, limit)
        
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
    """Get database statistics from Supabase."""
    try:
        db = get_db()
        stats = db.get_stats()
        
        return jsonify(stats), 200
        
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return jsonify({'error': str(e)}), 500


@app.before_request
def initialize():
    """Initialize database on first request."""
    if not hasattr(app, 'db_initialized'):
        try:
            db = get_db()
            
            # Create tables if they don't exist
            if not db.verify_tables():
                logger.info("Creating tables...")
                db.create_tables()
            
            # Test connection
            db.test_connection()
            
            app.db_initialized = True
            logger.info("✓ Database initialization complete")
            
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
