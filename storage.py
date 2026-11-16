"""SQLite transactions with deterministic close (including on Windows)."""
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

_hooks = {}
_locks = {}
_registry_lock = threading.Lock()


def exclusive_file_lock(path):
    import os
    handle = Path(path).open('a+b')
    try:
        if handle.seek(0, 2) == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise RuntimeError('Cartella dati già utilizzata da un altro processo, o non accessibile.')
    return handle


def transaction_hooks(path, before_commit, after_commit):
    key = str(Path(path).resolve())
    with _registry_lock:
        _hooks[key] = (before_commit, after_commit)


def database_lock(path):
    key = str(Path(path).resolve())
    with _registry_lock:
        return _locks.setdefault(key, threading.RLock())


@contextmanager
def database(path):
    key = str(Path(path).resolve())
    with database_lock(path):
        conn = sqlite3.connect(str(path), timeout=10)
        try:
            conn.execute('PRAGMA journal_mode=WAL')
            changed = False
            with conn:
                yield conn
                changed = bool(conn.total_changes)
                hooks = _hooks.get(key)
                if changed and hooks:
                    hooks[0]()
            if changed and hooks:
                hooks[1]()
        finally:
            conn.close()
