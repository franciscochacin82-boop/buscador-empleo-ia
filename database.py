import re
import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "jobs.db"

_HTML_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_html(text: str) -> str:
    if not text:
        return text
    text = _HTML_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _clean_existing_html():
    """One-time migration: strip HTML from any descriptions already in the DB."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, description FROM jobs WHERE description LIKE '%<%'"
        ).fetchall()
        for row in rows:
            conn.execute(
                "UPDATE jobs SET description=? WHERE id=?",
                (_strip_html(row["description"]), row["id"]),
            )


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY,
                name TEXT,
                email TEXT,
                phone TEXT,
                location TEXT,
                linkedin TEXT,
                summary TEXT,
                skills TEXT,
                experience TEXT,
                education TEXT,
                languages TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                external_id TEXT,
                title TEXT NOT NULL,
                company TEXT,
                location TEXT,
                job_type TEXT,
                salary TEXT,
                description TEXT,
                url TEXT,
                tags TEXT,
                found_at TEXT,
                UNIQUE(source, external_id)
            );

            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER REFERENCES jobs(id),
                status TEXT DEFAULT 'saved',
                cover_letter TEXT,
                notes TEXT,
                applied_at TEXT,
                updated_at TEXT
            );
        """)
    _clean_existing_html()


# --- Profile ---

def save_profile(data: dict):
    with get_conn() as conn:
        existing = conn.execute("SELECT id FROM profile LIMIT 1").fetchone()
        data["updated_at"] = datetime.now().isoformat()
        if existing:
            cols = ", ".join(f"{k}=?" for k in data)
            conn.execute(f"UPDATE profile SET {cols} WHERE id=?", (*data.values(), existing["id"]))
        else:
            cols = ", ".join(data.keys())
            placeholders = ", ".join("?" * len(data))
            conn.execute(f"INSERT INTO profile ({cols}) VALUES ({placeholders})", tuple(data.values()))


def get_profile() -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM profile LIMIT 1").fetchone()
        return dict(row) if row else None


# --- Jobs ---

def upsert_jobs(jobs: list[dict]) -> int:
    inserted = 0
    with get_conn() as conn:
        for job in jobs:
            job.setdefault("found_at", datetime.now().isoformat())
            if isinstance(job.get("tags"), list):
                job["tags"] = json.dumps(job["tags"])
            # Always store clean text, no HTML
            if job.get("description"):
                job["description"] = _strip_html(job["description"])
            try:
                conn.execute(
                    """INSERT INTO jobs (source, external_id, title, company, location,
                       job_type, salary, description, url, tags, found_at)
                       VALUES (:source, :external_id, :title, :company, :location,
                               :job_type, :salary, :description, :url, :tags, :found_at)""",
                    job,
                )
                inserted += 1
            except sqlite3.IntegrityError:
                pass
    return inserted


def get_jobs(search: str = "", exclude: str = "", source: str = "", only_unsaved: bool = False) -> list[dict]:
    with get_conn() as conn:
        query = """
            SELECT j.*, a.id as app_id, a.status, a.applied_at
            FROM jobs j
            LEFT JOIN applications a ON a.job_id = j.id
            WHERE 1=1
        """
        params = []
        if search:
            words = [w.strip() for w in search.replace(",", " ").split() if len(w.strip()) > 2]
            if words:
                if len(words) == 1:
                    # Single word: match in title, tags, or description
                    w = words[0]
                    query += " AND (j.title LIKE ? OR j.tags LIKE ? OR j.description LIKE ?)"
                    params += [f"%{w}%", f"%{w}%", f"%{w}%"]
                else:
                    # Multiple words: EVERY word must appear somewhere across
                    # title + tags + description (cross-field AND).
                    # This prevents "video" in tags matching "video editar" when
                    # "editar" appears nowhere in that job.
                    per_word = " AND ".join(
                        "(j.title LIKE ? OR COALESCE(j.tags,'') LIKE ? OR COALESCE(j.description,'') LIKE ?)"
                        for _ in words
                    )
                    query += f" AND ({per_word})"
                    for w in words:
                        params += [f"%{w}%", f"%{w}%", f"%{w}%"]

        if exclude:
            ex_words = [w.strip() for w in exclude.replace(",", " ").split() if len(w.strip()) > 2]
            for w in ex_words:
                query += " AND j.title NOT LIKE ? AND j.tags NOT LIKE ?"
                params += [f"%{w}%", f"%{w}%"]
        if source:
            query += " AND j.source = ?"
            params.append(source)
        if only_unsaved:
            query += " AND a.id IS NULL"
        query += " ORDER BY j.found_at DESC"
        rows = conn.execute(query, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("tags") and isinstance(d["tags"], str):
                try:
                    d["tags"] = json.loads(d["tags"])
                except Exception:
                    d["tags"] = []
            result.append(d)
        return result


def get_job(job_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None


# --- Applications ---

def save_application(job_id: int, status: str, cover_letter: str = "", notes: str = "") -> int:
    with get_conn() as conn:
        existing = conn.execute("SELECT id FROM applications WHERE job_id=?", (job_id,)).fetchone()
        now = datetime.now().isoformat()
        if existing:
            conn.execute(
                "UPDATE applications SET status=?, cover_letter=?, notes=?, updated_at=? WHERE id=?",
                (status, cover_letter, notes, now, existing["id"]),
            )
            return existing["id"]
        else:
            applied_at = now if status == "applied" else None
            cur = conn.execute(
                "INSERT INTO applications (job_id, status, cover_letter, notes, applied_at, updated_at) VALUES (?,?,?,?,?,?)",
                (job_id, status, cover_letter, notes, applied_at, now),
            )
            return cur.lastrowid


def get_application(job_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM applications WHERE job_id=?", (job_id,)).fetchone()
        return dict(row) if row else None


def get_applications_summary() -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM applications GROUP BY status"
        ).fetchall()
        return {r["status"]: r["cnt"] for r in rows}


def delete_job(job_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM applications WHERE job_id=?", (job_id,))
        conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))
