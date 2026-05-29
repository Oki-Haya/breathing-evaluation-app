import os
import sqlite3
from pathlib import Path

DATABASE_URL = os.environ.get('DATABASE_URL')
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras

DB_PATH = Path(__file__).parent / 'breathing.db'

_SCHEMA_COMMON_BODY = """
    CREATE TABLE IF NOT EXISTS clients (
        id {serial} PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS sessions (
        id {serial} PRIMARY KEY,
        client_id INTEGER NOT NULL REFERENCES clients(id),
        session_date DATE NOT NULL,
        day_of_week TEXT NOT NULL,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS evaluations (
        id {serial} PRIMARY KEY,
        session_id INTEGER NOT NULL REFERENCES sessions(id),
        eval_type TEXT NOT NULL,
        maekutsu INTEGER DEFAULT 0,
        koukutsu INTEGER DEFAULT 0,
        banzai INTEGER DEFAULT 0,
        atede_gumi INTEGER DEFAULT 0,
        sokukutsu INTEGER DEFAULT 0,
        kubi_sokukutsu INTEGER DEFAULT 0,
        kyokaku_kubinashi INTEGER DEFAULT 0,
        kyokaku_kubiari INTEGER DEFAULT 0,
        kyokaku_kubiari_me INTEGER DEFAULT 0,
        shagamu INTEGER DEFAULT 0,
        breathing_count REAL,
        breathing_type TEXT,
        body_score INTEGER,
        breathing_rate_score INTEGER,
        breathing_type_score INTEGER,
        total_score INTEGER
    );
"""

_SCHEMA_SQLITE = _SCHEMA_COMMON_BODY.format(serial='INTEGER')
_SCHEMA_POSTGRES = _SCHEMA_COMMON_BODY.format(serial='SERIAL')


def get_conn():
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        return conn
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def _exec(conn, sql, params=()):
    if USE_POSTGRES:
        sql = sql.replace('?', '%s')
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur


def _rows(cur):
    return [dict(r) for r in cur.fetchall()]


def _row(cur):
    row = cur.fetchone()
    return dict(row) if row else None


def _insert(conn, sql, params=()):
    if USE_POSTGRES:
        sql = sql.replace('?', '%s') + ' RETURNING id'
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchone()['id']
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur.lastrowid


def init_db():
    conn = get_conn()
    try:
        if USE_POSTGRES:
            cur = conn.cursor()
            for stmt in _SCHEMA_POSTGRES.split(';'):
                stmt = stmt.strip()
                if stmt:
                    cur.execute(stmt)
            # マイグレーション: exercise_notes カラムを追加（既存DBへの対応）
            try:
                cur.execute('ALTER TABLE sessions ADD COLUMN IF NOT EXISTS exercise_notes TEXT')
            except Exception:
                pass
        else:
            conn.executescript(_SCHEMA_SQLITE)
            # マイグレーション: exercise_notes カラムを追加（既存DBへの対応）
            try:
                conn.execute('ALTER TABLE sessions ADD COLUMN exercise_notes TEXT')
            except Exception:
                pass
        conn.commit()
    finally:
        conn.close()


# --- Clients ---

def get_all_clients():
    conn = get_conn()
    try:
        cur = _exec(conn, """
            SELECT c.*,
                   COUNT(s.id) AS session_count,
                   MAX(s.session_date) AS last_session_date
            FROM clients c
            LEFT JOIN sessions s ON s.client_id = c.id
            GROUP BY c.id
            ORDER BY c.name
        """)
        return _rows(cur)
    finally:
        conn.close()


def get_client(client_id):
    conn = get_conn()
    try:
        return _row(_exec(conn, 'SELECT * FROM clients WHERE id = ?', (client_id,)))
    finally:
        conn.close()


def create_client(name):
    conn = get_conn()
    try:
        row_id = _insert(conn, 'INSERT INTO clients (name) VALUES (?)', (name,))
        conn.commit()
        return row_id
    finally:
        conn.close()


def delete_client(client_id):
    conn = get_conn()
    try:
        _exec(conn, 'DELETE FROM evaluations WHERE session_id IN (SELECT id FROM sessions WHERE client_id = ?)', (client_id,))
        _exec(conn, 'DELETE FROM sessions WHERE client_id = ?', (client_id,))
        _exec(conn, 'DELETE FROM clients WHERE id = ?', (client_id,))
        conn.commit()
    finally:
        conn.close()


# --- Sessions ---

def get_client_sessions(client_id):
    conn = get_conn()
    try:
        cur = _exec(conn, """
            SELECT s.*,
                   b.total_score AS before_total,
                   a.total_score AS after_total
            FROM sessions s
            LEFT JOIN evaluations b ON b.session_id = s.id AND b.eval_type = 'before'
            LEFT JOIN evaluations a ON a.session_id = s.id AND a.eval_type = 'after'
            WHERE s.client_id = ?
            ORDER BY s.session_date DESC
        """, (client_id,))
        return _rows(cur)
    finally:
        conn.close()


def get_session(session_id):
    conn = get_conn()
    try:
        return _row(_exec(conn, 'SELECT * FROM sessions WHERE id = ?', (session_id,)))
    finally:
        conn.close()


def create_session(client_id, session_date, day_of_week, notes='', exercise_notes=''):
    conn = get_conn()
    try:
        row_id = _insert(
            conn,
            'INSERT INTO sessions (client_id, session_date, day_of_week, notes, exercise_notes) VALUES (?, ?, ?, ?, ?)',
            (client_id, session_date, day_of_week, notes, exercise_notes),
        )
        conn.commit()
        return row_id
    finally:
        conn.close()


def update_session_notes(session_id, notes, exercise_notes):
    conn = get_conn()
    try:
        _exec(conn,
              'UPDATE sessions SET notes = ?, exercise_notes = ? WHERE id = ?',
              (notes, exercise_notes, session_id))
        conn.commit()
    finally:
        conn.close()


def delete_session(session_id):
    conn = get_conn()
    try:
        _exec(conn, 'DELETE FROM evaluations WHERE session_id = ?', (session_id,))
        _exec(conn, 'DELETE FROM sessions WHERE id = ?', (session_id,))
        conn.commit()
    finally:
        conn.close()


# --- Evaluations ---

def get_evaluation(session_id, eval_type):
    conn = get_conn()
    try:
        return _row(_exec(
            conn,
            'SELECT * FROM evaluations WHERE session_id = ? AND eval_type = ?',
            (session_id, eval_type),
        ))
    finally:
        conn.close()


def upsert_evaluation(session_id, eval_type, fields):
    conn = get_conn()
    try:
        existing = _row(_exec(
            conn,
            'SELECT id FROM evaluations WHERE session_id = ? AND eval_type = ?',
            (session_id, eval_type),
        ))
        cols = list(fields.keys())
        vals = list(fields.values())
        if existing:
            set_clause = ', '.join(f'{k} = ?' for k in cols)
            _exec(conn,
                f'UPDATE evaluations SET {set_clause} WHERE session_id = ? AND eval_type = ?',
                vals + [session_id, eval_type])
        else:
            placeholders = ', '.join('?' * len(cols))
            _insert(conn,
                f'INSERT INTO evaluations (session_id, eval_type, {", ".join(cols)}) VALUES (?, ?, {placeholders})',
                [session_id, eval_type] + vals)
        conn.commit()
    finally:
        conn.close()
