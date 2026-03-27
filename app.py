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
from graph_builder import build_graph_from_new_articles, render_full_graph_with_highlight

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
# 사이드바 — DB 현황만 표시
# ============================================================================

with st.sidebar:
    st.header("📦 DB 현황")
    stats = get_stats()
    g_stats = get_graph_stats()

    c1, c2 = st.columns(2)
    c1.metric("수집 기사", stats["total_articles"])
    c2.metric("검색 횟수", stats["total_searches"])
    c3, c4 = st.columns(2)
    c3.metric("그래프 노드", g_stats["node_count"])
    c4.metric("그래프 엣지", g_stats["edge_count"])
    c5, c6 = st.columns(2)
    c5.metric("근거 문장", g_stats.get("evidence_count", 0))
    c6.metric("별칭 등록", g_stats.get("alias_count", 0))

    if g_stats.get("by_category"):
        st.divider()
        st.caption("📂 관계 카테고리별")
        cat_kr = {"SUPPLY_CHAIN":"공급망","FINANCIAL":"재무","REGULATORY":"규제",
                  "CAUSAL":"인과","MARKET":"시장","ORGANIZATIONAL":"조직"}
        for r in g_stats["by_category"]:
            label = cat_kr.get(r["relation_category"], r["relation_category"] or "기타")
            st.write(f"- {label}: {r['cnt']}개")

    if g_stats["top_nodes"]:
        st.divider()
        st.caption("🔥 핵심 노드 Top 10")
        for n in g_stats["top_nodes"]:
            score = n.get("sentiment_score", 0)
            badge = "🟢" if score > 0.1 else "🔴" if score < -0.1 else "⚪"
            st.write(f"- {badge} **{n['label']}** `{n['type']}` {n['mention_count']}회")

# ============================================================================
# 탭
# ============================================================================

tab_search, tab_full, tab_report = st.tabs(["🔍 키워드 분석", "🌐 전체 그래프", "📋 AI 리포트"])

# ============================================================================
# TAB 1: 키워드 분석 (검색 → 수집 → 그래프 업데이트 → 누적 그래프 하이라이트)
# ============================================================================

with tab_search:
    st.title("🔍 키워드 분석")
    st.caption("기업명 또는 섹터를 입력하면 뉴스를 수집하고 누적 그래프에서 연관 영향관계를 강조 표시합니다.")

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

        # ── Step 1: 뉴스 수집 ─────────────────────────────────────────────
        with st.status(f"**Step 1** · '{kw}' 뉴스 수집 중...", expanded=True) as status:
            articles = fetch_news_by_keywords([kw])
            status.update(
                label=f"**Step 1** · 뉴스 {len(articles)}건 수집 완료 (30건 수집 → 중복 제거)",
                state="complete",
            )

        # ── Step 2: 그래프 업데이트 ───────────────────────────────────────
        with st.status("**Step 2** · 그래프 업데이트 중...", expanded=True) as status:
            result = build_graph_from_new_articles()
            status.update(
                label=f"**Step 2** · 노드 +{result['new_nodes']} · 엣지 +{result['new_edges']} 추가됨",
                state="complete",
            )

        # ── Step 3: 누적 그래프에서 키워드 하이라이트 ─────────────────────
        st.subheader(f"🔗 누적 그래프 — '{kw}' 강조")
        graph_html, neighborhood = render_full_graph_with_highlight(kw, height=580)

        if not neighborhood.get("center_nodes"):
            st.warning(f"그래프에서 '{kw}'와 일치하는 노드를 찾지 못했습니다.")
            components.html(graph_html, height=600, scrolling=False)
        else:
            components.html(graph_html, height=600, scrolling=False)

            # ── 영향관계 테이블 ───────────────────────────────────────────
            ALLOWED_TYPES = {"Company", "Event", "Sector"}

            RELATION_DESC = {
                "AFFECTS":      {"positive": "긍정적 영향을 미침",     "negative": "부정적 영향을 미침",   "neutral": "영향을 미침"},
                "CATALYZES":    {"positive": "성장·확대를 촉진",        "negative": "위축·둔화를 촉진",     "neutral": "변화를 유발"},
                "IMPACTS":      {"positive": "실적·가치 개선에 기여",   "negative": "실적·가치에 타격",     "neutral": "영향을 줌"},
                "BENEFITS_FROM":{"positive": "수혜 기대",               "negative": "역풍 우려",            "neutral": "연관됨"},
                "TRADES":       {"positive": "거래량 확대 기대",        "negative": "거래 위축 우려",       "neutral": "거래 관계"},
                "SUPPLIES_TO":  {"positive": "공급 확대·수주 기대",     "negative": "공급 축소 우려",       "neutral": "공급 관계"},
                "PRODUCES":     {"positive": "생산 확대·신제품 출시",   "negative": "생산 차질 우려",       "neutral": "생산 관계"},
                "COMPETES_WITH":{"positive": "경쟁 우위 확보",          "negative": "경쟁 심화 압박",       "neutral": "경쟁 관계"},
                "REGULATES":    {"positive": "규제 완화·혜택",          "negative": "규제 강화·제약",       "neutral": "규제 관계"},
                "INVESTS_IN":   {"positive": "투자 확대·자금 유입",     "negative": "투자 회수 우려",       "neutral": "투자 관계"},
            }

            def describe(relation: str, sentiment: str) -> str:
                desc = RELATION_DESC.get(relation, {}).get(sentiment)
                if desc:
                    return desc
                # 알 수 없는 relation은 감성으로만
                return {"positive": "긍정적 연관", "negative": "부정적 연관"}.get(sentiment, "연관 관계")

            def sentiment_badge(s: str) -> str:
                return "🟢 긍정" if s == "positive" else "🔴 부정" if s == "negative" else "⚪ 중립"

            def build_rows(items, limit=6):
                filtered = [n for n in items if n.get("type") in ALLOWED_TYPES]
                return [
                    {
                        "이름": n["label"],
                        "구분": n["type"],
                        "영향": sentiment_badge(n["sentiment"]),
                        "설명": describe(n["relation"], n["sentiment"]),
                    }
                    for n in filtered[:limit]
                ]

            st.subheader("📊 영향 관계 분석")
            col_in, col_out = st.columns(2)

            with col_in:
                st.markdown(f"#### ⬅️ **{kw}** 에 영향을 주는 요소")
                rows_in = build_rows(neighborhood["inbound"])
                if rows_in:
                    st.dataframe(pd.DataFrame(rows_in), use_container_width=True, hide_index=True)
                else:
                    st.info("분석된 영향 요소 없음")

            with col_out:
                st.markdown(f"#### ➡️ **{kw}** 이 영향을 주는 요소")
                rows_out = build_rows(neighborhood["outbound"])
                if rows_out:
                    st.dataframe(pd.DataFrame(rows_out), use_container_width=True, hide_index=True)
                else:
                    st.info("분석된 영향 요소 없음")

        # ── 수집된 뉴스 목록 ──────────────────────────────────────────────
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
# TAB 2: 전체 누적 그래프
# ============================================================================

