"""
enrich_graph.py — 기업·섹터 노드 중심 그래프 보강 스크립트

1. 유효 기업·섹터 노드별 개별 뉴스 추가 수집
2. 교차 관계 쿼리 (A + B 동시 검색) 로 연관관계 강화
3. 기존 기사 graph_extracted 초기화 → 새 프롬프트로 재추출
4. build_graph_from_new_articles 실행
"""

import time
from dotenv import load_dotenv
load_dotenv()

from db import init_db, get_conn, get_graph_stats
from extractor import fetch_news_by_keywords
from graph_builder import build_graph_from_new_articles

init_db()

# ── 대상 기업 (증권 관련성 높은 것만) ─────────────────────────────────────
TARGET_COMPANIES = [
    "삼성전자", "SK하이닉스", "LG화학", "LG에너지솔루션",
    "포스코", "포스코홀딩스", "SK이노베이션", "금호석유화학",
    "현대차", "기아", "현대로템", "삼성SDI",
    "SK텔레콤", "KT", "네이버", "카카오",
    "삼성바이오로직스", "셀트리온", "한국조선해양",
    "하나은행", "KB금융", "신한금융", "우리금융",
]

# ── 대상 섹터 ──────────────────────────────────────────────────────────────
TARGET_SECTORS = [
    "반도체", "이차전지", "철강", "석유화학", "정유",
    "자동차", "조선", "제약·바이오", "통신", "금융",
    "로봇", "방산", "태양광", "수소에너지",
]

# ── 교차 관계 쿼리 (두 노드의 연관성을 직접 검색) ─────────────────────────
CROSS_QUERIES = [
    "삼성전자 엔비디아 HBM",
    "SK하이닉스 반도체 수출",
    "LG화학 포스코 배터리 소재",
    "LG에너지솔루션 전기차 수요",
    "현대차 기아 전기차 배터리",
    "철강 자동차 수요",
    "석유화학 유가 스프레드",
    "반도체 미국 수출규제",
    "이차전지 리튬 가격",
    "제약 바이오 FDA 임상",
    "금리 은행 순이자마진",
    "원달러 환율 수출 기업",
    "AI 반도체 데이터센터",
    "중국 경기 철강 화학",
    "삼성전자 SK하이닉스 D램",
]


def reset_graph_extracted():
    """기존 기사를 미처리 상태로 초기화 → 새 프롬프트로 재추출"""
    conn = get_conn()
    with conn:
        conn.execute("UPDATE news_articles SET graph_extracted = 0")
    count = conn.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0]
    conn.close()
    print(f"[초기화] {count}건 재처리 대상으로 설정")


def fetch_for_targets():
    total = 0
    print("\n=== 기업별 뉴스 수집 ===")
    for company in TARGET_COMPANIES:
        arts = fetch_news_by_keywords([company], max_per_keyword=10)
        total += len(arts)
        print(f"  {company}: {len(arts)}건")
        time.sleep(0.5)

    print("\n=== 섹터별 뉴스 수집 ===")
    for sector in TARGET_SECTORS:
        arts = fetch_news_by_keywords([sector], max_per_keyword=10)
        total += len(arts)
        print(f"  {sector}: {len(arts)}건")
        time.sleep(0.5)

    print("\n=== 교차 관계 쿼리 수집 ===")
    for query in CROSS_QUERIES:
        arts = fetch_news_by_keywords([query], max_per_keyword=8)
        total += len(arts)
        print(f"  '{query}': {len(arts)}건")
        time.sleep(0.5)

    print(f"\n총 {total}건 신규 수집 완료")


def run_graph_extraction():
    print("\n=== 그래프 추출 시작 ===")
    total_processed = 0
    total_nodes = 0
    total_edges = 0

    while True:
        result = build_graph_from_new_articles()
        if result["processed"] == 0:
            break
        total_processed += result["processed"]
        total_nodes += result["new_nodes"]
        total_edges += result["new_edges"]
        print(f"  처리 {result['processed']}건 | 노드 +{result['new_nodes']} | 엣지 +{result['new_edges']}")
        time.sleep(0.3)

    print(f"\n추출 완료: {total_processed}건 처리 | 노드 +{total_nodes} | 엣지 +{total_edges}")


if __name__ == "__main__":
    print("=" * 60)
    print("그래프 보강 스크립트 시작")
    print("=" * 60)

    # 1. 뉴스 수집
    fetch_for_targets()

    # 2. 기존 기사 재처리 설정 (새 프롬프트 적용)
    print("\n=== 기존 기사 재처리 설정 ===")
    reset_graph_extracted()

    # 3. 그래프 추출
    run_graph_extraction()

    # 4. 최종 현황
    stats = get_graph_stats()
    print("\n" + "=" * 60)
    print("최종 그래프 현황")
    print(f"  노드: {stats['node_count']}개")
    print(f"  엣지: {stats['edge_count']}개")
    print(f"  근거문장: {stats['evidence_count']}개")
    print(f"  카테고리: {stats['by_category']}")
    print("=" * 60)
