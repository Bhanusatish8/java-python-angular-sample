"""
Unit tests for address embedding and encryption service
"""

import unittest
import json
from app import app, encrypt_address, decrypt_address, derive_encryption_key, get_embedding
import os


class EmbeddingServiceTestCase(unittest.TestCase):
    """Test cases for embedding service"""
    
    def setUp(self):
        """Set up test client"""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
    
    def test_health_check(self):
        """Test health check endpoint"""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'healthy')
        self.assertEqual(data['embedding_dimension'], 768)
    
    def test_encryption_key_derivation(self):
        """Test encryption key derivation"""
        password = "test-password"
        key1, salt1 = derive_encryption_key(password)
        key2, salt2 = derive_encryption_key(password, salt1)
        
        # Keys should be the same if salt is reused
        self.assertEqual(key1, key2)
        
        # Different salts should produce different keys
        key3, salt3 = derive_encryption_key(password)
        self.assertNotEqual(key1, key3)
    
    def test_encrypt_decrypt(self):
        """Test address encryption and decryption"""
        address = "123 Main St, New York, NY 10001"
        password = "secure-password"
        
        key, salt = derive_encryption_key(password)
        encrypted = encrypt_address(address, key)
        decrypted = decrypt_address(encrypted, key)
        
        self.assertNotEqual(address, encrypted)
        self.assertEqual(address, decrypted)
    
    def test_embedding_generation(self):
        """Test embedding generation"""
        address = "123 Main St, New York, NY 10001"
        embedding = get_embedding(address)
        
        # Check dimensions
        self.assertEqual(len(embedding), 768)
        
        # Check that it's a numeric array
        self.assertTrue(all(isinstance(x, (int, float)) for x in embedding))
    
    def test_embedding_similarity(self):
        """Test that similar addresses produce similar embeddings"""
        address1 = "123 Main Street, New York, NY 10001"
        address2 = "123 Main St, New York, NY 10001"
        address3 = "456 Oak Avenue, Los Angeles, CA 90001"
        
        embedding1 = get_embedding(address1)
        embedding2 = get_embedding(address2)
        embedding3 = get_embedding(address3)
        
        # Calculate cosine similarity
        from numpy.linalg import norm
        
        def cosine_similarity(a, b):
            return sum(x * y for x, y in zip(a, b)) / (norm(a) * norm(b))
        
        sim_similar = cosine_similarity(embedding1, embedding2)
        sim_different = cosine_similarity(embedding1, embedding3)
        
        # Similar addresses should have higher similarity
        self.assertGreater(sim_similar, sim_different)


class EmbeddingAPITestCase(unittest.TestCase):
    """Test cases for API endpoints"""
    
    def setUp(self):
        """Set up test client"""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
    
    def test_missing_address_field(self):
        """Test error handling for missing address"""
        response = self.client.post(
            '/api/v1/embeddings',
            data=json.dumps({'encryption_password': 'test'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
    
    def test_empty_address(self):
        """Test error handling for empty address"""
        response = self.client.post(
            '/api/v1/embeddings',
            data=json.dumps({
                'address': '   ',
                'encryption_password': 'test'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
    
    def test_batch_empty_list(self):
        """Test error handling for empty batch"""
        response = self.client.post(
            '/api/v1/embeddings/batch',
            data=json.dumps({
                'addresses': [],
                'encryption_password': 'test'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
    
    def test_stats_endpoint(self):
        """Test stats endpoint"""
        response = self.client.get('/api/v1/stats')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('total_addresses', data)
        self.assertEqual(data['embedding_dimension'], 768)


if __name__ == '__main__':
    unittest.main()
