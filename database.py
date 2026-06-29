"""
双模式数据库引擎
- 本地开发：SQLite（无需配置）
- 云端生产：TiDB MySQL（设置 TIDB_URL 后自动切换）

用法：
    from database import db
    db.execute('SELECT ...', params)
    rows = db.fetchall('SELECT ...', params)
    row  = db.fetchone('SELECT ...', params)
    db.commit()
    last_id = db.insert('INSERT ...', params)
"""
import os
import sqlite3
import re
import time
import streamlit as st
from datetime import date, timedelta

try:
    import pymysql
    import pymysql.cursors
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False


# ========== 路径 ==========
DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_SQLITE = os.path.join(DB_DIR, 'study.db')


# ========== SQL 转换 ==========
def _sqlite_to_mysql(sql):
    """将 SQLite 风格的 SQL 转为 MySQL/TiDB 兼容"""
    sql = sql.replace('?', '%s')
    sql = sql.replace('AUTOINCREMENT', 'AUTO_INCREMENT')
    return sql


# ========== 连接管理 ==========
class _MySQLWrapper:
    """统一包装 pymysql，暴露出类似 sqlite3 的 API"""
    def __init__(self, config):
        self.config = config
        self.conn = None
        self.cursor = None
        self._connect()

    def _connect(self):
        self.conn = pymysql.connect(
            host=self.config['host'],
            port=self.config['port'],
            user=self.config['user'],
            password=self.config['password'],
            database=self.config['database'],
            ssl={'ssl': {}},
            charset='utf8mb4',
            cursorclass=pymysql.cursors.Cursor,
            autocommit=False,
            connect_timeout=30,
            read_timeout=60,
            write_timeout=60,
        )
        self.cursor = self.conn.cursor()

    def execute(self, sql, params=None):
        msql = _sqlite_to_mysql(sql)
        for attempt in range(2):
            try:
                if params is None:
                    self.cursor.execute(msql)
                else:
                    self.cursor.execute(msql, params)
                return self
            except Exception as e:
                if attempt == 0 and self._is_connection_error(e):
                    # 连接断开，重连后重试一次
                    self._reconnect()
                    continue
                raise
        return self

    def _is_connection_error(self, e):
        err_str = str(e).lower()
        return any(kw in err_str for kw in ['lost connection', 'broken pipe', 'connection reset',
                                             'timeout', 'server closed', 'write failed'])

    def _reconnect(self):
        try:
            self.cursor.close()
        except Exception:
            pass
        try:
            self.conn.close()
        except Exception:
            pass
        self._connect()

    def executemany(self, sql, params_list):
        msql = _sqlite_to_mysql(sql)
        try:
            self.cursor.executemany(msql, params_list)
        except Exception as e:
            if self._is_connection_error(e):
                self._reconnect()
                self.cursor.executemany(msql, params_list)
        return self

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    @property
    def lastrowid(self):
        return self.cursor.lastrowid

    def commit(self):
        try:
            self.conn.commit()
        except Exception:
            pass

    def close(self):
        try:
            self.cursor.close()
        except Exception:
            pass
        try:
            self.conn.close()
        except Exception:
            pass


class _SQLiteWrapper:
    """统一包装 sqlite3，API 同 _MySQLWrapper"""
    def __init__(self):
        self.conn = None
        self.cursor = None
        self._connect()

    def _connect(self):
        self.conn = sqlite3.connect(DB_SQLITE, check_same_thread=False)
        self.conn.execute('PRAGMA encoding="UTF-8"')
        self.cursor = self.conn.cursor()

    def execute(self, sql, params=None):
        if params is None:
            self.cursor.execute(sql)
        else:
            self.cursor.execute(sql, params)
        return self

    def executemany(self, sql, params_list):
        self.cursor.executemany(sql, params_list)
        return self

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    @property
    def lastrowid(self):
        return self.cursor.lastrowid

    def commit(self):
        self.conn.commit()

    def close(self):
        try:
            self.cursor.close()
        except Exception:
            pass
        try:
            self.conn.close()
        except Exception:
            pass

    def rowcount(self):
        return self.cursor.rowcount


