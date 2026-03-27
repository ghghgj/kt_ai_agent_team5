"""
투자 인사이트 자동화 에이전트 — B2B (증권사 리서치팀용)
"""

import streamlit.components.v1 as components
from datetime import datetime

import streamlit as st
import pandas as pd

import os
from openai import OpenAI

from db import init_db, get_stats, get_graph_stats
from extractor import fetch_news_by_keywords, auto_fetch_daily_news, run_agent1_extractor
from analyzer import run_agent2_analyzer
from graph_builder import build_graph_from_new_articles, render_full_graph_with_highlight


def is_valid_finance_keyword(keyword: str) -> bool:
    """키워드가 증권/투자 리서치와 관련 있는지 LLM으로 판단합니다."""
    try:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "당신은 증권사 리서치 서비스의 키워드 필터입니다.\n"
                        "아래 기준으로 'yes' 또는 'no'만 반환하세요.\n\n"
                        "yes (허용): 상장기업명, 산업섹터(반도체/철강/바이오 등), "
                        "금융지표(금리/환율/유가 등), 거시경제 이슈, 규제·정책, "
                        "투자 관련 사건·이슈\n\n"
                        "no (차단): 스포츠팀, 연예인, 드라마·영화, 음식, 여행, "
                        "게임, 정치인 이름(금융 무관), 일반 생활 키워드\n\n"
                        "반드시 'yes' 또는 'no' 한 단어만 반환."
                    ),
                },
                {"role": "user", "content": keyword},
            ],
            temperature=0,
            max_tokens=5,
        )
        return resp.choices[0].message.content.strip().lower().startswith("yes")
    except Exception:
        return True  # API 오류 시 통과

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

        with st.spinner("키워드 유효성 확인 중..."):
            valid = is_valid_finance_keyword(kw)

        if not valid:
            st.error(f"**'{kw}'** 에 대한 해당 정보가 없습니다.\n\n증권·투자와 관련된 기업명, 섹터, 경제 지표 등을 입력해주세요.\n예: 삼성전자, 반도체, 금리, 환율, 이차전지")
            st.stop()

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
            result = build_graph_from_new_articles(keyword=kw)
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

            # ── 간접 섹터 영향 분석 ──────────────────────────────────────
            from graph_builder import get_indirect_sector_influences

            def _llm_explain_influences(kw: str, items: list, direction: str) -> list[str]:
                """간접 영향 항목들을 한 번의 LLM 호출로 설명 생성"""
                if not items:
                    return []
                client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
                dir_label = f"'{kw}'에 간접적으로 영향을 주는" if direction == "inbound" else f"'{kw}'가 간접적으로 영향을 미치는"
                items_text = "\n".join([
                    f"{i+1}. 경로: {' → '.join(inf['path'])}  (관계: {inf['direct_relation']} → {inf['mid_relation']}, 감성: {inf['sentiment']})"
                    for i, inf in enumerate(items)
                ])
                prompt = f"""증권 투자 분석 관점에서 {dir_label} 섹터들의 영향 메커니즘을 설명하세요.

{items_text}

각 경로에 대해 2~3문장으로 구체적인 경제·시장 연쇄 메커니즘을 설명하세요.
JSON 형식으로만 반환: {{"explanations": ["경로1 설명", "경로2 설명"]}}"""
                try:
                    resp = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=400,
                        response_format={"type": "json_object"},
                    )
                    import json
                    data = json.loads(resp.choices[0].message.content)
                    return data.get("explanations", [])
                except Exception:
                    return ["설명을 생성하지 못했습니다."] * len(items)

            def _render_influence_cards(items: list, explanations: list, direction: str):
                badge_map = {"positive": "🟢 긍정", "negative": "🔴 부정", "neutral": "⚪ 중립"}
                for i, inf in enumerate(items):
                    badge  = badge_map.get(inf["sentiment"], "⚪")
                    path_str = " → ".join(inf["path"])
                    explanation = explanations[i] if i < len(explanations) else ""
                    st.markdown(
                        f"""<div style="background:#1e2130;border-radius:10px;padding:14px 16px;margin-bottom:10px;border-left:4px solid {'#10B981' if inf['sentiment']=='positive' else '#EF4444' if inf['sentiment']=='negative' else '#6B7280'}">
                        <div style="font-size:15px;font-weight:bold;color:#fff;margin-bottom:4px">{badge} &nbsp;{inf['sector_label']}</div>
                        <div style="font-size:11px;color:#9CA3AF;margin-bottom:8px">경로: {path_str}</div>
                        <div style="font-size:13px;color:#D1D5DB;line-height:1.6">{explanation}</div>
                        </div>""",
                        unsafe_allow_html=True,
                    )

            st.subheader("📊 간접 섹터 영향 분석")
            with st.spinner("간접 영향 경로 분석 중..."):
                indirect = get_indirect_sector_influences(kw, max_results=3)
                col_in, col_out = st.columns(2)

                with col_in:
                    st.markdown(f"#### ⬅️ **{kw}** 에 간접 영향을 주는 섹터")
                    if indirect["inbound"]:
                        expls = _llm_explain_influences(kw, indirect["inbound"], "inbound")
                        _render_influence_cards(indirect["inbound"], expls, "inbound")
                    else:
                        st.info("간접 영향 섹터를 찾지 못했습니다.")

                with col_out:
                    st.markdown(f"#### ➡️ **{kw}** 이 간접 영향을 주는 섹터")
                    if indirect["outbound"]:
                        expls = _llm_explain_influences(kw, indirect["outbound"], "outbound")
                        _render_influence_cards(indirect["outbound"], expls, "outbound")
                    else:
                        st.info("간접 영향 섹터를 찾지 못했습니다.")

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
            top_df.columns = ["노드명", "타입", "언급 수", "감성점수"]
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
