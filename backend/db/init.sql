CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS operators (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ai_summary TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'bot')),
    type TEXT DEFAULT 'text',
    content TEXT NOT NULL,
    satisfaction BOOLEAN DEFAULT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'open',
    priority TEXT DEFAULT 'medium',
    domain TEXT DEFAULT 'general',
    user_email TEXT NOT NULL,
    summary TEXT NOT NULL,
    ai_summary TEXT,
    original_message TEXT NOT NULL,
    translated_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS kb_sources (
    id TEXT PRIMARY KEY,
    kb_type TEXT NOT NULL,
    domain_label TEXT NOT NULL,
    title TEXT,
    source_url TEXT,
    is_kyma_mobility BOOLEAN NOT NULL DEFAULT FALSE,
    search_text TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS kb_source_domains (
    label TEXT PRIMARY KEY,
    source_count INTEGER NOT NULL DEFAULT 0,
    kyma_mobility_count INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kb_sources_domain_label ON kb_sources (domain_label);
CREATE INDEX IF NOT EXISTS idx_kb_sources_kyma_mobility ON kb_sources (is_kyma_mobility);
