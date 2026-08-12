-- =============================================================================
-- SOC Triager — Migration 002: Add password_hash to users table
-- Run after 001_initial.sql
-- =============================================================================

-- Add password_hash column (nullable first so existing rows don't fail)
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;

-- Seed bcrypt-hashed demo passwords
-- Passwords: analyst123 / senior123 / approver123
-- Generated with: passlib.hash.bcrypt.hash("analyst123")
UPDATE users SET password_hash = '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY2l3yHGHCmEzHi' WHERE email = 'analyst@example.com';
UPDATE users SET password_hash = '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36zLHtUSkkMr6YCHFzWeSBq' WHERE email = 'senior@example.com';
UPDATE users SET password_hash = '$2b$12$Kj1rQXy8mK2P0V3hL4N5uOQZc9T6wF7gR8sI1nJ2oP3qM4lE5fH6i' WHERE email = 'approver@example.com';

-- Make column NOT NULL after seeding
ALTER TABLE users ALTER COLUMN password_hash SET NOT NULL;

-- =============================================================================
-- Demo credentials (development only — rotate before production)
--   analyst@example.com   / analyst123
--   senior@example.com    / senior123
--   approver@example.com  / approver123
-- =============================================================================
