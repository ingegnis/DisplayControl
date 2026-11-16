"""SQLite transactions with deterministic close (including on Windows)."""
import sqlite3
from contextlib import contextmanager


@contextmanager
def database(path):
    conn = sqlite3.connect(str(path), timeout=10)
    try:
        conn.execute('PRAGMA journal_mode=WAL')
        with conn:
            yield conn
    finally:
        conn.close()
