CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS operators (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL DEFAULT 'Operatore',
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO operators (name, email, password_hash)
VALUES (
    'Operatore',
    'operatore@talos.it',
    '$2a$06$.VV5inNW2OX5P8Ws5YAXP.vCtnT3tvPK4AVBR7/ytliDej8LGOMGS'
)
ON CONFLICT (email) DO NOTHING;

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'bot')),
    type TEXT NOT NULL DEFAULT 'text' CHECK (type IN ('text', 'image', 'audio')),
    content TEXT DEFAULT NULL,
    caption TEXT DEFAULT NULL,
    media_url TEXT DEFAULT NULL,
    sources JSONB DEFAULT NULL,
    satisfaction BOOLEAN DEFAULT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    escalated_message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'aperto',
    priority TEXT DEFAULT 'media',
    domain TEXT DEFAULT 'informazioni generali',
    user_email TEXT NOT NULL,
    summary TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tickets_escalated_message_id ON tickets(escalated_message_id);
