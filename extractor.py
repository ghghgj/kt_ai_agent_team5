# extractor.py — 팀원 A 담당
# 역할: 뉴스 자동 수집 + 지식 그래프 데이터 추출 (Agent 1)
# ⚠️ 아래 두 함수의 내부 로직만 교체하면 됩니다. 함수 시그니처는 절대 변경 금지.

WATCHLIST = ["삼성전자", "SK하이닉스", "카카오", "현대차", "LG에너지솔루션"]


def auto_fetch_daily_news() -> str:
    """
    관심 종목(WATCHLIST)을 기반으로 최신 뉴스를 자동 수집하여
    하나의 긴 문자열로 반환합니다.

    TODO (팀원 A):
        - WATCHLIST 종목별 뉴스 크롤링 or API 호출 로직 구현
        - 반환값은 반드시 str 유지

    Returns:
        str: 수집된 뉴스 원문 텍스트 전체
    """
    # ── 더미 데이터 (실제 구현 전까지 이 블록을 사용) ──────────────────────
    dummy_news = """
    [2026-03-27] 삼성전자, 3나노 GAA 공정 수율 90% 돌파… HBM4 양산 본격화
    삼성전자가 차세대 3나노 GAA(Gate-All-Around) 공정에서 수율 90%를 달성했다고 밝혔다.
    이에 따라 HBM4 메모리 양산이 2분기부터 본격화될 전망이다.
    엔비디아와의 공급 협상도 재개된 것으로 알려졌다.

    [2026-03-27] 미국 반도체법(CHIPS Act) 보조금 2차 집행… SK하이닉스 1.2조 수혜
    미국 상무부가 반도체법 보조금 2차 집행 계획을 발표했다.
    SK하이닉스는 인디애나 공장 건설 지원금으로 약 1.2조 원을 받을 예정이다.
    외국인 투자자들은 SK하이닉스 주식을 3거래일 연속 순매수하고 있다.

    [2026-03-27] 카카오, AI 자회사 카카오브레인 흑자 전환 성공
    카카오브레인이 기업용 SaaS 서비스 확대로 첫 분기 흑자를 기록했다.
    이는 카카오 본사의 지분 가치 재평가로 이어질 것으로 분석된다.
    """
    return dummy_news.strip()
    # ── 더미 데이터 끝 ───────────────────────────────────────────────────────


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
    # ── 더미 데이터 (실제 구현 전까지 이 블록을 사용) ──────────────────────
    dummy_graph = {
        "nodes": [
            {"id": "삼성전자",       "type": "Company",    "label": "삼성전자"},
            {"id": "SK하이닉스",     "type": "Company",    "label": "SK하이닉스"},
            {"id": "카카오",         "type": "Company",    "label": "카카오"},
            {"id": "엔비디아",       "type": "Company",    "label": "엔비디아"},
            {"id": "HBM4",           "type": "Product",    "label": "HBM4 메모리"},
            {"id": "CHIPS_Act",      "type": "Regulation", "label": "미국 반도체법"},
            {"id": "외국인투자자",   "type": "Investor",   "label": "외국인 투자자"},
            {"id": "카카오브레인",   "type": "Company",    "label": "카카오브레인"},
        ],
        "edges": [
            {"source": "삼성전자",   "target": "HBM4",       "relation": "PRODUCES",   "sentiment": "positive"},
            {"source": "HBM4",       "target": "엔비디아",    "relation": "SUPPLIES_TO","sentiment": "positive"},
            {"source": "CHIPS_Act",  "target": "SK하이닉스", "relation": "CATALYZES",  "sentiment": "positive"},
            {"source": "외국인투자자","target": "SK하이닉스", "relation": "TRADES",     "sentiment": "positive"},
            {"source": "카카오브레인","target": "카카오",     "relation": "IMPACTS",    "sentiment": "positive"},
        ],
        "metadata": {
            "source_date": "2026-03-27",
            "total_articles": 3,
            "watchlist": WATCHLIST,
        },
    }
    return dummy_graph
    # ── 더미 데이터 끝 ───────────────────────────────────────────────────────
