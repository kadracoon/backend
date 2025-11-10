DDL = """
CREATE TABLE IF NOT EXISTS sets (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('STATIC')),
  size INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS set_items (
  set_id INT NOT NULL REFERENCES sets(id) ON DELETE CASCADE,
  ord INT NOT NULL,
  tmdb_id INT NOT NULL,
  PRIMARY KEY (set_id, ord)
);

CREATE TABLE IF NOT EXISTS questions (
  id SERIAL PRIMARY KEY,
  type TEXT NOT NULL CHECK (type IN ('ONE_FRAME_FOUR_TITLES')),
  tmdb_id INT NOT NULL,
  frame_paths TEXT[] NOT NULL,           -- 1 кадр
  distractor_pool INT[] NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS set_questions (
  set_id INT NOT NULL REFERENCES sets(id) ON DELETE CASCADE,
  ord INT NOT NULL,
  question_id INT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  PRIMARY KEY (set_id, ord)
);

CREATE TABLE IF NOT EXISTS sessions (
  id SERIAL PRIMARY KEY,
  set_id INT NOT NULL REFERENCES sets(id) ON DELETE CASCADE,
  total_questions INT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS rounds (
  id SERIAL PRIMARY KEY,
  session_id INT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  question_id INT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  idx INT NOT NULL,                       -- 1..N
  options_tmdb_ids INT[] NOT NULL,
  answer_tmdb_id INT NOT NULL,
  answered_tmdb_id INT,
  is_correct BOOLEAN,
  answered_at TIMESTAMPTZ,
  UNIQUE (session_id, idx)
);

CREATE INDEX IF NOT EXISTS idx_set_questions_set ON set_questions(set_id);
CREATE INDEX IF NOT EXISTS idx_rounds_session ON rounds(session_id);
"""
