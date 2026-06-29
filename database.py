"""
数据库引擎（当前使用 SQLite）
- SQLite：本地 + Streamlit Cloud 都可用，简单可靠

用法：
    from database import db
    rows = db.fetchall('SELECT ...', params)
    row  = db.fetchone('SELECT ...', params)
    last_id = db.insert('INSERT ...', params)
"""
import os
import sqlite3
from datetime import date, timedelta

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, 'study.db')


def _get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute('PRAGMA encoding="UTF-8"')
    return conn


class Database:
    """SQLite 数据库"""
    def __init__(self):
        self.conn = None

    def _ensure(self):
        if self.conn is None:
            self.conn = _get_conn()

    def execute(self, sql, params=None):
        self._ensure()
        if params is None:
            self.conn.execute(sql)
        else:
            self.conn.execute(sql, params)
        return self

    def fetchall(self, sql, params=None):
        self._ensure()
        if params is None:
            return self.conn.execute(sql).fetchall()
        return self.conn.execute(sql, params).fetchall()

    def fetchone(self, sql, params=None):
        self._ensure()
        if params is None:
            return self.conn.execute(sql).fetchone()
        return self.conn.execute(sql, params).fetchone()

    def insert(self, sql, params=None):
        self._ensure()
        cur = self.conn.execute(sql, params) if params else self.conn.execute(sql)
        self.conn.commit()
        return cur.lastrowid

    def commit(self):
        if self.conn:
            self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None


db = Database()


def init_tables():
    db.execute('CREATE TABLE IF NOT EXISTS wrong_questions ('
               'id INTEGER PRIMARY KEY AUTOINCREMENT, child_name TEXT, subject TEXT, '
               'question TEXT, wrong_reason TEXT, ai_analysis TEXT, image_data TEXT, '
               'created_date TEXT, is_mastered INTEGER DEFAULT 0, review_count INTEGER DEFAULT 0)')
    db.execute('CREATE TABLE IF NOT EXISTS checkins ('
               'id INTEGER PRIMARY KEY AUTOINCREMENT, child_name TEXT, checkin_date TEXT, note TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS daily_content ('
               'id INTEGER PRIMARY KEY AUTOINCREMENT, content_date TEXT, content_type TEXT, content TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS review_schedule ('
               'id INTEGER PRIMARY KEY AUTOINCREMENT, question_id INTEGER, child_name TEXT, '
               'subject TEXT, review_date TEXT, stage INTEGER, original_date TEXT, completed INTEGER DEFAULT 0)')
    db.commit()


EBBINGHAUS_INTERVALS = [1, 3, 7, 14, 30]


def create_review_schedule(question_id, child_name, subject, created_date):
    base = date.fromisoformat(created_date)
    for stage, days in enumerate(EBBINGHAUS_INTERVALS, 1):
        rd = (base + timedelta(days=days)).isoformat()
        db.execute('INSERT INTO review_schedule VALUES(NULL,?,?,?,?,?,?,?)',
                   (question_id, child_name, subject, rd, stage, created_date, 0))
    db.commit()


def get_today_reviews(child_name):
    today = str(date.today())
    return db.fetchall(
        'SELECT rs.id, rs.question_id, rs.subject, rs.stage, rs.original_date, '
        'wq.question, wq.wrong_reason, wq.ai_analysis, wq.image_data '
        'FROM review_schedule rs JOIN wrong_questions wq ON rs.question_id = wq.id '
        'WHERE rs.child_name=? AND rs.review_date=? AND rs.completed=0 '
        'ORDER BY rs.stage, rs.original_date',
        (child_name, today)
    )


def get_today_review_count(child_name):
    today = str(date.today())
    row = db.fetchone('SELECT COUNT(*) FROM review_schedule WHERE child_name=? AND review_date=? AND completed=0',
                      (child_name, today))
    return row[0] if row else 0


def mark_review_done(review_id):
    db.execute('UPDATE review_schedule SET completed=1 WHERE id=?', (review_id,))
    db.commit()
