"""
seed_news.py — 증권 시황용 주요 뉴스 초기 수집 스크립트
산업군별 키워드로 최근 뉴스 ~100건을 DB에 적재합니다.
"""

import time
from duckduckgo_search import DDGS
from db import init_db, save_articles, get_stats

# 산업군별 키워드 (5건 × 20개 = 최대 100건)
SECTOR_KEYWORDS = {
    "반도체/IT":    ["AI 반도체 수출", "HBM 메모리"],
    "빅테크":       ["엔비디아 실적", "마이크로소프트 AI"],
    "자동차/전기차": ["현대차 실적", "전기차 판매"],
    "배터리/에너지": ["LG에너지솔루션", "배터리 수요"],
    "바이오/제약":   ["바이오 임상", "제약 FDA 승인"],
    "금융/은행":    ["한국 기준금리", "은행 순이익"],
    "거시경제":     ["미국 연준 금리", "한국 경제성장률"],
    "환율/외환":    ["원달러 환율", "외국인 순매수"],
    "에너지/유가":  ["국제유가 WTI", "정유 실적"],
    "화학/소재":    ["포스코 철강", "LG화학 실적"],
}

def fetch_sector_news(keyword: str, sector: str, max_results: int = 5) -> list:
    articles = []
    with DDGS() as ddgs:
        try:
            results = list(ddgs.news(
                keyword,
                max_results=max_results,
                region="kr-kr",
                timelimit="w",  # 최근 1주일
            ))
            for r in results:
                articles.append({
                    "keyword": f"{sector}>{keyword}",
                    "title":   r.get("title", ""),
                    "body":    r.get("body", ""),
                    "url":     r.get("url", ""),
                    "source":  r.get("source", ""),
                    "date":    r.get("date", ""),
                })
        except Exception as e:
            print(f"  ⚠️  오류: {e}")
    return articles


def main():
    init_db()
    print("=" * 60)
    print("증권 시황 뉴스 초기 적재 시작")
    print("=" * 60)

    total_saved = 0
    total_fetched = 0

    for sector, keywords in SECTOR_KEYWORDS.items():
        print(f"\n[{sector}]")
        for keyword in keywords:
            articles = fetch_sector_news(keyword, sector, max_results=5)
            saved = save_articles(f"{sector}>{keyword}", articles, user_tag="seed_script")
            total_fetched += len(articles)
            total_saved += saved
            print(f"  '{keyword}': {len(articles)}건 수집, {saved}건 신규 저장")
            time.sleep(0.8)

    print("\n" + "=" * 60)
    print(f"완료: 총 {total_fetched}건 수집 / {total_saved}건 신규 저장")
    stats = get_stats()
    print(f"DB 누적 총 기사 수: {stats['total_articles']}건")
    print("=" * 60)


if __name__ == "__main__":
    main()
