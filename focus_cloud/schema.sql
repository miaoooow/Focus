CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  username TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  password_salt TEXT NOT NULL,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  created_at INTEGER NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);

CREATE TABLE IF NOT EXISTS daily_usage (
  user_id TEXT NOT NULL,
  usage_day TEXT NOT NULL,
  chat_count INTEGER NOT NULL DEFAULT 0,
  pet_count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, usage_day),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
