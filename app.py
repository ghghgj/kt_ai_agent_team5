"""
투자 인사이트 자동화 에이전트 — B2B (증권사 리서치팀용)
사용자가 검색어를 입력하면 실시간 뉴스를 수집하고 DB에 누적합니다.
"""

import streamlit.components.v1 as components
from datetime import datetime
from typing import List

import streamlit as st

from db import init_db, get_stats, get_graph_stats
from extractor import fetch_news_by_keywords, auto_fetch_daily_news, run_agent1_extractor
from analyzer import run_agent2_analyzer
from graph_builder import build_graph_from_new_articles, render_interactive_graph

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
    g_stats = get_graph_stats()

    col1, col2 = st.columns(2)
    col1.metric("총 수집 기사", stats["total_articles"])
    col2.metric("총 검색 횟수", stats["total_searches"])

    col3, col4 = st.columns(2)
    col3.metric("그래프 노드", g_stats["node_count"])
    col4.metric("그래프 엣지", g_stats["edge_count"])

    if g_stats["top_nodes"]:
        st.subheader("🔥 핵심 노드 Top 10")
        for n in g_stats["top_nodes"]:
            st.write(f"- **{n['label']}** ({n['type']}) — {n['mention_count']}회")

# ============================================================================
# 탭 레이아웃
# ============================================================================

tab_news, tab_graph, tab_report = st.tabs(["📰 뉴스 수집", "🔗 지식 그래프", "📋 AI 리포트"])

# ============================================================================
# TAB 1: 뉴스 수집
# ============================================================================

with tab_news:
    st.title("📰 뉴스 수집")
    st.caption("검색어를 입력하면 실시간 뉴스를 수집하고 DB에 누적합니다.")

    col_input, col_btn = st.columns([4, 1])
    with col_input:
        raw_keywords = st.text_input(
            "검색 키워드 (쉼표로 구분)",
            placeholder="예: 삼성전자, AI 반도체, 금리 인상",
            label_visibility="collapsed",
        )
    with col_btn:
        search_clicked = st.button("🔍 뉴스 수집", use_container_width=True)

    if search_clicked:
        keywords: List[str] = [k.strip() for k in raw_keywords.split(",") if k.strip()]
        if not keywords:
            st.warning("키워드를 하나 이상 입력해주세요.")
        else:
            with st.spinner(f"'{', '.join(keywords)}' 관련 뉴스 수집 중..."):
                articles = fetch_news_by_keywords(
                    keywords,
                    max_per_keyword=max_per_keyword,
                    user_tag=user_tag,
                )

            if not articles:
                st.error("수집된 뉴스가 없습니다. 키워드를 변경해보세요.")
            else:
                st.success(f"✅ {len(articles)}건 수집 완료 — DB 저장 및 그래프 처리 대기 중")

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
                                c1, c2 = st.columns(2)
                                c1.caption(f"출처: {a.get('source', '-')}")
                                c2.caption(f"날짜: {a.get('date', '-')}")
                                if a.get("url"):
                                    st.markdown(f"[원문 보기]({a['url']})")

# ============================================================================
# TAB 2: 지식 그래프
# ============================================================================

with tab_graph:
    st.title("🔗 지식 그래프")
    st.caption("DB에 누적된 뉴스에서 기업·이슈·규제·인과관계를 추출한 그래프입니다. 데이터가 쌓일수록 자동 확장됩니다.")

    col_build, col_info = st.columns([1, 3])
    with col_build:
        build_clicked = st.button("⚙️ 그래프 업데이트", use_container_width=True)
    with col_info:
        unprocessed = stats["total_articles"] - g_stats.get("processed_count", 0)
        st.info(f"총 {stats['total_articles']}건 중 미처리 기사가 있으면 업데이트하세요.")

    if build_clicked:
        progress_bar = st.progress(0, text="그래프 추출 시작...")

        def update_progress(current, total, title):
            pct = int((current / total) * 100) if total else 0
            short_title = title[:40] + "..." if len(title) > 40 else title
            progress_bar.progress(pct, text=f"[{current+1}/{total}] {short_title}")

        with st.spinner("OpenAI로 엔티티·관계 추출 중..."):
            result = build_graph_from_new_articles(progress_callback=update_progress)

        progress_bar.progress(100, text="완료!")

        if result["processed"] == 0:
            st.info("새로 처리할 기사가 없습니다.")
        else:
            st.success(
                f"✅ {result['processed']}건 처리 | "
                f"노드 +{result['new_nodes']} | "
                f"엣지 +{result['new_edges']}"
            )
        st.rerun()

    # 그래프 시각화
    g_stats_now = get_graph_stats()
    if g_stats_now["node_count"] == 0:
        st.warning("그래프 데이터가 없습니다. '⚙️ 그래프 업데이트'를 먼저 실행하세요.")
    else:
        st.markdown(f"**노드 {g_stats_now['node_count']}개 · 엣지 {g_stats_now['edge_count']}개**")

        # 필터 옵션
        with st.expander("🎛️ 필터 옵션"):
            from db import get_graph_data
            all_types = list({n["type"] for n in get_graph_data()["nodes"]})
            selected_types = st.multiselect("노드 타입 필터", all_types, default=all_types)

        graph_html = render_interactive_graph(height=680)
        components.html(graph_html, height=700, scrolling=False)

        # 하단 핵심 노드 테이블
        st.subheader("🔥 핵심 노드 (언급 빈도순)")
        import pandas as pd
        top_df = pd.DataFrame(g_stats_now["top_nodes"])
        if not top_df.empty:
            top_df.columns = ["노드명", "타입", "언급 수"]
            st.dataframe(top_df, use_container_width=True, hide_index=True)

# ============================================================================
# TAB 3: AI 리포트
# ============================================================================

with tab_report:
    st.title("📋 AI 투자 브리핑")
    st.caption("DB 누적 뉴스 전체를 기반으로 투자 분석 리포트를 생성합니다.")

    if st.button("🚀 AI 브리핑 생성", use_container_width=False):
        with st.spinner("뉴스 로딩 중..."):
            news_text = auto_fetch_daily_news()

        if not news_text:
            st.warning("DB에 수집된 뉴스가 없습니다. 먼저 뉴스를 수집해주세요.")
        else:
            with st.spinner("지식 그래프 추출 중..."):
                graph_data = run_agent1_extractor(news_text)
            with st.spinner("투자 리포트 생성 중..."):
                report = run_agent2_analyzer(graph_data)

            c_left, c_right = st.columns(2)
            with c_left:
                st.subheader("🔗 지식 그래프 (JSON)")
                st.json(graph_data)
            with c_right:
                st.subheader("📋 투자 분석 리포트")
                st.markdown(report)

# ============================================================================
# 푸터
# ============================================================================

st.markdown("---")
st.caption(
    f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 사용자: {user_tag}"
)
