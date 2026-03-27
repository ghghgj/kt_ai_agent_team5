"""
db.py — 뉴스 및 그래프 데이터 영속성 관리 (SQLite)
여러 사용자의 검색 결과가 누적되어 그래프 DB를 구축합니다.
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any

DB_PATH = os.environ.get("DB_PATH", "news_graph.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """테이블 초기화 (앱 시작 시 1회 실행)"""
    conn = get_conn()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS news_articles (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword       TEXT    NOT NULL,
                title         TEXT    NOT NULL,
                body          TEXT,
                url           TEXT    UNIQUE,
                source        TEXT,
                published_date TEXT,
                fetched_at    TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS search_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword    TEXT NOT NULL,
                user_tag   TEXT,
                searched_at TEXT NOT NULL
            );
        """)
    conn.close()


def save_articles(keyword: str, articles: List[Dict[str, Any]], user_tag: str = "anonymous"):
    """
    수집된 뉴스 기사를 DB에 저장합니다.
    URL이 이미 존재하면 IGNORE (중복 방지).

    Returns:
        int: 새로 저장된 기사 수
    """
    now = datetime.now().isoformat()
    conn = get_conn()
    saved = 0
    with conn:
        for a in articles:
            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO news_articles
                        (keyword, title, body, url, source, published_date, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        keyword,
                        a.get("title", ""),
                        a.get("body", ""),
                        a.get("url", ""),
                        a.get("source", ""),
                        a.get("date", ""),
                        now,
                    ),
                )
                if conn.execute("SELECT changes()").fetchone()[0]:
                    saved += 1
            except Exception:
                pass

        conn.execute(
            "INSERT INTO search_log (keyword, user_tag, searched_at) VALUES (?, ?, ?)",
            (keyword, user_tag, now),
        )
    conn.close()
    return saved


def get_articles_by_keyword(keyword: str, limit: int = 30) -> List[Dict]:
    """DB에서 키워드로 기사 조회 (최신순)"""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT title, body, url, source, published_date, fetched_at
        FROM news_articles
        WHERE keyword = ?
        ORDER BY fetched_at DESC
        LIMIT ?
        """,
        (keyword, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_articles(limit: int = 200) -> List[Dict]:
    """전체 누적 기사 조회 (그래프 구축용)"""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT keyword, title, body, url, source, published_date, fetched_at
        FROM news_articles
        ORDER BY fetched_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats() -> Dict[str, Any]:
    """DB 현황 통계"""
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0]
    keywords = conn.execute(
        "SELECT keyword, COUNT(*) as cnt FROM news_articles GROUP BY keyword ORDER BY cnt DESC"
    ).fetchall()
    searches = conn.execute("SELECT COUNT(*) FROM search_log").fetchone()[0]
    conn.close()
    return {
        "total_articles": total,
        "total_searches": searches,
        "by_keyword": [dict(r) for r in keywords],
    }
