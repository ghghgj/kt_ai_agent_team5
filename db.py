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
                fetched_at    TEXT    NOT NULL,
                graph_extracted INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS search_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword    TEXT NOT NULL,
                user_tag   TEXT,
                searched_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS graph_nodes (
                id            TEXT PRIMARY KEY,
                label         TEXT NOT NULL,
                type          TEXT NOT NULL,
                mention_count INTEGER DEFAULT 1,
                last_updated  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS graph_edges (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source      TEXT NOT NULL,
                target      TEXT NOT NULL,
                relation    TEXT NOT NULL,
                sentiment   TEXT DEFAULT 'neutral',
                weight      REAL DEFAULT 1.0,
                last_updated TEXT NOT NULL,
                UNIQUE(source, target, relation)
            );
        """)
        # 기존 테이블에 graph_extracted 컬럼 없으면 추가
        try:
            conn.execute("ALTER TABLE news_articles ADD COLUMN graph_extracted INTEGER DEFAULT 0")
        except Exception:
            pass
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


def get_unextracted_articles(limit: int = 50) -> List[Dict]:
    """그래프 추출이 안 된 기사 조회"""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT id, keyword, title, body, url
        FROM news_articles
        WHERE graph_extracted = 0 AND body IS NOT NULL AND body != ''
        ORDER BY fetched_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_articles_extracted(article_ids: List[int]):
    """기사를 그래프 추출 완료로 표시"""
    conn = get_conn()
    with conn:
        conn.executemany(
            "UPDATE news_articles SET graph_extracted = 1 WHERE id = ?",
            [(i,) for i in article_ids],
        )
    conn.close()


def upsert_node(node_id: str, label: str, node_type: str):
    """노드 추가 또는 mention_count 증가"""
    now = datetime.now().isoformat()
    conn = get_conn()
    with conn:
        conn.execute(
            """
            INSERT INTO graph_nodes (id, label, type, mention_count, last_updated)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(id) DO UPDATE SET
                mention_count = mention_count + 1,
                last_updated = excluded.last_updated
            """,
            (node_id, label, node_type, now),
        )
    conn.close()


def upsert_edge(source: str, target: str, relation: str, sentiment: str = "neutral"):
    """엣지 추가 또는 weight 증가"""
    now = datetime.now().isoformat()
    conn = get_conn()
    with conn:
        conn.execute(
            """
            INSERT INTO graph_edges (source, target, relation, sentiment, weight, last_updated)
            VALUES (?, ?, ?, ?, 1.0, ?)
            ON CONFLICT(source, target, relation) DO UPDATE SET
                weight = weight + 1.0,
                sentiment = excluded.sentiment,
                last_updated = excluded.last_updated
            """,
            (source, target, relation, sentiment, now),
        )
    conn.close()


def get_graph_data() -> Dict[str, Any]:
    """시각화용 전체 그래프 데이터 조회"""
    conn = get_conn()
    nodes = conn.execute(
        "SELECT id, label, type, mention_count FROM graph_nodes ORDER BY mention_count DESC"
    ).fetchall()
    edges = conn.execute(
        "SELECT source, target, relation, sentiment, weight FROM graph_edges"
    ).fetchall()
    conn.close()
    return {
        "nodes": [dict(n) for n in nodes],
        "edges": [dict(e) for e in edges],
    }


def get_graph_stats() -> Dict[str, Any]:
    """그래프 현황 통계"""
    conn = get_conn()
    node_count = conn.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0]
    edge_count = conn.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]
    top_nodes = conn.execute(
        "SELECT label, type, mention_count FROM graph_nodes ORDER BY mention_count DESC LIMIT 10"
    ).fetchall()
    conn.close()
    return {
        "node_count": node_count,
        "edge_count": edge_count,
        "top_nodes": [dict(n) for n in top_nodes],
    }


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
