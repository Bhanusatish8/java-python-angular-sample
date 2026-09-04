package com.example.config;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.CommandLineRunner;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;
import java.util.List;
import java.util.Map;

@Component
public class DatabaseInitializer implements CommandLineRunner {
    
    @Autowired
    private JdbcTemplate jdbc;
    
    @Override
    public void run(String... args) throws Exception {
        System.out.println("\n" +
            "╔═══════════════════════════════════════╗\n" +
            "║  Initializing Supabase Tables         ║\n" +
            "╚═══════════════════════════════════════╝\n");
        
        try {
            testConnection();
            enablePgVector();
            createTables();
            verifyTables();
            System.out.println("\n" +
                "╔═══════════════════════════════════════╗\n" +
                "║  ✓ Database Setup Complete!           ║\n" +
                "╚═══════════════════════════════════════╝\n");
        } catch (Exception e) {
            System.err.println("✗ Database initialization failed: " + e.getMessage());
            e.printStackTrace();
        }
    }
    
    private void testConnection() {
        try {
            String version = jdbc.queryForObject("SELECT version()", String.class);
            System.out.println("✓ Connected to PostgreSQL: " + version.substring(0, 60) + "...");
        } catch (Exception e) {
            System.err.println("✗ Connection test failed: " + e.getMessage());
            throw new RuntimeException(e);
        }
    }
    
    private void enablePgVector() {
        try {
            jdbc.execute("CREATE EXTENSION IF NOT EXISTS vector");
            
            // Verify
            List<String> result = jdbc.queryForList(
                "SELECT extversion FROM pg_extension WHERE extname='vector'",
                String.class
            );
            
            if (!result.isEmpty()) {
                System.out.println("✓ pgvector extension enabled: " + result.get(0));
            } else {
                System.out.println("⚠ pgvector may need manual installation");
            }
        } catch (Exception e) {
            System.err.println("⚠ pgvector setup: " + e.getMessage());
        }
    }
    
