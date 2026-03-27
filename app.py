"""
🚀 투자 인사이트 자동화 에이전트 - MVP (Streamlit)
지식 그래프 기반 금융 투자 자동 분석 시스템 | 단일 파일 완성 버전
"""

import json
from typing import Dict, List, Any
from datetime import datetime

import streamlit as st

# ============================================================================
# 설정 및 상수
# ============================================================================

# 샘플 뉴스 데이터 (DDGS 설치 불필요)
SAMPLE_NEWS_DATA = {
    "상법 개정 증권주": [
        {
            "title": "상법 개정안, 주주총회 소집 기간 30일→21일로 단축",
            "body": "국회를 통과한 상법 개정안이 신속한 기업 의사결정을 가능하게 한다. 증권 거래 절차 간소화로 증권업계에 긍정적 영향 예상. 미래에셋증권, 신한투자증권 등 주요 증권사의 수익성 개선 가능성.",
            "source": "금융뉴스",
        },
        {
            "title": "증권업계, 상법 개정으로 외국인 투자 유입 기대",
            "body": "한국 증권시장의 투명성과 효율성 강화로 외국인 투자자들의 관심 증가. TR ETF 등 증권 섹터 관련 상품의 수급 개선 전망.",
            "source": "투자정보",
        },
    ],
    "미국 AI 빅테크 하락": [
        {
            "title": "미국 AI 빅테크 주가 조정, 테크 섹터 약세",
            "body": "OpenAI, Google, Microsoft 등 주요 AI 관련 기업들의 주가가 조정세를 보이고 있다. 시장의 AI 고평가 우려가 반영된 결과로 분석된다.",
            "source": "미국증시",
        },
        {
            "title": "한국 테크주, 미국 AI 약세의 여파 받을 가능성",
            "body": "SK하이닉스, 삼성전자 등 한국 반도체 기업의 실적 전망이 불투명해질 수 있다. 단기간 기술주 조정 가능성 높음.",
            "source": "국내증시",
        },
    ],
}

WATCHLIST = list(SAMPLE_NEWS_DATA.keys())

# ============================================================================
# Streamlit 페이지 설정
# ============================================================================

