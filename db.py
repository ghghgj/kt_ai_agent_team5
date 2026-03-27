"""
db.py — Graph RAG용 지식 그래프 DB (SQLite)

스키마 설계 원칙:
  - 노드: 타입·서브타입·감성점수·별칭 지원
  - 엣지: 관계 카테고리(6종) · 신뢰도 · 시간 범위 · 근거 문장 연결
  - 서브 테이블로 RAG 검색 품질 향상 (evidence, aliases, hierarchy)
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_PATH = os.environ.get("DB_PATH", "news_graph.db")

# ── 관계 카테고리 정의 ──────────────────────────────────────────────────────
RELATION_CATEGORIES = {
    # 공급망
    "SUPPLIES_TO":       "SUPPLY_CHAIN",
    "SOURCES_FROM":      "SUPPLY_CHAIN",
    "COMPETES_WITH":     "SUPPLY_CHAIN",
    "PARTNERS_WITH":     "SUPPLY_CHAIN",
    "MANUFACTURES":      "SUPPLY_CHAIN",
    "DISTRIBUTES":       "SUPPLY_CHAIN",
    # 재무·투자
    "INVESTS_IN":        "FINANCIAL",
    "ACQUIRES":          "FINANCIAL",
    "OWNS_STAKE_IN":     "FINANCIAL",
    "FUNDED_BY":         "FINANCIAL",
    "MERGES_WITH":       "FINANCIAL",
    "DIVESTS":           "FINANCIAL",
    # 규제·정책
    "REGULATES":         "REGULATORY",
    "SUBSIDIZES":        "REGULATORY",
    "SANCTIONS":         "REGULATORY",
    "PENALIZES":         "REGULATORY",
    "APPROVES":          "REGULATORY",
    "RESTRICTS":         "REGULATORY",
    # 인과관계
    "CAUSES":            "CAUSAL",
    "CATALYZES":         "CAUSAL",
    "BENEFITS_FROM":     "CAUSAL",
    "THREATENS":         "CAUSAL",
    "DISRUPTS":          "CAUSAL",
    "DRIVES":            "CAUSAL",
    "AFFECTS":           "CAUSAL",
    "IMPACTS":           "CAUSAL",
    # 시장 영향
    "AFFECTS_PRICE":     "MARKET",
    "CORRELATES_WITH":   "MARKET",
    "LEADS_SECTOR":      "MARKET",
    "FOLLOWS_TREND":     "MARKET",
    "TRADES":            "MARKET",
    # 조직 관계
    "SUBSIDIARY_OF":     "ORGANIZATIONAL",
    "LED_BY":            "ORGANIZATIONAL",
    "EMPLOYS":           "ORGANIZATIONAL",
}


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """전체 테이블 초기화 및 마이그레이션"""
    conn = get_conn()
    with conn:
        conn.executescript("""
            -- ── 뉴스 기사 ──────────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS news_articles (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword        TEXT    NOT NULL,
                title          TEXT    NOT NULL,
                body           TEXT,
                url            TEXT    UNIQUE,
                source         TEXT,
                published_date TEXT,
                fetched_at     TEXT    NOT NULL,
                graph_extracted INTEGER DEFAULT 0
            );

            -- ── 검색 로그 ──────────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS search_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword     TEXT NOT NULL,
                user_tag    TEXT,
                searched_at TEXT NOT NULL
            );

            -- ── 그래프 노드 ────────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS graph_nodes (
                id              TEXT PRIMARY KEY,
                label           TEXT NOT NULL,
                type            TEXT NOT NULL,
                subtype         TEXT,              -- 세부 분류 (예: Listed/Unlisted, Primary/Sub)
                description     TEXT,
                mention_count   INTEGER DEFAULT 1,
                sentiment_score REAL    DEFAULT 0.0, -- 누적 감성 점수 (-1 ~ 1)
                first_seen      TEXT,
                last_updated    TEXT    NOT NULL
            );

            -- ── 노드 속성 (key-value) ──────────────────────────────────────
            CREATE TABLE IF NOT EXISTS node_properties (
                node_id TEXT NOT NULL,
                key     TEXT NOT NULL,
                value   TEXT,
                PRIMARY KEY (node_id, key),
                FOREIGN KEY (node_id) REFERENCES graph_nodes(id)
            );

            -- ── 노드 별칭 (정규화용) ───────────────────────────────────────
            CREATE TABLE IF NOT EXISTS node_aliases (
                alias        TEXT PRIMARY KEY,
                canonical_id TEXT NOT NULL,
                FOREIGN KEY (canonical_id) REFERENCES graph_nodes(id)
            );

            -- ── 섹터 계층 구조 ─────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS sector_hierarchy (
                child_sector  TEXT NOT NULL,
                parent_sector TEXT NOT NULL,
                PRIMARY KEY (child_sector, parent_sector)
            );

            -- ── 그래프 엣지 ────────────────────────────────────────────────
            CREATE TABLE IF NOT EXISTS graph_edges (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                source            TEXT NOT NULL,
                target            TEXT NOT NULL,
                relation          TEXT NOT NULL,
                relation_category TEXT,           -- SUPPLY_CHAIN/FINANCIAL/REGULATORY/CAUSAL/MARKET/ORGANIZATIONAL
                sentiment         TEXT DEFAULT 'neutral',
                confidence        REAL DEFAULT 1.0, -- LLM 추출 신뢰도 (0~1)
                weight            REAL DEFAULT 1.0, -- 언급 빈도 누적
                temporal_scope    TEXT,           -- SHORT/MEDIUM/LONG
                first_seen        TEXT,
                last_updated      TEXT NOT NULL,
                UNIQUE(source, target, relation)
            );

            -- ── 엣지 근거 (RAG 핵심: 어떤 기사의 어떤 문장이 근거인가) ────
            CREATE TABLE IF NOT EXISTS edge_evidence (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                edge_id    INTEGER NOT NULL,
                article_id INTEGER NOT NULL,
                excerpt    TEXT,                  -- 근거 문장 (뉴스 원문 발췌)
                UNIQUE(edge_id, article_id),
                FOREIGN KEY (edge_id)    REFERENCES graph_edges(id),
                FOREIGN KEY (article_id) REFERENCES news_articles(id)
            );
        """)

        # ── 기존 테이블 마이그레이션 (컬럼 추가) ──────────────────────────
        migrations = [
            ("news_articles",  "graph_extracted INTEGER DEFAULT 0"),
            ("graph_nodes",    "subtype TEXT"),
            ("graph_nodes",    "description TEXT"),
            ("graph_nodes",    "sentiment_score REAL DEFAULT 0.0"),
            ("graph_nodes",    "first_seen TEXT"),
            ("graph_edges",    "relation_category TEXT"),
            ("graph_edges",    "confidence REAL DEFAULT 1.0"),
            ("graph_edges",    "temporal_scope TEXT"),
            ("graph_edges",    "first_seen TEXT"),
        ]
        for table, col_def in migrations:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
            except Exception:
                pass
    conn.close()


# ── 뉴스 저장 ────────────────────────────────────────────────────────────────

def save_articles(keyword: str, articles: List[Dict[str, Any]], user_tag: str = "anonymous") -> int:
    now = datetime.now().isoformat()
    conn = get_conn()
    saved = 0
    with conn:
        for a in articles:
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO news_articles
                       (keyword, title, body, url, source, published_date, fetched_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (keyword, a.get("title",""), a.get("body",""),
                     a.get("url",""), a.get("source",""), a.get("date",""), now),
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


# ── 노드 ─────────────────────────────────────────────────────────────────────

def upsert_node(
    node_id: str,
    label: str,
    node_type: str,
    subtype: str = None,
    description: str = None,
    sentiment_delta: float = 0.0,
):
    """노드 추가 또는 mention_count·sentiment_score 업데이트"""
    now = datetime.now().isoformat()
    conn = get_conn()
    with conn:
        conn.execute(
            """
            INSERT INTO graph_nodes
                (id, label, type, subtype, description, mention_count, sentiment_score, first_seen, last_updated)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                mention_count   = mention_count + 1,
                sentiment_score = ROUND((sentiment_score * mention_count + excluded.sentiment_score)
                                        / (mention_count + 1), 4),
                last_updated    = excluded.last_updated
            """,
            (node_id, label, node_type, subtype, description, sentiment_delta, now, now),
        )
        # 별칭 자동 등록 (label ≠ id 이면 label을 alias로)
        if label != node_id:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO node_aliases (alias, canonical_id) VALUES (?, ?)",
                    (label, node_id),
                )
            except Exception:
                pass
    conn.close()


def set_node_property(node_id: str, key: str, value: str):
    conn = get_conn()
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO node_properties (node_id, key, value) VALUES (?, ?, ?)",
            (node_id, key, value),
        )
    conn.close()


def resolve_alias(name: str) -> str:
    """별칭을 정규 노드 ID로 변환 (없으면 원본 반환)"""
    conn = get_conn()
    row = conn.execute(
        "SELECT canonical_id FROM node_aliases WHERE alias = ?", (name,)
    ).fetchone()
    conn.close()
    return row["canonical_id"] if row else name


# ── 엣지 ─────────────────────────────────────────────────────────────────────

def upsert_edge(
    source: str,
    target: str,
    relation: str,
    sentiment: str = "neutral",
    confidence: float = 1.0,
    temporal_scope: str = None,
) -> int:
    """엣지 추가 또는 weight·confidence 업데이트. edge_id 반환"""
    now = datetime.now().isoformat()
    category = RELATION_CATEGORIES.get(relation, "CAUSAL")
    conn = get_conn()
    with conn:
        conn.execute(
            """
            INSERT INTO graph_edges
                (source, target, relation, relation_category, sentiment,
                 confidence, weight, temporal_scope, first_seen, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, 1.0, ?, ?, ?)
            ON CONFLICT(source, target, relation) DO UPDATE SET
                weight         = weight + 1.0,
                confidence     = ROUND((confidence + excluded.confidence) / 2, 4),
                sentiment      = excluded.sentiment,
                last_updated   = excluded.last_updated
            """,
            (source, target, relation, category, sentiment,
             confidence, temporal_scope, now, now),
        )
        row = conn.execute(
            "SELECT id FROM graph_edges WHERE source=? AND target=? AND relation=?",
            (source, target, relation),
        ).fetchone()
    edge_id = row["id"] if row else None
    conn.close()
    return edge_id


def add_edge_evidence(edge_id: int, article_id: int, excerpt: str = ""):
    """엣지에 근거 기사·발췌문 연결"""
    if not edge_id or not article_id:
        return
    conn = get_conn()
    with conn:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO edge_evidence (edge_id, article_id, excerpt) VALUES (?, ?, ?)",
                (edge_id, article_id, excerpt[:500]),
            )
        except Exception:
            pass
    conn.close()


def add_sector_hierarchy(child: str, parent: str):
    conn = get_conn()
    with conn:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO sector_hierarchy (child_sector, parent_sector) VALUES (?, ?)",
                (child, parent),
            )
        except Exception:
            pass
    conn.close()


# ── 조회 ─────────────────────────────────────────────────────────────────────

def get_unextracted_articles(limit: int = 50, keyword: str = None) -> List[Dict]:
    conn = get_conn()
    if keyword:
        rows = conn.execute(
            """SELECT id, keyword, title, body, url FROM news_articles
               WHERE graph_extracted = 0 AND body IS NOT NULL AND body != ''
               AND keyword = ?
               ORDER BY fetched_at DESC LIMIT ?""",
            (keyword, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT id, keyword, title, body, url FROM news_articles
               WHERE graph_extracted = 0 AND body IS NOT NULL AND body != ''
               ORDER BY fetched_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_articles_extracted(article_ids: List[int]):
    conn = get_conn()
    with conn:
        conn.executemany(
            "UPDATE news_articles SET graph_extracted = 1 WHERE id = ?",
            [(i,) for i in article_ids],
        )
    conn.close()


def get_graph_data() -> Dict[str, Any]:
    """시각화용 전체 그래프"""
    conn = get_conn()
    nodes = conn.execute(
        """SELECT id, label, type, subtype, mention_count, sentiment_score
           FROM graph_nodes ORDER BY mention_count DESC"""
    ).fetchall()
    edges = conn.execute(
        """SELECT id, source, target, relation, relation_category,
                  sentiment, confidence, weight, temporal_scope
           FROM graph_edges"""
    ).fetchall()
    conn.close()
    return {
        "nodes": [dict(n) for n in nodes],
        "edges": [dict(e) for e in edges],
    }


def get_node_properties(node_id: str) -> Dict[str, str]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT key, value FROM node_properties WHERE node_id = ?", (node_id,)
    ).fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def get_edge_evidence_for_rag(edge_ids: List[int]) -> List[Dict]:
    """엣지 근거 기사 조회 (RAG 컨텍스트 강화용)"""
    if not edge_ids:
        return []
    conn = get_conn()
    placeholders = ",".join("?" * len(edge_ids))
    rows = conn.execute(
        f"""
        SELECT ee.edge_id, ee.excerpt,
               na.title, na.body, na.source, na.published_date,
               ge.source as edge_src, ge.target as edge_tgt, ge.relation
        FROM edge_evidence ee
        JOIN news_articles na ON ee.article_id = na.id
        JOIN graph_edges   ge ON ee.edge_id    = ge.id
        WHERE ee.edge_id IN ({placeholders})
        ORDER BY ee.edge_id
        """,
        edge_ids,
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_graph_stats() -> Dict[str, Any]:
    conn = get_conn()
    node_count  = conn.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0]
    edge_count  = conn.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]
    evidence_count = conn.execute("SELECT COUNT(*) FROM edge_evidence").fetchone()[0]
    alias_count = conn.execute("SELECT COUNT(*) FROM node_aliases").fetchone()[0]
    top_nodes   = conn.execute(
        "SELECT label, type, mention_count, ROUND(sentiment_score,2) as sentiment_score FROM graph_nodes ORDER BY mention_count DESC LIMIT 10"
    ).fetchall()
    by_category = conn.execute(
        "SELECT relation_category, COUNT(*) as cnt FROM graph_edges GROUP BY relation_category ORDER BY cnt DESC"
    ).fetchall()
    conn.close()
    return {
        "node_count":     node_count,
        "edge_count":     edge_count,
        "evidence_count": evidence_count,
        "alias_count":    alias_count,
        "top_nodes":      [dict(n) for n in top_nodes],
        "by_category":    [dict(r) for r in by_category],
    }


def get_articles_by_keyword(keyword: str, limit: int = 30) -> List[Dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT title, body, url, source, published_date, fetched_at
           FROM news_articles WHERE keyword = ?
           ORDER BY fetched_at DESC LIMIT ?""",
        (keyword, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_articles(limit: int = 200) -> List[Dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT keyword, title, body, url, source, published_date, fetched_at
           FROM news_articles ORDER BY fetched_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_articles_for_nodes(node_labels: List[str], limit: int = 15) -> List[Dict]:
    """노드 레이블 포함 뉴스 기사 검색"""
    if not node_labels:
        return []
    conn = get_conn()
    conditions = " OR ".join(["(title LIKE ? OR body LIKE ?)" for _ in node_labels])
    params = [v for label in node_labels for v in (f"%{label}%", f"%{label}%")]
    rows = conn.execute(
        f"""SELECT DISTINCT id, title, body, source, published_date, url
            FROM news_articles WHERE {conditions}
            ORDER BY fetched_at DESC LIMIT ?""",
        params + [limit],
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats() -> Dict[str, Any]:
    conn = get_conn()
    total    = conn.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0]
    keywords = conn.execute(
        "SELECT keyword, COUNT(*) as cnt FROM news_articles GROUP BY keyword ORDER BY cnt DESC"
    ).fetchall()
    searches = conn.execute("SELECT COUNT(*) FROM search_log").fetchone()[0]
    conn.close()
    return {
        "total_articles":  total,
        "total_searches":  searches,
        "by_keyword":      [dict(r) for r in keywords],
    }
