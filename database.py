"""
数据库引擎
- 默认：SQLite（本地 + Streamlit Cloud 都可用）
- 可选：TiDB MySQL（设置 TIDB_URL 后自动切换）

用法：
    from database import db
    rows = db.fetchall('SELECT ...', params)
    row  = db.fetchone('SELECT ...', params)
    last_id = db.insert('INSERT ...', params)
"""
import os
import sqlite3
import re
import streamlit as st
from datetime import date, timedelta

# ========== 路径 ==========
DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_SQLITE = os.path.join(DB_DIR, 'study.db')

HAS_MYSQL = False
try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    pass


# ========== SQL 转换 ==========
def _sqlite_to_mysql(sql):
    sql = sql.replace('?', '%s')
    sql = sql.replace('AUTOINCREMENT', 'AUTO_INCREMENT')
    return sql


# ========== SQLite 实现 ==========
class _SQLiteWrapper:
    def __init__(self):
        self.conn = sqlite3.connect(DB_SQLITE, check_same_thread=False)
        self.conn.execute('PRAGMA encoding="UTF-8"')
        self.cursor = self.conn.cursor()

    def execute(self, sql, params=None):
        if params is None:
            self.cursor.execute(sql)
        else:
            self.cursor.execute(sql, params)
        return self

    def fetchone(self): return self.cursor.fetchone()
    def fetchall(self): return self.cursor.fetchall()
    @property
    def lastrowid(self): return self.cursor.lastrowid
    def commit(self): self.conn.commit()
    def close(self):
        try: self.cursor.close()
        except: pass
        try: self.conn.close()
        except: pass


# ========== MySQL/TiDB 实现 ==========
class _MySQLWrapper:
    def __init__(self, config):
        self.config = config
        self.conn = None
        self.cursor = None
        self._connect()

    def _connect(self):
        self.conn = mysql.connector.connect(
            host=self.config['host'], port=self.config['port'],
            user=self.config['user'], password=self.config['password'],
            database=self.config['database'], use_pure=True, connection_timeout=15,
        )
        self.cursor = self.conn.cursor()

    def execute(self, sql, params=None):
        msql = _sqlite_to_mysql(sql)
        if params is None:
            self.cursor.execute(msql)
        else:
            self.cursor.execute(msql, params)
        return self

    def fetchone(self): return self.cursor.fetchone()
    def fetchall(self): return self.cursor.fetchall()
    @property
    def lastrowid(self): return self.cursor.lastrowid
    def commit(self):
        try: self.conn.commit()
        except: pass
    def close(self):
        try: self.cursor.close()
        except: pass
        try: self.conn.close()
        except: pass


# ========== 数据库引擎 ==========
class Database:
    """SQLite（默认）/ TiDB MySQL（可选）"""

    def __init__(self):
        self.mode = 'sqlite'
        self._wrapper = None
        self._mysql_config = None
        self._try_tidb()

    def _try_tidb(self):
        """尝试连接 TiDB，失败则静默回退 SQLite"""
        tidb_url = st.secrets.get('TIDB_URL', '')
        if not tidb_url or not HAS_MYSQL:
            return
        m = re.match(r'mysql://([^:]+):([^@]+)@([^:]+):(\d+)/(\w+)', tidb_url.strip())
        if not m:
            return
        cfg = {
            'host': m.group(3), 'port': int(m.group(4)),
            'user': m.group(1), 'password': m.group(2),
            'database': m.group(5),
        }
        try:
            # 测试连接
            test = mysql.connector.connect(
                host=cfg['host'], port=cfg['port'],
                user=cfg['user'], password=cfg['password'],
                database=cfg['database'], use_pure=True, connection_timeout=10,
            )
            test.close()
            self.mode = 'mysql'
            self._mysql_config = cfg
        except Exception:
            pass  # 连不上就继续用 SQLite

    def _get_wrapper(self):
        if self.mode == 'mysql':
            if self._wrapper is None:
                self._wrapper = _MySQLWrapper(self._mysql_config)
        else:
            if self._wrapper is None:
                self._wrapper = _SQLiteWrapper()
        return self._wrapper

    def execute(self, sql, params=None):
        return self._get_wrapper().execute(sql, params)

    def fetchall(self, sql, params=None):
        return self._get_wrapper().execute(sql, params).fetchall()

    def fetchone(self, sql, params=None):
        return self._get_wrapper().execute(sql, params).fetchone()

    def insert(self, sql, params=None):
        w = self._get_wrapper()
        w.execute(sql, params)
        w.commit()
        return w.lastrowid

    def commit(self):
        if self._wrapper:
            self._wrapper.commit()

    def close(self):
        if self._wrapper:
            self._wrapper.close()
            self._wrapper = None

    def set_sqlite(self):
        """强制使用 SQLite（当 TiDB 连不上时自动回退）"""
        self.close()
        self.mode = 'sqlite'
        self._mysql_config = None


# ========== 全局单例 ==========
db = Database()


# ========== 建表 ==========
def init_tables():
    """初始化所有数据表"""
    db.execute('''
        CREATE TABLE IF NOT EXISTS wrong_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            child_name TEXT, subject TEXT,
            question TEXT, wrong_reason TEXT, ai_analysis TEXT, image_data TEXT,
            created_date TEXT, is_mastered INTEGER DEFAULT 0, review_count INTEGER DEFAULT 0
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            child_name TEXT, checkin_date TEXT, note TEXT
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS daily_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_date TEXT, content_type TEXT, content TEXT
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS review_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER, child_name TEXT, subject TEXT,
            review_date TEXT, stage INTEGER, original_date TEXT,
            completed INTEGER DEFAULT 0
        )
    ''')
    db.commit()


# ========== 艾宾浩斯复习计划 ==========
EBBINGHAUS_INTERVALS = [1, 3, 7, 14, 30]

def create_review_schedule(question_id, child_name, subject, created_date):
    base = date.fromisoformat(created_date)
    for stage, days in enumerate(EBBINGHAUS_INTERVALS, 1):
        rd = (base + timedelta(days=days)).isoformat()
        db.execute(
            'INSERT INTO review_schedule(question_id, child_name, subject, review_date, stage, original_date) VALUES(?,?,?,?,?,?)',
            (question_id, child_name, subject, rd, stage, created_date)
        )
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
    row = db.fetchone(
        'SELECT COUNT(*) FROM review_schedule WHERE child_name=? AND review_date=? AND completed=0',
        (child_name, today)
    )
    return row[0] if row else 0

def mark_review_done(review_id):
    db.execute('UPDATE review_schedule SET completed=1 WHERE id=?', (review_id,))
    db.commit()
