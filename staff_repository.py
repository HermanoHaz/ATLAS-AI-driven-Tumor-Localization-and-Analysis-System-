"""
ATLAS - staff profile, profile photo and personal tasks  (databases/staff_repository.py)

Works on your existing  staff  table (found by username) and creates what is missing the
first time it runs:
    * staff.profile_picture      BYTEA column  (the photo itself, shrunk to 256 x 256)
    * personal_tasks             new table     (the tasks from the Settings page)

All SQL uses placeholders (%s), so user input can never inject SQL.
"""
from datetime import date, timedelta

from databases.db_connection import db_cursor, pg

_schema_ready = False


def ensure_schema():
    """Add the photo column and the tasks table if they are not there yet (safe to repeat)."""
    global _schema_ready
    if _schema_ready:
        return
    with db_cursor() as cur:
        cur.execute("ALTER TABLE staff ADD COLUMN IF NOT EXISTS profile_picture BYTEA")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS personal_tasks (
                id           SERIAL PRIMARY KEY,
                username     VARCHAR(100) NOT NULL,
                title        VARCHAR(160) NOT NULL,
                description  TEXT,
                due_date     DATE NOT NULL,
                due_time     TIME,
                note         TEXT,
                is_done      BOOLEAN NOT NULL DEFAULT FALSE,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS personal_tasks_user_date_idx "
                    "ON personal_tasks (username, due_date)")
    _schema_ready = True


# ----------------------------------------------------------------------------
# Profile
# ----------------------------------------------------------------------------
def _staff_identifier(row: dict) -> str:
    for key in ("staff_id", "staff_code", "staff_no", "id"):
        value = row.get(key)
        if value:
            return value if isinstance(value, str) else f"ATL-{int(value):04d}" if str(value).isdigit() else str(value)
    return ""


def get_profile(username: str) -> dict:
    with db_cursor(commit=False, dict_rows=True) as cur:
        cur.execute("SELECT * FROM staff WHERE username = %s", (username,))
        row = cur.fetchone()
    if row is None:
        raise LookupError("This account was not found in the database.")
    first, last = row.get("first_name") or "", row.get("last_name") or ""
    return {
        "full_name": f"{first} {last}".strip(),
        "email": row.get("email") or "",
        "phone": row.get("contact_no") or "",
        "department": row.get("department") or "",
        "role": row.get("staff_role") or "",
        "staff_id": _staff_identifier(row),
    }


def update_profile(username: str, full_name: str, email: str, phone: str, department: str):
    """Save the editable profile fields. The full name is split into first / last name."""
    parts = full_name.split()
    first = " ".join(parts[:-1]) if len(parts) > 1 else (parts[0] if parts else "")
    last = parts[-1] if len(parts) > 1 else ""
    pgmod = pg()
    try:
        with db_cursor() as cur:
            cur.execute(
                """UPDATE staff
                   SET first_name = %s, last_name = %s, email = %s, contact_no = %s, department = %s
                   WHERE username = %s""",
                (first, last, email, phone or None, department or None, username))
            if cur.rowcount == 0:
                raise LookupError("This account was not found in the database.")
    except pgmod.errors.UniqueViolation as e:
        raise ValueError("That email address is already used by another account.") from e


# ----------------------------------------------------------------------------
# Profile photo
# ----------------------------------------------------------------------------
def get_avatar(username: str):
    """The stored photo as bytes (PNG), or None."""
    with db_cursor(commit=False, dict_rows=True) as cur:
        cur.execute("SELECT profile_picture FROM staff WHERE username = %s", (username,))
        row = cur.fetchone()
    data = row["profile_picture"] if row else None
    return bytes(data) if data else None


def set_avatar(username: str, data):
    """Save the photo (bytes), or remove it (None)."""
    value = pg().Binary(data) if data else None
    with db_cursor() as cur:
        cur.execute("UPDATE staff SET profile_picture = %s WHERE username = %s", (value, username))


# ----------------------------------------------------------------------------
# Personal tasks
# ----------------------------------------------------------------------------
def add_task(username: str, title: str, description: str, due_date: date, due_time, note: str) -> int:
    with db_cursor() as cur:
        cur.execute(
            """INSERT INTO personal_tasks (username, title, description, due_date, due_time, note)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
            (username, title, description or None, due_date, due_time, note or None))
        return cur.fetchone()[0]


def dashboard_tasks(username: str, days: int = 30):
    """
    Returns (today_rows, upcoming_rows) as (title, subtitle, right_text) tuples,
    ready for DashboardPage.set_today_tasks() and set_upcoming().
    """
    today = date.today()
    with db_cursor(commit=False, dict_rows=True) as cur:
        cur.execute(
            """SELECT title, description, note, due_date, due_time
               FROM personal_tasks
               WHERE username = %s AND is_done = FALSE AND due_date BETWEEN %s AND %s
               ORDER BY due_date, due_time NULLS LAST, id""",
            (username, today, today + timedelta(days=days)))
        rows = cur.fetchall()

    today_rows, upcoming_rows = [], []
    for r in rows:
        sub = (r["note"] or r["description"] or "").strip().replace("\n", " ")
        sub = sub[:48] + "..." if len(sub) > 48 else sub
        clock = r["due_time"].strftime("%H:%M") if r["due_time"] else ""
        if r["due_date"] == today:
            today_rows.append((r["title"], sub, clock))
        else:
            when = r["due_date"].strftime("%d %b") + (f" {clock}" if clock else "")
            upcoming_rows.append((r["title"], sub, when))
    return today_rows, upcoming_rows