# ========== 数据库引擎 ==========
class Database:
    """双模式数据库：SQLite（本地）/ TiDB MySQL（云端）"""

    def __init__(self):
        self.mode = 'sqlite'
        self._wrapper = None
        self._parse_config()

    def _parse_config(self):
        """从 secrets 读取 TiDB 配置"""
        tidb_url = st.secrets.get('TIDB_URL', '')
        if tidb_url and HAS_MYSQL:
            pattern = r'mysql://([^:]+):([^@]+)@([^:]+):(\d+)/(\w+)'
            m = re.match(pattern, tidb_url.strip())
            if m:
                self.mode = 'mysql'
                self._mysql_config = {
                    'host': m.group(3),
                    'port': int(m.group(4)),
                    'user': m.group(1),
                    'password': m.group(2),
                    'database': m.group(5),
                }
                # 尝试使用 studydb，不存在则创建
                self._ensure_database()
            else:
                print(f'[DB] TiDB URL 格式无法解析，回退 SQLite')

    def _ensure_database(self):
        """确保 studydb 数据库存在"""
        db_name = self._mysql_config.get('database', 'studydb')
        if db_name != 'sys':
            return  # 用户已经用了非 sys 库
        try:
            temp = pymysql.connect(
                host=self._mysql_config['host'],
                port=self._mysql_config['port'],
                user=self._mysql_config['user'],
                password=self._mysql_config['password'],
                database='sys',
                ssl={'ssl': {}},
                connect_timeout=10,
            )
            with temp.cursor() as c:
                c.execute("CREATE DATABASE IF NOT EXISTS studydb")
            temp.close()
            self._mysql_config['database'] = 'studydb'
        except Exception as e:
            print(f'[DB] 创建 studydb 失败: {e}')

    def _get_wrapper(self):
        """获取数据库连接（惰性创建，无健康检查——执行时会自动重连）"""
        if self.mode == 'mysql':
            if self._wrapper is None:
                self._wrapper = _MySQLWrapper(self._mysql_config)
        else:
            if self._wrapper is None:
                self._wrapper = _SQLiteWrapper()
        return self._wrapper

    # -------- 对外 API --------

    def execute(self, sql, params=None):
        w = self._get_wrapper()
        w.execute(sql, params)
        return w

    def fetchall(self, sql, params=None):
        w = self._get_wrapper()
        w.execute(sql, params)
        return w.fetchall()

    def fetchone(self, sql, params=None):
        w = self._get_wrapper()
        w.execute(sql, params)
        return w.fetchone()

    def insert(self, sql, params=None):
        """执行 INSERT，返回 lastrowid"""
        w = self._get_wrapper()
        w.execute(sql, params)
        self.commit()
        return w.lastrowid

    def commit(self):
        if self._wrapper:
            self._wrapper.commit()

    def close(self):
        if self._wrapper:
            try:
                self._wrapper.close()
            except Exception:
                pass
            self._wrapper = None

    @property
    def lastrowid(self):
        if self._wrapper:
            return self._wrapper.lastrowid
        return None

    @property
    def rowcount(self):
        if self._wrapper:
            return self._wrapper.rowcount()
        return 0


# ========== 全局单例 ==========
db = Database()


# ========== 建表（双模式） ==========
def init_tables():
    """初始化所有数据表"""
    # SQLite 建表
    if db.mode == 'sqlite':
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
    # MySQL / TiDB 建表（用重试防止网络抖动）
    else:
        import time
        for table_sql in [
            '''CREATE TABLE IF NOT EXISTS wrong_questions (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                child_name TEXT, subject TEXT,
                question TEXT, wrong_reason TEXT, ai_analysis TEXT, image_data TEXT,
                created_date TEXT, is_mastered INTEGER DEFAULT 0, review_count INTEGER DEFAULT 0)''',
            '''CREATE TABLE IF NOT EXISTS checkins (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                child_name TEXT, checkin_date TEXT, note TEXT)''',
            '''CREATE TABLE IF NOT EXISTS daily_content (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                content_date TEXT, content_type TEXT, content TEXT)''',
            '''CREATE TABLE IF NOT EXISTS review_schedule (
                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                question_id INTEGER, child_name TEXT, subject TEXT,
                review_date TEXT, stage INTEGER, original_date TEXT,
                completed INTEGER DEFAULT 0)''',
        ]:
            for attempt in range(3):
                try:
                    db.execute(table_sql)
                    break
                except Exception:
                    if attempt < 2:
                        time.sleep(2)
                    else:
                        raise
    db.commit()


# ========== 艾宾浩斯复习计划 ==========
EBBINGHAUS_INTERVALS = [1, 3, 7, 14, 30]

def create_review_schedule(question_id, child_name, subject, created_date):
    """为一道错题创建艾宾浩斯复习计划"""
    base = date.fromisoformat(created_date)
    params = []
    for stage, days in enumerate(EBBINGHAUS_INTERVALS, 1):
        review_date = (base + timedelta(days=days)).isoformat()
        params.append((question_id, child_name, subject, review_date, stage, created_date))

    for p in params:
        db.execute(
            'INSERT INTO review_schedule(question_id, child_name, subject, review_date, stage, original_date) VALUES(%s,%s,%s,%s,%s,%s)',
            p
        )
    db.commit()

def get_today_reviews(child_name):
    """获取今天到期的复习任务"""
    today = str(date.today())
    mode = db.mode

    if mode == 'sqlite':
        return db.fetchall(
            'SELECT rs.id, rs.question_id, rs.subject, rs.stage, rs.original_date, '
            'wq.question, wq.wrong_reason, wq.ai_analysis, wq.image_data '
            'FROM review_schedule rs JOIN wrong_questions wq ON rs.question_id = wq.id '
            'WHERE rs.child_name=? AND rs.review_date=? AND rs.completed=0 '
            'ORDER BY rs.stage, rs.original_date',
            (child_name, today)
        )
    else:
        return db.fetchall(
            'SELECT rs.id, rs.question_id, rs.subject, rs.stage, rs.original_date, '
            'wq.question, wq.wrong_reason, wq.ai_analysis, wq.image_data '
            'FROM review_schedule rs JOIN wrong_questions wq ON rs.question_id = wq.id '
            'WHERE rs.child_name=%s AND rs.review_date=%s AND rs.completed=0 '
            'ORDER BY rs.stage, rs.original_date',
            (child_name, today)
        )

def get_today_review_count(child_name):
    """获取今天待复习数量"""
    today = str(date.today())
    mode = db.mode
    ph = '?' if mode == 'sqlite' else '%s'
    row = db.fetchone(
        f'SELECT COUNT(*) FROM review_schedule WHERE child_name={ph} AND review_date={ph} AND completed=0',
        (child_name, today)
    )
    return row[0] if row else 0

def mark_review_done(review_id):
    """标记复习完成"""
    mode = db.mode
    ph = '?' if mode == 'sqlite' else '%s'
    db.execute(f'UPDATE review_schedule SET completed=1 WHERE id={ph}', (review_id,))
    db.commit()
