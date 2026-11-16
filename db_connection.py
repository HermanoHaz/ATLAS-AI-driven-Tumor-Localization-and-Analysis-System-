"""
ATLAS - PostgreSQL connection helper  (databases/db_connection.py)

Reads the connection settings from a  .env  file in the project root
(or from normal environment variables). See  .env.example .

Usage:
    from databases.db_connection import db_cursor

    with db_cursor() as cur:
        cur.execute("SELECT 1")
"""
import os
from contextlib import contextmanager

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class DatabaseUnavailable(Exception):
    """PostgreSQL can't be used (driver missing, server off, wrong password, no tables...)."""


def load_env(path: str = None):
    """Tiny .env reader (KEY=VALUE per line) - no extra package needed."""
    path = path or os.path.join(ROOT_DIR, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_config() -> dict:
    load_env()
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", "5432")),
        "dbname": os.environ.get("DB_NAME", "atlas"),
        "user": os.environ.get("DB_USER", "postgres"),
        "password": os.environ.get("DB_PASSWORD", ""),
    }


def pg():
    """Return the psycopg2 module, or raise a friendly error if it isn't installed."""
    try:
        import psycopg2
        import psycopg2.errors
        import psycopg2.extras
        return psycopg2
    except ImportError as e:
        raise DatabaseUnavailable(
            "The PostgreSQL driver is not installed.\n"
            "Run:  pip install psycopg2-binary") from e


def get_connection():
    psycopg2 = pg()
    cfg = get_config()
    try:
        return psycopg2.connect(connect_timeout=5, **cfg)
    except psycopg2.OperationalError as e:
        raise DatabaseUnavailable(
            f"Cannot connect to PostgreSQL at {cfg['host']}:{cfg['port']} "
            f"(database '{cfg['dbname']}', user '{cfg['user']}').\n{str(e).strip()}") from e


@contextmanager
def db_cursor(commit: bool = True, dict_rows: bool = False):
    """Open a connection + cursor, commit on success, roll back on error, always close."""
    psycopg2 = pg()
    conn = get_connection()
    try:
        factory = psycopg2.extras.RealDictCursor if dict_rows else None
        cur = conn.cursor(cursor_factory=factory)
        try:
            yield cur
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
    finally:
        conn.close()


def test_connection():
    """Returns (ok: bool, message: str)."""
    try:
        with db_cursor(commit=False) as cur:
            cur.execute("SELECT version()")
            return True, cur.fetchone()[0]
    except DatabaseUnavailable as e:
        return False, str(e)


# ----------------------------------------------------------------------------
# Run this file directly to check the connection and print the database
# STRUCTURE (tables, columns, keys - never any row data):
#       python databases\db_connection.py
# ----------------------------------------------------------------------------
def describe_database():
    cfg = get_config()
    print(f"Database '{cfg['dbname']}' on {cfg['host']}:{cfg['port']} (user '{cfg['user']}')\n")
    with db_cursor(commit=False) as cur:
        cur.execute("""
            SELECT table_name, column_name, data_type, character_maximum_length,
                   is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
        """)
        columns = cur.fetchall()
        cur.execute("""
            SELECT conrelid::regclass::text, contype, pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE connamespace = 'public'::regnamespace
            ORDER BY 1, 2
        """)
        constraints = cur.fetchall()
        cur.execute("SELECT relname, n_live_tup FROM pg_stat_user_tables")
        counts = dict(cur.fetchall())

    kinds = {"p": "PRIMARY KEY", "f": "FOREIGN KEY", "u": "UNIQUE", "c": "CHECK"}
    for t in sorted({c[0] for c in columns}):
        print(f"TABLE {t}   (~{counts.get(t, 0)} rows)")
        for _, name, dtype, length, nullable, default in (c for c in columns if c[0] == t):
            line = f"  - {name}  {dtype}" + (f"({length})" if length else "")
            line += "  NOT NULL" if nullable == "NO" else ""
            line += f"  DEFAULT {default}" if default else ""
            print(line)
        for table, kind, definition in constraints:
            if table.strip('"') == t:
                print(f"  * {kinds.get(kind, kind)}: {definition}")
        print()


if __name__ == "__main__":
    import sys
    try:
        describe_database()
    except DatabaseUnavailable as e:
        print("FAILED:\n" + str(e))
        sys.exit(1)