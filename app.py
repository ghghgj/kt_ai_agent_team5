"""
투자 인사이트 자동화 에이전트 — B2B (증권사 리서치팀용)
"""

import streamlit.components.v1 as components
from datetime import datetime

import streamlit as st
import pandas as pd

from db import init_db, get_stats, get_graph_stats
from extractor import fetch_news_by_keywords, auto_fetch_daily_news, run_agent1_extractor
from analyzer import run_agent2_analyzer
from graph_builder import (
    build_graph_from_new_articles,
    render_interactive_graph,
    render_subgraph,
)

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
# 사이드바
# ============================================================================

with st.sidebar:
    st.header("⚙️ 설정")
    user_tag = st.text_input("사용자 ID", value="analyst_01")
    max_per_keyword = st.slider("키워드당 수집 기사 수", 3, 20, 5)

    st.divider()
    st.header("📦 DB 현황")
    stats = get_stats()
    g_stats = get_graph_stats()

    c1, c2 = st.columns(2)
    c1.metric("수집 기사", stats["total_articles"])
    c2.metric("검색 횟수", stats["total_searches"])
    c3, c4 = st.columns(2)
    c3.metric("그래프 노드", g_stats["node_count"])
    c4.metric("그래프 엣지", g_stats["edge_count"])

    if g_stats["top_nodes"]:
        st.divider()
        st.caption("🔥 핵심 노드 Top 10")
        for n in g_stats["top_nodes"]:
            st.write(f"- **{n['label']}** `{n['type']}` {n['mention_count']}회")

# ============================================================================
# 탭
# ============================================================================

tab_search, tab_full, tab_report = st.tabs(["🔍 키워드 분석", "🌐 전체 그래프", "📋 AI 리포트"])

# ============================================================================
# TAB 1: 키워드 분석 (검색 → 수집 → 그래프 → 영향관계)
# ============================================================================

with tab_search:
    st.title("🔍 키워드 분석")
    st.caption("기업명 또는 섹터를 입력하면 뉴스를 수집하고 연관 영향관계를 그래프로 보여줍니다.")

    col_input, col_btn = st.columns([4, 1])
    with col_input:
        keyword = st.text_input(
            "검색어",
            placeholder="예: 삼성전자 / 반도체 / 금리",
            label_visibility="collapsed",
        )
    with col_btn:
        analyze_clicked = st.button("🔍 분석", use_container_width=True, type="primary")

    if analyze_clicked and keyword.strip():
        kw = keyword.strip()
        st.markdown("---")

        # ── Step 1: 뉴스 수집 ──────────────────────────────────────────────
        with st.status(f"**Step 1** · '{kw}' 뉴스 수집 중...", expanded=True) as status:
            articles = fetch_news_by_keywords(
                [kw],
                max_per_keyword=max_per_keyword,
                user_tag=user_tag,
            )
            status.update(
                label=f"**Step 1** · 뉴스 {len(articles)}건 수집 완료",
                state="complete",
            )

        # ── Step 2: 그래프 업데이트 ────────────────────────────────────────
        with st.status("**Step 2** · 그래프 업데이트 중...", expanded=True) as status:
            result = build_graph_from_new_articles()
            status.update(
                label=f"**Step 2** · 노드 +{result['new_nodes']} · 엣지 +{result['new_edges']} 추가",
                state="complete",
            )

        # ── Step 3: 키워드 중심 서브그래프 시각화 ──────────────────────────
        st.subheader(f"🔗 '{kw}' 연관 그래프")
        graph_html, neighborhood = render_subgraph(kw, height=550)

        if not neighborhood["center_nodes"]:
            st.warning(f"그래프에서 '{kw}'와 일치하는 노드를 찾지 못했습니다. 다른 키워드로 시도해보세요.")
        else:
            components.html(graph_html, height=570, scrolling=False)

            # ── Step 4: 영향관계 테이블 ────────────────────────────────────
            st.subheader("📊 영향 관계 분석")
            col_in, col_out = st.columns(2)

            with col_in:
                st.markdown("#### ⬅️ 이 항목에 영향을 주는 요소")
                st.caption("외부에서 이 노드로 영향이 들어오는 관계")
                if neighborhood["inbound"]:
                    inbound_df = pd.DataFrame([
                        {
                            "노드": n["label"],
                            "타입": n["type"],
                            "관계": n["relation"],
                            "감성": "🟢" if n["sentiment"] == "positive" else "🔴" if n["sentiment"] == "negative" else "⚪",
                        }
                        for n in neighborhood["inbound"]
                    ])
                    st.dataframe(inbound_df, use_container_width=True, hide_index=True)
                else:
                    st.info("영향을 주는 요소 없음")

            with col_out:
                st.markdown("#### ➡️ 이 항목이 영향을 주는 요소")
                st.caption("이 노드에서 외부로 영향이 나가는 관계")
                if neighborhood["outbound"]:
                    outbound_df = pd.DataFrame([
                        {
                            "노드": n["label"],
                            "타입": n["type"],
                            "관계": n["relation"],
                            "감성": "🟢" if n["sentiment"] == "positive" else "🔴" if n["sentiment"] == "negative" else "⚪",
                        }
                        for n in neighborhood["outbound"]
                    ])
                    st.dataframe(outbound_df, use_container_width=True, hide_index=True)
                else:
                    st.info("영향을 받는 요소 없음")

            # ── 수집된 뉴스 목록 ───────────────────────────────────────────
            if articles:
                with st.expander(f"📰 수집된 뉴스 {len(articles)}건 보기"):
                    for a in articles:
                        st.markdown(f"**{a['title']}**")
                        st.caption(f"{a.get('source', '')} · {a.get('date', '')}")
                        st.write(a.get("body", ""))
                        if a.get("url"):
                            st.markdown(f"[원문]({a['url']})")
                        st.divider()

    elif analyze_clicked:
        st.warning("검색어를 입력해주세요.")

# ============================================================================
# TAB 2: 전체 그래프
# ============================================================================

with tab_full:
    st.title("🌐 전체 지식 그래프")
    st.caption("누적된 모든 뉴스에서 추출된 전체 그래프입니다.")

    if g_stats["node_count"] == 0:
        st.warning("그래프 데이터가 없습니다. '🔍 키워드 분석' 탭에서 먼저 분석을 실행하세요.")
    else:
        st.markdown(f"**노드 {g_stats['node_count']}개 · 엣지 {g_stats['edge_count']}개**")
        graph_html = render_interactive_graph(height=680)
        components.html(graph_html, height=700, scrolling=False)

        st.subheader("🔥 핵심 노드 Top 10")
        top_df = pd.DataFrame(g_stats["top_nodes"])
        if not top_df.empty:
            top_df.columns = ["노드명", "타입", "언급 수"]
            st.dataframe(top_df, use_container_width=True, hide_index=True)

# ============================================================================
# TAB 3: AI 리포트
# ============================================================================

with tab_report:
    st.title("📋 AI 투자 브리핑")
    st.caption("DB 누적 뉴스 전체를 기반으로 투자 분석 리포트를 생성합니다.")

    if st.button("🚀 AI 브리핑 생성"):
        with st.spinner("뉴스 로딩 중..."):
            news_text = auto_fetch_daily_news()

        if not news_text:
            st.warning("DB에 수집된 뉴스가 없습니다.")
        else:
            with st.spinner("그래프 추출 중..."):
                graph_data = run_agent1_extractor(news_text)
            with st.spinner("리포트 생성 중..."):
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
st.caption(f"업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 사용자: {user_tag}")
