-- SQLite schema for LOCAL_MODE (single-user, no Docker).
--
-- Hand-translated superset of migrations/000..003 (Postgres). Differences:
--   * No extensions, functions, or triggers — the backend supplies ids and
--     timestamps in Python on INSERT/UPDATE.
--   * UUID -> TEXT, JSONB -> TEXT, TIMESTAMPTZ -> TEXT (ISO-8601 strings),
--     BIGINT/INT -> INTEGER, FLOAT -> REAL, BOOLEAN -> INTEGER (0/1).
--   * No ai_rate_limit_events table — local mode uses an in-process limiter.
-- Idempotent: every statement is IF NOT EXISTS. Column names match the
-- Postgres schema exactly, including the quoted camelCase BetterAuth columns.

-- ─── BetterAuth: user table ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS "user" (
  id               TEXT PRIMARY KEY,
  name             TEXT NOT NULL,
  email            TEXT NOT NULL UNIQUE,
  "emailVerified"  INTEGER NOT NULL DEFAULT 0,
  image            TEXT,
  "createdAt"      TEXT NOT NULL,
  "updatedAt"      TEXT NOT NULL
);

-- ─── BetterAuth: session table ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS session (
  id           TEXT PRIMARY KEY,
  "expiresAt"  TEXT NOT NULL,
  token        TEXT NOT NULL UNIQUE,
  "createdAt"  TEXT NOT NULL,
  "updatedAt"  TEXT NOT NULL,
  "ipAddress"  TEXT,
  "userAgent"  TEXT,
  "userId"     TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE
);

-- ─── BetterAuth: account table ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS account (
  id                      TEXT PRIMARY KEY,
  "accountId"             TEXT NOT NULL,
  "providerId"            TEXT NOT NULL,
  "userId"                TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  "accessToken"           TEXT,
  "refreshToken"          TEXT,
  "idToken"               TEXT,
  "accessTokenExpiresAt"  TEXT,
  "refreshTokenExpiresAt" TEXT,
  scope                   TEXT,
  password                TEXT,
  "createdAt"             TEXT NOT NULL,
  "updatedAt"             TEXT NOT NULL
);

-- ─── BetterAuth: verification table ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS verification (
  id           TEXT PRIMARY KEY,
  identifier   TEXT NOT NULL,
  value        TEXT NOT NULL,
  "expiresAt"  TEXT NOT NULL,
  "createdAt"  TEXT NOT NULL,
  "updatedAt"  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_session_user_id ON session("userId");
CREATE INDEX IF NOT EXISTS idx_session_token ON session(token);
CREATE INDEX IF NOT EXISTS idx_account_user_id ON account("userId");
CREATE INDEX IF NOT EXISTS idx_account_provider ON account("providerId", "accountId");
CREATE INDEX IF NOT EXISTS idx_verification_identifier ON verification(identifier);

-- ─── Projects ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS projects (
  id             TEXT PRIMARY KEY,
  user_id        TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  name           TEXT NOT NULL,
  timeline_state TEXT NOT NULL DEFAULT '{"tracks":[]}',
  created_at     TEXT NOT NULL,
  updated_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_projects_user_created_at
  ON projects(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_projects_user_updated_at
  ON projects(user_id, updated_at DESC);

-- ─── Shared R2 objects (dedup store) ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS r2_objects (
  content_hash  TEXT PRIMARY KEY,
  r2_key        TEXT NOT NULL UNIQUE,
  file_size     INTEGER NOT NULL,
  mime_type     TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'ready')),
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);

-- ─── Per-user asset records ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS assets (
  id               TEXT PRIMARY KEY,
  user_id          TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  project_id       TEXT REFERENCES projects(id) ON DELETE SET NULL,
  content_hash     TEXT REFERENCES r2_objects(content_hash),
  r2_key           TEXT,
  filename         TEXT,
  file_size        INTEGER,
  mime_type        TEXT,
  media_type       TEXT,
  duration_seconds REAL,
  width            INTEGER,
  height           INTEGER,
  status           TEXT NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending', 'uploading', 'ready', 'failed')),
  public_url       TEXT,
  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL,
  deleted_at       TEXT
);

CREATE INDEX IF NOT EXISTS idx_assets_user_created_at
  ON assets(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_assets_user_project_created_at
  ON assets(user_id, project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_assets_status
  ON assets(user_id, status) WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_assets_content_hash
  ON assets(content_hash) WHERE deleted_at IS NULL;

-- ─── Export history per project ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS project_renders (
  id                  TEXT PRIMARY KEY,
  project_id          TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  user_id             TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
  render_job_id       TEXT NOT NULL,
  content_fingerprint TEXT NOT NULL,
  file_name           TEXT NOT NULL,
  codec               TEXT NOT NULL,
  width               INTEGER NOT NULL,
  height              INTEGER NOT NULL,
  duration_frames     INTEGER,
  crf                 INTEGER,
  resolution_preset   TEXT,
  r2_video_key        TEXT NOT NULL,
  r2_thumb_key        TEXT,
  created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_project_renders_project_created
  ON project_renders(project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_project_renders_fingerprint
  ON project_renders(project_id, user_id, content_fingerprint, created_at DESC);
