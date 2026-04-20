"""SQLite database: compile history, ratings, and techniques knowledge base."""
import json
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict

# Store DB in the user's home directory so it persists across updates
DB_DIR = Path.home() / ".prompt-forge"
DB_PATH = DB_DIR / "forge.db"

SEED_PATH = Path(__file__).parent.parent / "data" / "techniques_seed.json"


SCHEMA = """
CREATE TABLE IF NOT EXISTS compilations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_input   TEXT NOT NULL,
    domain      TEXT,
    level       INTEGER,
    xml_output  TEXT NOT NULL,
    corrections TEXT,
    techniques  TEXT,
    assumptions TEXT,
    rating      INTEGER,
    note        TEXT
);

CREATE TABLE IF NOT EXISTS techniques (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    when_to_use TEXT,
    snippet     TEXT,
    domains     TEXT,   -- JSON array of applicable domains
    source_url  TEXT,
    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    weight      REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS fetch_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fetched_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_url  TEXT,
    status      TEXT,
    n_added     INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_compilations_created ON compilations(created_at);
CREATE INDEX IF NOT EXISTS idx_techniques_name      ON techniques(name);
"""


def connect() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(force: bool = False) -> None:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    if force and DB_PATH.exists():
        DB_PATH.unlink()
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        _seed_techniques(conn)
    finally:
        conn.close()


def _seed_techniques(conn: sqlite3.Connection) -> None:
    if not SEED_PATH.exists():
        return
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM techniques")
    if cur.fetchone()[0] > 0:
        return  # already seeded
    with open(SEED_PATH, "r", encoding="utf-8") as f:
        seed = json.load(f)
    for t in seed:
        conn.execute(
            """INSERT OR IGNORE INTO techniques
               (name, description, when_to_use, snippet, domains, source_url)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (t["name"], t["description"], t.get("when_to_use", ""),
             t.get("snippet", ""), json.dumps(t.get("domains", [])),
             t.get("source_url", "seed")),
        )
    conn.commit()


def save_compilation(raw: str, domain: str, level: int, xml: str,
                     corrections: List[str], techniques: List[str],
                     assumptions: List[str]) -> int:
    conn = connect()
    try:
        cur = conn.execute(
            """INSERT INTO compilations
               (raw_input, domain, level, xml_output,
                corrections, techniques, assumptions)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (raw, domain, level, xml,
             json.dumps(corrections), json.dumps(techniques),
             json.dumps(assumptions)),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_techniques_for(domain: str) -> List[Dict]:
    """Return techniques applicable to a domain, ordered by weight."""
    conn = connect()
    try:
        cur = conn.execute("SELECT * FROM techniques ORDER BY weight DESC")
        rows = cur.fetchall()
        result = []
        for r in rows:
            domains = json.loads(r["domains"] or "[]")
            if not domains or domain in domains or "any" in domains:
                result.append(dict(r))
        return result
    finally:
        conn.close()


def add_technique(name: str, description: str, when_to_use: str = "",
                  snippet: str = "", domains: Optional[List[str]] = None,
                  source_url: str = "") -> bool:
    conn = connect()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO techniques
               (name, description, when_to_use, snippet, domains, source_url)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, description, when_to_use, snippet,
             json.dumps(domains or []), source_url),
        )
        changed = conn.total_changes
        conn.commit()
        return changed > 0
    finally:
        conn.close()


def log_fetch(url: str, status: str, n_added: int) -> None:
    conn = connect()
    try:
        conn.execute(
            "INSERT INTO fetch_log (source_url, status, n_added) VALUES (?, ?, ?)",
            (url, status, n_added),
        )
        conn.commit()
    finally:
        conn.close()


def rate_last_compilation(score: int, note: str = "") -> bool:
    conn = connect()
    try:
        cur = conn.execute("SELECT id FROM compilations ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if not row:
            return False
        conn.execute(
            "UPDATE compilations SET rating = ?, note = ? WHERE id = ?",
            (score, note, row["id"]),
        )
        # Bump/penalize technique weights based on score
        cur = conn.execute("SELECT techniques FROM compilations WHERE id = ?",
                           (row["id"],))
        techs_json = cur.fetchone()["techniques"]
        techs = json.loads(techs_json or "[]")
        delta = (score - 3) * 0.05  # -0.10 .. +0.10
        for t in techs:
            conn.execute(
                "UPDATE techniques SET weight = MAX(0.1, weight + ?) WHERE name = ?",
                (delta, t),
            )
        conn.commit()
        return True
    finally:
        conn.close()


def get_stats() -> Dict:
    conn = connect()
    try:
        stats = {}
        cur = conn.execute("SELECT COUNT(*) FROM compilations")
        stats["total_compilations"] = cur.fetchone()[0]
        cur = conn.execute("SELECT COUNT(*) FROM techniques")
        stats["total_techniques"] = cur.fetchone()[0]
        cur = conn.execute(
            "SELECT AVG(rating) FROM compilations WHERE rating IS NOT NULL"
        )
        avg = cur.fetchone()[0]
        stats["avg_rating"] = round(avg, 2) if avg else None
        cur = conn.execute(
            """SELECT domain, COUNT(*) as n FROM compilations
               GROUP BY domain ORDER BY n DESC"""
        )
        stats["by_domain"] = [dict(r) for r in cur.fetchall()]
        cur = conn.execute(
            """SELECT level, COUNT(*) as n FROM compilations
               GROUP BY level ORDER BY level"""
        )
        stats["by_level"] = [dict(r) for r in cur.fetchall()]
        cur = conn.execute(
            """SELECT name, weight FROM techniques
               ORDER BY weight DESC LIMIT 10"""
        )
        stats["top_techniques"] = [dict(r) for r in cur.fetchall()]
        cur = conn.execute(
            """SELECT COUNT(*) FROM fetch_log WHERE status = 'ok'"""
        )
        stats["successful_fetches"] = cur.fetchone()[0]
        return stats
    finally:
        conn.close()
