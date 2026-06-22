"""오목 게임 결과를 SQLite(omok.db)에 기록하고 리더보드를 집계하는 모듈."""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "omok.db")

# CLAUDE.md 의 스키마 정의를 그대로 사용한다.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    played_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    mode        TEXT    NOT NULL,
    black_name  TEXT    NOT NULL,
    white_name  TEXT    NOT NULL,
    winner      TEXT    NOT NULL,
    renju_rule  INTEGER NOT NULL,
    move_count  INTEGER NOT NULL,
    duration_s  INTEGER NOT NULL
);
"""


def _connect():
    return sqlite3.connect(DB_PATH)


def init_db():
    """테이블이 없으면 생성한다. (시작 시 1회 호출)"""
    with _connect() as conn:
        conn.execute(_SCHEMA)
        conn.commit()


def record_game(mode, black_name, white_name, winner, renju_rule, move_count, duration_s):
    """게임 종료 시 결과 1행을 INSERT 한다.

    winner: 'BLACK' | 'WHITE' | 'DRAW'
    renju_rule: 1(ON/금지) | 0(OFF/허용)
    """
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO games
                (mode, black_name, white_name, winner, renju_rule, move_count, duration_s)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (mode, black_name, white_name, winner, int(renju_rule), int(move_count), int(duration_s)),
        )
        conn.commit()


def get_leaderboard(limit=10):
    """플레이어별 승수 랭킹을 [(name, wins), ...] 형태로 반환한다."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT name, COUNT(*) AS wins
            FROM (
                SELECT black_name AS name FROM games WHERE winner = 'BLACK'
                UNION ALL
                SELECT white_name AS name FROM games WHERE winner = 'WHITE'
            )
            WHERE name != 'CPU'
            GROUP BY name
            ORDER BY wins DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return rows


def get_recent_games(limit=10):
    """최근 게임 기록을 반환한다."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT played_at, mode, black_name, white_name, winner, move_count, duration_s
            FROM games
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return rows
