# -*- coding: utf-8 -*-
"""SQLite: foydalanuvchilar, natijalar/reyting va endi SAVOLLAR bazasi (admin kiritadi)."""

import json
import sqlite3
from contextlib import contextmanager

DB_PATH = "tarix_bot.db"


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT,
                username TEXT,
                total_correct INTEGER DEFAULT 0,
                total_wrong INTEGER DEFAULT 0,
                total_tests INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                mode TEXT,
                class_num INTEGER,
                subject TEXT,
                topic TEXT,
                correct INTEGER,
                wrong INTEGER,
                total INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_num INTEGER NOT NULL,
                subject TEXT NOT NULL,
                topic TEXT NOT NULL,
                question TEXT NOT NULL,
                options TEXT NOT NULL,       -- JSON ro'yxat sifatida saqlanadi
                correct TEXT NOT NULL,       -- to'g'ri javob matni
                added_by INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ---------- Foydalanuvchilar ----------
def register_user(user_id: int, full_name: str, username: str | None):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO users (user_id, full_name, username)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET full_name=excluded.full_name, username=excluded.username""",
            (user_id, full_name, username),
        )
        conn.commit()


def save_attempt(user_id: int, mode: str, class_num, subject, topic, correct: int, wrong: int, total: int):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO attempts (user_id, mode, class_num, subject, topic, correct, wrong, total)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, mode, class_num, subject, topic, correct, wrong, total),
        )
        conn.execute(
            """UPDATE users SET total_correct = total_correct + ?,
                                 total_wrong = total_wrong + ?,
                                 total_tests = total_tests + 1
               WHERE user_id = ?""",
            (correct, wrong, user_id),
        )
        conn.commit()


def get_user_stats(user_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_top(limit: int = 3):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM users
               WHERE total_tests > 0
               ORDER BY total_correct DESC, total_wrong ASC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_user_rank(user_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT user_id FROM users
               WHERE total_tests > 0
               ORDER BY total_correct DESC, total_wrong ASC"""
        ).fetchall()
        for idx, r in enumerate(rows, start=1):
            if r["user_id"] == user_id:
                return idx, len(rows)
        return None, len(rows)


# ---------- Savollar (admin kiritadi) ----------
def add_question(class_num: int, subject: str, topic: str, question: str,
                  options: list[str], correct: str, added_by: int) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO questions (class_num, subject, topic, question, options, correct, added_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (class_num, subject, topic, question, json.dumps(options, ensure_ascii=False), correct, added_by),
        )
        conn.commit()
        return cur.lastrowid


def delete_last_question(added_by: int) -> bool:
    """Shu admin qo'shgan eng oxirgi savolni o'chiradi (bekor qilish uchun)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM questions WHERE added_by = ? ORDER BY id DESC LIMIT 1", (added_by,)
        ).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM questions WHERE id = ?", (row["id"],))
        conn.commit()
        return True


def _row_to_question(row) -> dict:
    return {
        "q": row["question"],
        "options": json.loads(row["options"]),
        "correct": row["correct"],
    }


def get_classes() -> list[int]:
    with get_conn() as conn:
        rows = conn.execute("SELECT DISTINCT class_num FROM questions ORDER BY class_num").fetchall()
        return [r["class_num"] for r in rows]


def get_subjects(class_num: int) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT subject FROM questions WHERE class_num = ? ORDER BY subject", (class_num,)
        ).fetchall()
        return [r["subject"] for r in rows]


def get_topics(class_num: int, subject: str) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT topic FROM questions WHERE class_num = ? AND subject = ? ORDER BY topic",
            (class_num, subject),
        ).fetchall()
        return [r["topic"] for r in rows]


def get_questions_by_class(class_num: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM questions WHERE class_num = ?", (class_num,)).fetchall()
        return [_row_to_question(r) for r in rows]


def get_questions_by_subject(class_num: int, subject: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM questions WHERE class_num = ? AND subject = ?", (class_num, subject)
        ).fetchall()
        return [_row_to_question(r) for r in rows]


def get_questions_by_topic(class_num: int, subject: str, topic: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM questions WHERE class_num = ? AND subject = ? AND topic = ?",
            (class_num, subject, topic),
        ).fetchall()
        return [_row_to_question(r) for r in rows]


def get_all_questions() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM questions").fetchall()
        return [_row_to_question(r) for r in rows]


def get_season_top(limit: int = 10) -> list[dict]:
    """Joriy oy (kalendar oyi) bo'yicha eng ko'p to'g'ri javob bergan foydalanuvchilar."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT u.user_id, u.full_name,
                      COALESCE(SUM(a.correct), 0) AS season_correct,
                      COALESCE(SUM(a.wrong), 0) AS season_wrong,
                      COUNT(a.id) AS season_tests
               FROM attempts a
               JOIN users u ON u.user_id = a.user_id
               WHERE strftime('%Y-%m', a.created_at) = strftime('%Y-%m', 'now')
               GROUP BY a.user_id
               HAVING season_tests > 0
               ORDER BY season_correct DESC, season_wrong ASC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_season_rank(user_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT a.user_id, COALESCE(SUM(a.correct), 0) AS season_correct,
                      COALESCE(SUM(a.wrong), 0) AS season_wrong
               FROM attempts a
               WHERE strftime('%Y-%m', a.created_at) = strftime('%Y-%m', 'now')
               GROUP BY a.user_id
               ORDER BY season_correct DESC, season_wrong ASC"""
        ).fetchall()
        for idx, r in enumerate(rows, start=1):
            if r["user_id"] == user_id:
                return idx, len(rows)
        return None, len(rows)


def get_subject_breakdown(user_id: int) -> list[dict]:
    """Foydalanuvchining har bir fan bo'yicha statistikasi (tahlil uchun)."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT subject,
                      SUM(correct) AS correct, SUM(wrong) AS wrong, COUNT(*) AS tests
               FROM attempts
               WHERE user_id = ? AND subject IS NOT NULL
               GROUP BY subject
               ORDER BY correct DESC""",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_best_attempt_percent(user_id: int) -> float:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT MAX(CAST(correct AS FLOAT) / total * 100) AS best
               FROM attempts WHERE user_id = ? AND total > 0""",
            (user_id,),
        ).fetchone()
        return row["best"] or 0


def get_question_count(class_num=None, subject=None, topic=None) -> int:
    query = "SELECT COUNT(*) as cnt FROM questions WHERE 1=1"
    params = []
    if class_num is not None:
        query += " AND class_num = ?"
        params.append(class_num)
    if subject is not None:
        query += " AND subject = ?"
        params.append(subject)
    if topic is not None:
        query += " AND topic = ?"
        params.append(topic)
    with get_conn() as conn:
        row = conn.execute(query, params).fetchone()
        return row["cnt"]