    private void createTables() {
        try {
            System.out.println("\n📋 Creating tables...");
            
            // Create addresses table
            jdbc.execute(
                "CREATE TABLE IF NOT EXISTS addresses (\n" +
                "    id BIGSERIAL PRIMARY KEY,\n" +
                "    original_address_encrypted TEXT NOT NULL,\n" +
                "    address_embedding vector(768) NOT NULL,\n" +
                "    encryption_salt BYTEA NOT NULL,\n" +
                "    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,\n" +
                "    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,\n" +
                "    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,\n" +
                "    metadata JSONB DEFAULT '{}'::jsonb\n" +
                ")"
            );
            System.out.println("  ✓ Created 'addresses' table");
            
            // Create indexes
            jdbc.execute(
                "CREATE INDEX IF NOT EXISTS idx_address_embedding \n" +
                "ON addresses USING ivfflat (address_embedding vector_cosine_ops) \n" +
                "WITH (lists = 100)"
            );
            System.out.println("  ✓ Created 'idx_address_embedding' index");
            
            jdbc.execute(
                "CREATE INDEX IF NOT EXISTS idx_addresses_created_at \n" +
                "ON addresses(created_at DESC)"
            );
            System.out.println("  ✓ Created 'idx_addresses_created_at' index");
            
            // Create address history table
            jdbc.execute(
                "CREATE TABLE IF NOT EXISTS address_history (\n" +
                "    id BIGSERIAL PRIMARY KEY,\n" +
                "    address_id BIGINT REFERENCES addresses(id) ON DELETE CASCADE,\n" +
                "    previous_embedding vector(768),\n" +
                "    previous_metadata JSONB,\n" +
                "    change_reason TEXT,\n" +
                "    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,\n" +
                "    changed_by UUID REFERENCES auth.users(id) ON DELETE SET NULL\n" +
                ")"
            );
            System.out.println("  ✓ Created 'address_history' table");
            
            jdbc.execute(
                "CREATE INDEX IF NOT EXISTS idx_address_history_address_id \n" +
                "ON address_history(address_id)"
            );
            System.out.println("  ✓ Created 'idx_address_history_address_id' index");
            
            // Create similarity search cache table
            jdbc.execute(
                "CREATE TABLE IF NOT EXISTS similarity_search_cache (\n" +
                "    id BIGSERIAL PRIMARY KEY,\n" +
                "    query_address TEXT NOT NULL,\n" +
                "    similar_address_ids BIGINT[] NOT NULL,\n" +
                "    similarity_scores FLOAT8[] NOT NULL,\n" +
                "    search_limit INT,\n" +
                "    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,\n" +
                "    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP + INTERVAL '24 hours'),\n" +
                "    hit_count INT DEFAULT 1\n" +
                ")"
            );
            System.out.println("  ✓ Created 'similarity_search_cache' table");
            
            jdbc.execute(
                "CREATE INDEX IF NOT EXISTS idx_similarity_search_cache_expires \n" +
                "ON similarity_search_cache(expires_at)"
            );
            System.out.println("  ✓ Created 'idx_similarity_search_cache_expires' index");
            
            // Create audit logs table
            jdbc.execute(
                "CREATE TABLE IF NOT EXISTS audit_logs (\n" +
                "    id BIGSERIAL PRIMARY KEY,\n" +
                "    table_name TEXT NOT NULL,\n" +
                "    operation TEXT NOT NULL,\n" +
                "    record_id BIGINT,\n" +
                "    old_values JSONB,\n" +
                "    new_values JSONB,\n" +
                "    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,\n" +
                "    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,\n" +
                "    ip_address INET\n" +
                ")"
            );
            System.out.println("  ✓ Created 'audit_logs' table");
            
            jdbc.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_logs_table_operation \n" +
                "ON audit_logs(table_name, operation, timestamp DESC)"
            );
            System.out.println("  ✓ Created 'idx_audit_logs_table_operation' index");
            
        } catch (Exception e) {
            System.err.println("✗ Table creation failed: " + e.getMessage());
            throw new RuntimeException(e);
        }
    }
    
    private void verifyTables() {
        try {
            System.out.println("\n🔍 Verifying tables...");
            
            List<Map<String, Object>> tables = jdbc.queryForList(
                "SELECT table_name FROM information_schema.tables " +
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' " +
                "ORDER BY table_name"
            );
            
            System.out.println("\n📊 Tables in Supabase:");
            for (Map<String, Object> table : tables) {
                String tableName = (String) table.get("table_name");
                
                // Get row count
                Integer rowCount = jdbc.queryForObject(
                    "SELECT COUNT(*) FROM " + tableName,
                    Integer.class
                );
                
                System.out.println("  ✓ " + tableName + " (rows: " + rowCount + ")");
                
                // Get column info
                List<Map<String, Object>> columns = jdbc.queryForList(
                    "SELECT column_name, data_type FROM information_schema.columns " +
                    "WHERE table_name = ? ORDER BY ordinal_position",
                    tableName
                );
                
                for (Map<String, Object> col : columns) {
                    System.out.println("      - " + col.get("column_name") + ": " + col.get("data_type"));
                }
            }
            
            // Show indexes
            System.out.println("\n🔑 Indexes:");
            List<Map<String, Object>> indexes = jdbc.queryForList(
                "SELECT indexname, tablename FROM pg_indexes " +
                "WHERE tablename IN ('addresses', 'address_history', 'similarity_search_cache', 'audit_logs') " +
                "ORDER BY tablename, indexname"
            );
            
            for (Map<String, Object> idx : indexes) {
                System.out.println("  ✓ " + idx.get("indexname") + " (on " + idx.get("tablename") + ")");
            }
            
        } catch (Exception e) {
            System.err.println("✗ Verification failed: " + e.getMessage());
        }
    }
}