st.set_page_config(
    page_title="투자 인사이트 AI 브리핑",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.title("🚀 오늘의 포트폴리오 AI 브리핑")
st.markdown("---")

# ============================================================================
# 세션 상태 초기화
# ============================================================================

if "search_results" not in st.session_state:
    st.session_state.search_results = None
if "agent1_output" not in st.session_state:
    st.session_state.agent1_output = None
if "agent2_output" not in st.session_state:
    st.session_state.agent2_output = None
if "is_running" not in st.session_state:
    st.session_state.is_running = False

# ============================================================================
# Agent 0: 뉴스 검색 (샘플 데이터 - DDGS 불필요)
# ============================================================================

def search_news(keywords: List[str]) -> str:
    """
    주어진 키워드 리스트에 대해 샘플 뉴스를 반환.
    
    Args:
        keywords: 검색 키워드 리스트
        
    Returns:
        통합된 뉴스 텍스트 문자열
    """
    all_news = []
    
    with st.spinner("📰 뉴스 데이터 준비 중..."):
        for keyword in keywords:
            st.write(f"  ▶ '{keyword}' 데이터 로딩...")
            
            if keyword in SAMPLE_NEWS_DATA:
                for news_item in SAMPLE_NEWS_DATA[keyword]:
                    all_news.append({
                        "title": news_item.get("title", ""),
                        "body": news_item.get("body", ""),
                        "source": news_item.get("source", ""),
                        "keyword": keyword,
                    })
    
    # 모든 뉴스를 하나의 문자열로 합치기
    news_text = "\n---\n".join(
        [f"[{item['keyword']}] {item['title']}\n{item['body']}" for item in all_news]
    )
    
    return news_text

# 샘플 그래프 데이터
SAMPLE_GRAPH_DATA = {
    "nodes": [
        {"id": "n1", "name": "상법 개정", "type": "Regulation"},
        {"id": "n2", "name": "주주총회 절차 단축", "type": "Regulation"},
        {"id": "n3", "name": "증권업", "type": "Sector"},
        {"id": "n4", "name": "미래에셋증권", "type": "Company"},
        {"id": "n5", "name": "신한투자증권", "type": "Company"},
        {"id": "n6", "name": "외국인 투자", "type": "Investor"},
        {"id": "n7", "name": "AI 기업 조정", "type": "Sector"},
        {"id": "n8", "name": "반도체", "type": "Sector"},
        {"id": "n9", "name": "SK하이닉스", "type": "Company"},
        {"id": "n10", "name": "삼성전자", "type": "Company"},
    ],
    "edges": [
        {"source": "n1", "target": "n2", "type": "CATALYZES", "confidence": 0.95},
        {"source": "n2", "target": "n3", "type": "BENEFITS_FROM", "confidence": 0.90},
        {"source": "n3", "target": "n4", "type": "TRADES", "confidence": 0.85},
        {"source": "n3", "target": "n5", "type": "TRADES", "confidence": 0.85},
        {"source": "n2", "target": "n6", "type": "AFFECTS", "confidence": 0.80},
        {"source": "n7", "target": "n8", "type": "AFFECTS", "confidence": 0.85},
        {"source": "n8", "target": "n9", "type": "TRADES", "confidence": 0.88},
        {"source": "n8", "target": "n10", "type": "TRADES", "confidence": 0.88},
    ]
}

# ============================================================================
# Agent 1: 그래프 추출 (샘플 데이터)
# ============================================================================

def extract_graph_from_news(news_text: str) -> Dict[str, Any]:
    """
    뉴스 텍스트에서 그래프 데이터(노드와 엣지)를 추출 (샘플 데이터 반환).
    
    Args:
        news_text: 통합된 뉴스 텍스트
        
    Returns:
        노드와 엣지를 포함한 JSON 딕셔너리
    """
    
    if not news_text.strip():
        st.warning("⚠️ 검색된 뉴스가 없습니다.")
        return {"nodes": [], "edges": []}
    
    with st.spinner("🔗 그래프 데이터 추출 중..."):
        import time
        time.sleep(1)  # 처리 시뮬레이션
        
        st.success(f"✅ {len(SAMPLE_GRAPH_DATA.get('nodes', []))}개 노드, {len(SAMPLE_GRAPH_DATA.get('edges', []))}개 엣지 추출 완료")
        return SAMPLE_GRAPH_DATA

# 샘플 투자 분석 리포트
SAMPLE_INVESTMENT_REPORT = """
## 📊 핵심 인사이트

상법 개정으로 주주총회 소집 기간이 30일에서 21일로 단축되면서 **회사 의사결정 프로세스의 효율성이 대폭 향상**될 것으로 전망됩니다. 
이는 증권시장의 투명성 강화로 이어지며, 특히 **외국인 투자자들의 관심을 증가**시킬 수 있는 긍정적 신호입니다.
동시에 미국 AI 빅테크의 조정 여파로 한국 반도체 기업들이 단기적 조정압에 직면할 가능성을 인지해야 합니다.

---

## 🔗 영향 경로 분석

**긍정 경로 (상법 개정):**
- 상법 개정 → 주주총회 절차 단축 → 증권업 수익성 개선
- 절차 간소화 → 외국인 투자 유입 증가 → ETF 등 금융상품 수급 개선

**부정 경로 (AI 기업 조정):**
- 미국 AI 빅테크 약세 → 반도체 실적 전망 불투명 → SK하이닉스, 삼성전자 주가 압박

---

## 💼 투자 제안

### 추천 액션:
1. **증권주 롱 포지션** - 미래에셋증권, 신한투자증권 등 중점 보유
   - 상법 개정의 직접적 수혜 예상
   - 기간: 중기 (3-6개월)

2. **반도체주 헤징** - 옷 좋은 타이밍에서 차등 매매 추진
   - 미국 AI 조정의 영향 제한
   - 기간: 단기 (1-3개월)

3. **금융ETF 롱** - 증권 섹터 관련 ETF 추가 매수
   - 외국인 투자 유입 활용
   - 기간: 중기

---

## ⚠️ 리스크 팩터

| 리스크 | 확률 | 영향도 | 대응 방안 |
|--------|------|--------|----------|
| 미국 경제 둔화 가속화 | 높음 | 고 | 반도체주 익절 시점 단축 |
| 상법 개정 지연/유보 | 중간 | 중 | 증권주 이익 실현 계획 수립 |
| 글로벌 금리 인상 재개 | 중간 | 중 | 포트폴리오 밸런싱 검토 |

---

## 📈 성공 가능성 평가

- **상법 개정 수혜 실현율:** **85%** (정책 확정도 높음)
- **외국인 투자 유입:** **78%** (시장 심리 변수 존재)
- **반도체 조정 지속:** **72%** (단기 기술적 조정 우려)

**포트폴리오 수익률 전망 (중기):** +4.5% ~ +8.2%

### 최종 평가: ⭐⭐⭐⭐ (4/5) - 온건한 매수 추천

---

*분석 기준일: {date}*  
*면책조항: 본 리포트는 샘플 분석이며 투자 조언이 아닙니다.*
""".format(date=datetime.now().strftime('%Y-%m-%d'))

# ============================================================================
# Agent 2: 투자 분석 리포트 (샘플 템플릿)
# ============================================================================

def generate_investment_report(graph_data: Dict[str, Any], original_news: str) -> str:
    """
    그래프 데이터와 뉴스를 바탕으로 투자 분석 리포트 생성 (샘플 리포트 반환).
    
    Args:
        graph_data: Agent 1에서 추출한 그래프 데이터
        original_news: 원본 뉴스 텍스트
        
    Returns:
        마크다운 형식의 투자 분석 리포트
    """
    
    with st.spinner("📋 투자 분석 리포트 생성 중..."):
        import time
        time.sleep(1)  # 처리 시뮬레이션
        
        st.success("✅ 분석 리포트 생성 완료")
        return SAMPLE_INVESTMENT_REPORT

# ============================================================================
# 메인 워크플로우
# ============================================================================

def run_analysis():
    """통합 분석 워크플로우 실행"""
    st.session_state.is_running = True
    
    try:
        # Step 1: Agent 0 - 뉴스 검색
        st.subheader("📰 Step 1: 뉴스 데이터 수집")
        news_text = search_news(WATCHLIST)
        st.session_state.search_results = news_text
        
        if not news_text.strip():
            st.error("❌ 검색된 뉴스가 없어 분석을 진행할 수 없습니다.")
            st.session_state.is_running = False
            return
        
        st.success(f"✅ {len(news_text)} 글자의 뉴스 수집 완료")
        
        # Step 2: Agent 1 - 그래프 추출
        st.subheader("🔗 Step 2: 지식 그래프 추출")
        graph_data = extract_graph_from_news(news_text)
        st.session_state.agent1_output = graph_data
        
        if not graph_data.get("nodes"):
            st.warning("⚠️ 추출된 그래프 데이터가 없습니다.")
        
        # Step 3: Agent 2 - 투자 분석 리포트
        st.subheader("📋 Step 3: 투자 분석 리포트 생성")
        report = generate_investment_report(graph_data, news_text)
        st.session_state.agent2_output = report
        
        st.success("✅ 모든 분석 완료!")
        
    except Exception as e:
        st.error(f"❌ 분석 중 예상치 못한 오류 발생: {str(e)}")
        
    finally:
        st.session_state.is_running = False

# ============================================================================
# UI 레이아웃
# ============================================================================

# 중앙 버튼
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    if st.button(
        "🚀 오늘의 포트폴리오 AI 브리핑 생성",
        key="main_button",
        disabled=st.session_state.is_running,
        use_container_width=True,
    ):
        run_analysis()

st.markdown("---")

# 결과 출력 레이아웃
if st.session_state.agent1_output or st.session_state.agent2_output:
    col_left, col_right = st.columns(2)
    
    # 좌측: 그래프 데이터 (JSON)
    with col_left:
        st.subheader("📊 지식 그래프 (JSON)")
        if st.session_state.agent1_output:
            st.json(st.session_state.agent1_output)
        else:
            st.info("그래프 데이터가 없습니다.")
    
    # 우측: 투자 분석 리포트 (마크다운)
    with col_right:
        st.subheader("📋 투자 분석 리포트")
        if st.session_state.agent2_output:
            st.markdown(st.session_state.agent2_output)
        else:
            st.info("리포트가 없습니다.")

# 푸터
st.markdown("---")
st.markdown(
    f"**생성 시간:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
    f"**데이터 소스:** 샘플 데이터 | "
    f"**상태:** ✅ API 키 불필요 (완전 오프라인 모드)"
)

# ============================================================================
# 종료
# ============================================================================

if __name__ == "__main__":
    pass
