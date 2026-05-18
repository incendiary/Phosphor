import sqlite3


class PhosphorDB:
    """Lightweight SQLite store for post-run result analysis."""

    def __init__(self, path="phosphor.db"):
        self._conn = sqlite3.connect(path)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id      TEXT    NOT NULL,
                mode        TEXT    NOT NULL,
                username    TEXT,
                environment TEXT,
                code        TEXT    NOT NULL,
                response    TEXT    NOT NULL,
                recorded_at TEXT    NOT NULL DEFAULT (datetime('now'))
            )
            """)
        self._conn.commit()

    def record(self, run_id, mode, code, response, username=None, environment=None):
        self._conn.execute(
            """
            INSERT INTO results (run_id, mode, code, response, username, environment)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, mode, str(code), response, username, environment),
        )
        self._conn.commit()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
