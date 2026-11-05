PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'admin'))
);
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL CHECK(length(title) BETWEEN 3 AND 120),
    description TEXT NOT NULL CHECK(length(description) BETWEEN 1 AND 2000),
    priority TEXT NOT NULL CHECK(priority IN ('low', 'normal', 'high')),
    status TEXT NOT NULL DEFAULT 'new' CHECK(status IN ('new', 'work', 'done')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS tickets_owner ON tickets(owner_id);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    csrf TEXT NOT NULL,
    expires REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL,
    ticket_id INTEGER REFERENCES tickets(id),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
PRAGMA user_version = 1;
