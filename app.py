"""
투자 인사이트 자동화 에이전트 — B2B (증권사 리서치팀용)
사용자가 검색어를 입력하면 실시간 뉴스를 수집하고 DB에 누적합니다.
"""

import json
from datetime import datetime
from typing import List

import streamlit as st

from db import init_db, get_stats
from extractor import fetch_news_by_keywords, auto_fetch_daily_news, run_agent1_extractor
from analyzer import run_agent2_analyzer

# ============================================================================
# 초기화
# ============================================================================

init_db()

st.set_page_config(
    page_title="리서치 AI 브리핑",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# 사이드바 — 사용자 설정 & DB 현황
# ============================================================================

with st.sidebar:
    st.header("⚙️ 설정")
    user_tag = st.text_input("사용자 ID (팀/담당자)", value="analyst_01")
    max_per_keyword = st.slider("키워드당 수집 기사 수", 3, 20, 5)

    st.divider()
    st.header("📦 누적 DB 현황")

    stats = get_stats()
    st.metric("총 수집 기사", stats["total_articles"])
    st.metric("총 검색 횟수", stats["total_searches"])

    if stats["by_keyword"]:
        st.subheader("키워드별 기사 수")
        for row in stats["by_keyword"]:
            st.write(f"- **{row['keyword']}**: {row['cnt']}건")

# ============================================================================
# 메인 — 검색어 입력
# ============================================================================

st.title("📊 리서치 AI 브리핑")
st.caption("검색어를 입력하면 실시간 뉴스를 수집하고 DB에 누적합니다.")
st.markdown("---")

col_input, col_btn = st.columns([4, 1])

with col_input:
    raw_keywords = st.text_input(
        "검색 키워드 (쉼표로 구분)",
        placeholder="예: 삼성전자, AI 반도체, 금리 인상",
        label_visibility="collapsed",
    )

with col_btn:
    search_clicked = st.button("🔍 뉴스 수집", use_container_width=True)

# ============================================================================
# 뉴스 수집 실행
# ============================================================================

if search_clicked:
    keywords: List[str] = [k.strip() for k in raw_keywords.split(",") if k.strip()]

    if not keywords:
        st.warning("키워드를 하나 이상 입력해주세요.")
    else:
        st.markdown("---")
        st.subheader("📰 뉴스 수집 결과")

        with st.spinner(f"'{', '.join(keywords)}' 관련 뉴스 수집 중..."):
            articles = fetch_news_by_keywords(
                keywords,
                max_per_keyword=max_per_keyword,
                user_tag=user_tag,
            )

        if not articles:
            st.error("수집된 뉴스가 없습니다. 키워드를 변경해보세요.")
        else:
            st.success(f"✅ {len(articles)}건 수집 완료 (DB 저장 포함)")

            # 키워드별 탭으로 결과 표시
            tabs = st.tabs(keywords)
            for tab, kw in zip(tabs, keywords):
                with tab:
                    kw_articles = [a for a in articles if a.get("keyword") == kw]
                    if not kw_articles:
                        st.info("해당 키워드 결과 없음")
                        continue
                    for a in kw_articles:
                        with st.expander(f"📄 {a['title']}", expanded=False):
                            st.write(a.get("body", ""))
                            col1, col2 = st.columns(2)
                            col1.caption(f"출처: {a.get('source', '-')}")
                            col2.caption(f"날짜: {a.get('date', '-')}")
                            if a.get("url"):
                                st.markdown(f"[원문 보기]({a['url']})")

# ============================================================================
# AI 분석 섹션
# ============================================================================

st.markdown("---")
st.subheader("🤖 AI 브리핑 생성")
st.caption("DB에 누적된 뉴스 전체를 기반으로 지식 그래프와 투자 리포트를 생성합니다.")

if st.button("🚀 AI 브리핑 생성", use_container_width=False):
    with st.spinner("뉴스 → 지식 그래프 → 투자 리포트 생성 중..."):
        news_text = auto_fetch_daily_news()

    if not news_text:
        st.warning("DB에 수집된 뉴스가 없습니다. 먼저 뉴스를 수집해주세요.")
    else:
        with st.spinner("지식 그래프 추출 중..."):
            graph_data = run_agent1_extractor(news_text)

        with st.spinner("투자 리포트 생성 중..."):
            report = run_agent2_analyzer(graph_data)

        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("🔗 지식 그래프 (JSON)")
            st.json(graph_data)

        with col_right:
            st.subheader("📋 투자 분석 리포트")
            st.markdown(report)

# ============================================================================
# 푸터
# ============================================================================

st.markdown("---")
st.caption(
    f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
    f"사용자: {user_tag}"
)