with tab_full:
    st.title("🌐 전체 누적 그래프")
    st.caption("모든 검색으로 누적된 전체 그래프입니다. 검색할수록 그래프가 확장됩니다.")

    g_stats_now = get_graph_stats()
    if g_stats_now["node_count"] == 0:
        st.warning("그래프 데이터가 없습니다. '🔍 키워드 분석' 탭에서 먼저 분석을 실행하세요.")
    else:
        st.markdown(f"**노드 {g_stats_now['node_count']}개 · 엣지 {g_stats_now['edge_count']}개**")
        graph_html, _ = render_full_graph_with_highlight(keyword=None, height=680)
        components.html(graph_html, height=700, scrolling=False)

        st.subheader("🔥 핵심 노드 Top 10")
        top_df = pd.DataFrame(g_stats_now["top_nodes"])
        if not top_df.empty:
            top_df.columns = ["노드명", "타입", "언급 수"]
            st.dataframe(top_df, use_container_width=True, hide_index=True)

# ============================================================================
# TAB 3: AI 리포트
# ============================================================================

with tab_report:
    st.title("📋 AI 투자 브리핑")
    st.caption("누적 그래프와 관련 뉴스를 근거로 LLM이 리포트를 생성합니다. 할루시네이션 없이 그래프 경로를 명시합니다.")

    report_query = st.text_input(
        "분석 대상 (선택)",
        placeholder="예: 반도체 / LG화학 / 금리 — 비워두면 전체 그래프 기반",
        label_visibility="visible",
    )

    if st.button("🚀 AI 브리핑 생성", type="primary"):
        from db import get_graph_data as get_full_graph
        from graph_builder import get_node_neighborhood

        with st.spinner("그래프 컨텍스트 탐색 중..."):
            if report_query.strip():
                # 쿼리 키워드 중심 서브그래프 탐색
                neighborhood = get_node_neighborhood(report_query.strip())
                graph_data = {
                    "nodes": neighborhood["nodes"],
                    "edges": neighborhood["edges"],
                    "metadata": {"query": report_query.strip()},
                }
            else:
                # 전체 그래프 사용
                full = get_full_graph()
                graph_data = {
                    "nodes": full["nodes"][:40],  # 상위 40개 노드
                    "edges": full["edges"][:60],
                    "metadata": {"query": "전체 시장"},
                }

        if not graph_data["nodes"]:
            st.warning("그래프에서 관련 노드를 찾지 못했습니다. 먼저 키워드 분석을 실행하세요.")
        else:
            st.info(f"그래프 탐색 완료 — 노드 {len(graph_data['nodes'])}개 · 엣지 {len(graph_data['edges'])}개 기반으로 분석")

            with st.spinner("Graph RAG 리포트 생성 중..."):
                report = run_agent2_analyzer(graph_data)

            st.markdown(report)

            with st.expander("🔍 사용된 그래프 컨텍스트 보기"):
                from graph_builder import build_rag_context
                st.text(build_rag_context(graph_data, query=graph_data["metadata"].get("query", "")))

# ============================================================================
# 푸터
# ============================================================================

st.markdown("---")
st.caption(f"업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
