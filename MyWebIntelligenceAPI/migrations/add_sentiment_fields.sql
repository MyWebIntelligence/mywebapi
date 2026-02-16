-- Migration: Add sentiment analysis fields to expressions table
-- Date: 2025-10-18
-- Description: Add 5 new fields for comprehensive sentiment analysis

BEGIN;

-- Add sentiment analysis fields
ALTER TABLE expressions ADD COLUMN IF NOT EXISTS sentiment_label VARCHAR(20);
ALTER TABLE expressions ADD COLUMN IF NOT EXISTS sentiment_confidence FLOAT;
ALTER TABLE expressions ADD COLUMN IF NOT EXISTS sentiment_status VARCHAR(30);
ALTER TABLE expressions ADD COLUMN IF NOT EXISTS sentiment_model VARCHAR(100);
ALTER TABLE expressions ADD COLUMN IF NOT EXISTS sentiment_computed_at TIMESTAMP WITH TIME ZONE;

-- Add comments for documentation
COMMENT ON COLUMN expressions.sentiment_score IS 'Sentiment score from -1.0 (negative) to +1.0 (positive)';
COMMENT ON COLUMN expressions.sentiment_label IS 'Sentiment label: positive, neutral, or negative';
COMMENT ON COLUMN expressions.sentiment_confidence IS 'Model confidence score (0.0 to 1.0)';
COMMENT ON COLUMN expressions.sentiment_status IS 'Status: computed, failed, unsupported_lang, no_content, low_confidence';
COMMENT ON COLUMN expressions.sentiment_model IS 'Model used for analysis (textblob or llm/model-name)';
COMMENT ON COLUMN expressions.sentiment_computed_at IS 'Timestamp when sentiment was computed';

-- Create index for filtering by sentiment status
CREATE INDEX IF NOT EXISTS idx_expressions_sentiment_status ON expressions(sentiment_status);

-- Create index for sentiment score queries
CREATE INDEX IF NOT EXISTS idx_expressions_sentiment_score ON expressions(sentiment_score) WHERE sentiment_score IS NOT NULL;

COMMIT;
