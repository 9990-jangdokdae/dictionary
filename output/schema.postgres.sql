CREATE TABLE stock_terms (
  id BIGSERIAL PRIMARY KEY,
  term TEXT NOT NULL,
  aliases JSONB NOT NULL DEFAULT '[]'::jsonb,
  category TEXT NOT NULL,
  definition TEXT NOT NULL,
  source_name TEXT NOT NULL,
  source_url TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
