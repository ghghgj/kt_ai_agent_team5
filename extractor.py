# extractor.py — 팀원 A 담당
# 역할: 뉴스 자동 수집 + 지식 그래프 데이터 추출 (Agent 1)
# ⚠️ run_agent1_extractor 함수의 시그니처는 절대 변경 금지.

import time
from datetime import datetime
from typing import List, Dict, Any

from db import init_db, save_articles, get_articles_by_keyword

# DB 초기화 (모듈 로드 시 1회)
init_db()


# ============================================================================
# 뉴스 수집 (DDGS 실제 구현)
# ============================================================================

def fetch_news_by_keywords(
    keywords: List[str],
    max_per_keyword: int = 5,
    user_tag: str = "anonymous",
) -> List[Dict[str, Any]]:
    """
    키워드 리스트로 DuckDuckGo News에서 최신 뉴스를 수집하고 DB에 저장합니다.

    Args:
        keywords: 검색 키워드 리스트 (예: ["삼성전자", "AI 반도체"])
        max_per_keyword: 키워드당 최대 수집 기사 수
        user_tag: 요청 사용자 식별자 (검색 로그용)

    Returns:
        List[Dict]: 수집된 기사 리스트
            각 항목: {keyword, title, body, url, source, date}
    """
    from duckduckgo_search import DDGS

    all_articles = []

    with DDGS() as ddgs:
        for keyword in keywords:
            try:
                results = list(
                    ddgs.news(
                        keyword,
                        max_results=max_per_keyword,
                        region="kr-kr",
                    )
                )
            except Exception as e:
                print(f"[DDGS] '{keyword}' 검색 오류: {e}")
                results = []

            articles = [
                {
                    "keyword": keyword,
                    "title":   r.get("title", ""),
                    "body":    r.get("body", ""),
                    "url":     r.get("url", ""),
                    "source":  r.get("source", ""),
                    "date":    r.get("date", ""),
                }
                for r in results
            ]

            saved = save_articles(keyword, articles, user_tag=user_tag)
            print(f"[DB] '{keyword}': {len(articles)}건 수집, {saved}건 신규 저장")

            all_articles.extend(articles)
            time.sleep(0.5)  # DDGS 요청 간격

    return all_articles


def auto_fetch_daily_news(
    keywords: List[str] | None = None,
    user_tag: str = "anonymous",
) -> str:
    """
    키워드 기반으로 최신 뉴스를 수집하여 하나의 텍스트 문자열로 반환합니다.
    수집된 기사는 DB에 자동 저장됩니다.

    Args:
        keywords: 검색 키워드 리스트. None이면 DB에서 기존 기사 반환.
        user_tag: 요청 사용자 식별자

    Returns:
        str: 수집된 뉴스 원문 텍스트 전체
    """
    if keywords:
        articles = fetch_news_by_keywords(keywords, user_tag=user_tag)
    else:
        # 키워드 없으면 DB 전체 최신 기사 활용
        from db import get_all_articles
        articles = get_all_articles(limit=50)

    if not articles:
        return ""

    lines = []
    for a in articles:
        date_str = a.get("date") or a.get("fetched_at", "")[:10]
        kw = a.get("keyword", "")
        lines.append(
            f"[{date_str}][{kw}] {a['title']}\n{a.get('body', '')}"
        )

    return "\n\n---\n\n".join(lines)


# ============================================================================
# Agent 1: 지식 그래프 추출 (TODO: LLM 연동)
# ============================================================================

def run_agent1_extractor(news_text: str) -> dict:
    """
    뉴스 텍스트를 분석하여 지식 그래프용 노드·엣지 데이터를 추출합니다.

    Args:
        news_text (str): auto_fetch_daily_news()가 반환한 뉴스 원문

    TODO (팀원 A):
        - LLM(GPT-4o 등)을 호출해 news_text에서 엔티티·관계 추출
        - 반환 딕셔너리의 키 구조("nodes", "edges")는 반드시 유지
        - 각 노드: {"id": str, "type": str, "label": str}
        - 각 엣지: {"source": str, "target": str, "relation": str, "sentiment": str}

    Returns:
        dict: 노드(nodes)와 엣지(edges) 리스트를 담은 지식 그래프 딕셔너리
    """
    # ── 더미 데이터 (LLM 연동 전까지 사용) ──────────────────────────────────
    dummy_graph = {
        "nodes": [
            {"id": "삼성전자",     "type": "Company",    "label": "삼성전자"},
            {"id": "SK하이닉스",   "type": "Company",    "label": "SK하이닉스"},
            {"id": "카카오",       "type": "Company",    "label": "카카오"},
            {"id": "엔비디아",     "type": "Company",    "label": "엔비디아"},
            {"id": "HBM4",         "type": "Product",    "label": "HBM4 메모리"},
            {"id": "CHIPS_Act",    "type": "Regulation", "label": "미국 반도체법"},
            {"id": "외국인투자자", "type": "Investor",   "label": "외국인 투자자"},
            {"id": "카카오브레인", "type": "Company",    "label": "카카오브레인"},
        ],
        "edges": [
            {"source": "삼성전자",    "target": "HBM4",      "relation": "PRODUCES",    "sentiment": "positive"},
            {"source": "HBM4",        "target": "엔비디아",   "relation": "SUPPLIES_TO", "sentiment": "positive"},
            {"source": "CHIPS_Act",   "target": "SK하이닉스", "relation": "CATALYZES",   "sentiment": "positive"},
            {"source": "외국인투자자","target": "SK하이닉스", "relation": "TRADES",      "sentiment": "positive"},
            {"source": "카카오브레인","target": "카카오",     "relation": "IMPACTS",     "sentiment": "positive"},
        ],
        "metadata": {
            "source_date": datetime.now().strftime("%Y-%m-%d"),
            "total_articles": len(news_text.split("---")),
        },
    }
    return dummy_graph
    # ── 더미 데이터 끝 ───────────────────────────────────────────────────────
