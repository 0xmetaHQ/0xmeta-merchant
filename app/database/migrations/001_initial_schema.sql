-- =====================================================
-- DROP EXISTING TABLES
-- =====================================================
DROP TABLE IF EXISTS signal_items CASCADE;
DROP TABLE IF EXISTS category_feeds CASCADE;
DROP TABLE IF EXISTS payment_transactions CASCADE;

-- =====================================================
-- CREATE EXTENSION
-- =====================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- Signal Items Table (Unified news + tweets)
-- =====================================================
CREATE TABLE signal_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    oxmeta_id VARCHAR(100) UNIQUE NOT NULL,
    
    -- Source info
    source VARCHAR(20) NOT NULL CHECK (source IN ('cryptonews', 'twitter')),
    category VARCHAR(50) NOT NULL,
    sources TEXT[] NOT NULL,
    
    -- Content
    title TEXT NOT NULL,
    short_context TEXT,
    long_context TEXT,
    text TEXT,
    
    -- Sentiment
    sentiment VARCHAR(20),
    sentiment_value DOUBLE PRECISION,
    
    -- Classification
    feed_categories TEXT[],
    tokens TEXT[],
    
    -- Author
    author VARCHAR(200),
    
    -- Timestamps
    timestamp DOUBLE PRECISION NOT NULL,
    normalized_date VARCHAR(200),
    
    -- Additional data
    metadata JSONB,
    
    -- Database tracking
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for signal_items
CREATE INDEX idx_signal_oxmeta_id ON signal_items(oxmeta_id);
CREATE INDEX idx_signal_source ON signal_items(source);
CREATE INDEX idx_signal_category ON signal_items(category);
CREATE INDEX idx_signal_timestamp ON signal_items(timestamp DESC);
CREATE INDEX idx_signal_created ON signal_items(created_at DESC);
CREATE INDEX idx_signal_sentiment ON signal_items(sentiment);
CREATE INDEX idx_signal_category_timestamp ON signal_items(category, timestamp DESC);
CREATE INDEX idx_signal_tokens ON signal_items USING GIN(tokens);
CREATE INDEX idx_signal_feed_categories ON signal_items USING GIN(feed_categories);

-- =====================================================
-- Category Feeds Table
-- =====================================================
CREATE TABLE category_feeds (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category VARCHAR(50) NOT NULL,
    
    -- Separate sources
    cryptonews_items JSONB NOT NULL DEFAULT '[]'::jsonb,
    twitter_items JSONB NOT NULL DEFAULT '[]'::jsonb,
    
    -- Counts
    total_news INTEGER DEFAULT 0,
    total_tweets INTEGER DEFAULT 0,
    total_items INTEGER DEFAULT 0,
    
    -- Timestamps
    last_updated DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for category_feeds
CREATE INDEX idx_category ON category_feeds(category);
CREATE INDEX idx_category_updated ON category_feeds(category, last_updated DESC);
CREATE INDEX idx_last_updated ON category_feeds(last_updated DESC);

-- =====================================================
-- Payment Transactions Table
-- =====================================================
CREATE TABLE payment_transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Payment info
    payment_hash VARCHAR(200) UNIQUE NOT NULL,
    endpoint VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    
    -- Amount
    amount DOUBLE PRECISION NOT NULL,
    
    -- Status
    verified BOOLEAN DEFAULT FALSE,
    settled BOOLEAN DEFAULT FALSE,
    
    -- User info
    user_identifier VARCHAR(200),
    user_wallet VARCHAR(100),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    verified_at TIMESTAMP,
    settled_at TIMESTAMP,
    
    -- Transaction details
    transaction_data JSONB
);

-- Indexes for payment_transactions
CREATE INDEX idx_payment_hash ON payment_transactions(payment_hash);
CREATE INDEX idx_payment_endpoint ON payment_transactions(endpoint);
CREATE INDEX idx_payment_category ON payment_transactions(category);
CREATE INDEX idx_payment_verified ON payment_transactions(verified);
CREATE INDEX idx_payment_settled ON payment_transactions(settled);
CREATE INDEX idx_payment_created ON payment_transactions(created_at DESC);
CREATE INDEX idx_payment_user ON payment_transactions(user_wallet);

-- =====================================================
-- Comments
-- =====================================================
COMMENT ON TABLE signal_items IS 'Unified signal items from CryptoNews and Twitter';
COMMENT ON TABLE category_feeds IS 'Cached processed category feeds';
COMMENT ON TABLE payment_transactions IS 'X402 payment transaction logs';

COMMENT ON COLUMN signal_items.oxmeta_id IS 'Unique identifier: 0xmeta_{index}_{merchant}';
COMMENT ON COLUMN signal_items.sources IS 'Array of source URLs';
COMMENT ON COLUMN signal_items.sentiment_value IS 'Sentiment score 0.0-1.0';
COMMENT ON COLUMN signal_items.tokens IS 'Crypto tokens like [$BTC, $ETH]';
COMMENT ON COLUMN signal_items.metadata IS 'Extra fields (engagement, image_url, etc.)';