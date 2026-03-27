"""
graph_builder.py — 뉴스 → 지식 그래프 추출 (OpenAI) + 인터랙티브 시각화 (pyvis)
뉴스가 누적될수록 그래프가 자동으로 확장됩니다.
"""

import json
import os
import tempfile
from typing import Dict, Any

from openai import OpenAI
from pyvis.network import Network

from db import (
    get_unextracted_articles,
    mark_articles_extracted,
    upsert_node,
    upsert_edge,
    get_graph_data,
)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# 노드 타입별 색상
NODE_COLORS = {
    "Company":    "#4E9AF1",  # 파랑
    "Person":     "#F1A74E",  # 주황
    "Event":      "#E05C5C",  # 빨강
    "Regulation": "#8B5CF6",  # 보라
    "Sector":     "#10B981",  # 초록
    "Product":    "#F59E0B",  # 노랑
    "Macro":      "#6B7280",  # 회색
}

# 감성별 엣지 색상
EDGE_COLORS = {
    "positive": "#10B981",
    "negative": "#EF4444",
    "neutral":  "#9CA3AF",
}

EXTRACTION_PROMPT = """
다음 뉴스 기사에서 증권/투자 분석에 유용한 엔티티와 관계를 추출하세요.

[뉴스]
{text}

[추출 규칙]
- nodes: 기업, 인물, 사건/이슈, 규제/정책, 산업섹터, 제품, 거시지표 중 중요한 것만
- edges: 명확한 인과관계, 영향관계, 거래관계만 포함
- node type은 Company/Person/Event/Regulation/Sector/Product/Macro 중 하나
- sentiment는 증권 관점에서 positive/negative/neutral
- id는 한글 정식 명칭으로 통일 (예: "삼성전자", "미국 연준")
- 노드는 최대 6개, 엣지는 최대 5개

반드시 아래 JSON 형식만 반환하세요:
{{
  "nodes": [
    {{"id": "...", "label": "...", "type": "..."}}
  ],
  "edges": [
    {{"source": "...", "target": "...", "relation": "...", "sentiment": "..."}}
  ]
}}
"""


def extract_graph_from_article(title: str, body: str) -> Dict[str, Any]:
    """단일 기사에서 노드·엣지 추출 (OpenAI 호출)"""
    text = f"{title}\n{body}"
    try:
        response = client.chat.completions.create(
            model=os.environ.get("MODEL_NAME", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "당신은 증권 리서치 전문 지식 그래프 추출 엔진입니다. JSON만 반환합니다."},
                {"role": "user", "content": EXTRACTION_PROMPT.format(text=text)},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        print(f"[LLM 오류] {e}")
        return {"nodes": [], "edges": []}


def build_graph_from_new_articles(progress_callback=None) -> Dict[str, int]:
    """
    미처리 뉴스 기사를 읽어 그래프를 점진적으로 확장합니다.

    Args:
        progress_callback: (current, total, title) → None (Streamlit progress bar용)

    Returns:
        {"processed": int, "new_nodes": int, "new_edges": int}
    """
    articles = get_unextracted_articles(limit=50)
    if not articles:
        return {"processed": 0, "new_nodes": 0, "new_edges": 0}

    processed_ids = []
    total_nodes = 0
    total_edges = 0

    for i, article in enumerate(articles):
        if progress_callback:
            progress_callback(i, len(articles), article["title"])

        result = extract_graph_from_article(article["title"], article.get("body", ""))

        for node in result.get("nodes", []):
            if node.get("id") and node.get("type"):
                upsert_node(node["id"], node.get("label", node["id"]), node["type"])
                total_nodes += 1

        for edge in result.get("edges", []):
            if edge.get("source") and edge.get("target") and edge.get("relation"):
                upsert_edge(
                    edge["source"],
                    edge["target"],
                    edge["relation"],
                    edge.get("sentiment", "neutral"),
                )
                total_edges += 1

        processed_ids.append(article["id"])

    mark_articles_extracted(processed_ids)

    return {
        "processed": len(processed_ids),
        "new_nodes": total_nodes,
        "new_edges": total_edges,
    }


def render_interactive_graph(height: int = 700) -> str:
    """
    DB의 그래프 데이터를 pyvis로 렌더링하여 HTML 문자열 반환.
    Streamlit에서 st.components.v1.html()로 표시합니다.
    """
    data = get_graph_data()
    nodes = data["nodes"]
    edges = data["edges"]

    if not nodes:
        return "<p style='color:white;text-align:center'>그래프 데이터가 없습니다.</p>"

    net = Network(
        height=f"{height}px",
        width="100%",
        bgcolor="#0f1117",
        font_color="#ffffff",
        directed=True,
    )
    net.barnes_hut(gravity=-8000, central_gravity=0.3, spring_length=150)

    # 노드 추가
    max_mention = max((n["mention_count"] for n in nodes), default=1)
    for node in nodes:
        size = 15 + (node["mention_count"] / max_mention) * 35
        color = NODE_COLORS.get(node["type"], "#888888")
        net.add_node(
            node["id"],
            label=node["label"],
            title=f"{node['label']}\n타입: {node['type']}\n언급 수: {node['mention_count']}",
            color=color,
            size=size,
            font={"size": 12, "color": "#ffffff"},
        )

    # 엣지 추가
    existing_node_ids = {n["id"] for n in nodes}
    for edge in edges:
        if edge["source"] not in existing_node_ids or edge["target"] not in existing_node_ids:
            continue
        color = EDGE_COLORS.get(edge["sentiment"], "#9CA3AF")
        width = min(1 + edge["weight"] * 0.5, 6)
        net.add_edge(
            edge["source"],
            edge["target"],
            title=f"{edge['relation']} ({edge['sentiment']})\n강도: {edge['weight']:.1f}",
            label=edge["relation"],
            color=color,
            width=width,
            arrows="to",
            font={"size": 9, "color": "#cccccc", "align": "middle"},
        )

    # 범례 HTML 추가
    net.set_options("""
    var options = {
      "interaction": {
        "hover": true,
        "tooltipDelay": 100,
        "navigationButtons": true,
        "keyboard": true
      },
      "physics": {
        "enabled": true,
        "stabilization": {"iterations": 100}
      }
    }
    """)

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as f:
        net.save_graph(f.name)
        f.seek(0)

    with open(f.name, "r", encoding="utf-8") as f:
        html = f.read()

    # 다크 배경 + 범례 주입
    legend_html = """
    <div style="position:absolute;top:10px;right:10px;background:#1e2130;padding:12px;border-radius:8px;font-size:12px;color:#fff;z-index:999">
      <b>노드 타입</b><br>
      <span style="color:#4E9AF1">●</span> 기업 &nbsp;
      <span style="color:#F1A74E">●</span> 인물 &nbsp;
      <span style="color:#E05C5C">●</span> 이슈<br>
      <span style="color:#8B5CF6">●</span> 규제 &nbsp;
      <span style="color:#10B981">●</span> 섹터 &nbsp;
      <span style="color:#F59E0B">●</span> 제품<br>
      <span style="color:#6B7280">●</span> 거시<br><br>
      <b>엣지 감성</b><br>
      <span style="color:#10B981">─</span> 긍정 &nbsp;
      <span style="color:#EF4444">─</span> 부정 &nbsp;
      <span style="color:#9CA3AF">─</span> 중립
    </div>
    """
    html = html.replace("<body>", f"<body>{legend_html}")

    return html
