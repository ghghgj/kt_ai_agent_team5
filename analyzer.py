# analyzer.py — Graph RAG 기반 투자 브리핑 생성 (Agent 2)
# 그래프 컨텍스트 + 뉴스 원문을 LLM에 주입하여 근거 있는 리포트를 생성합니다.

import os
from datetime import datetime
from openai import OpenAI

from graph_builder import build_rag_context

ANALYST_SYSTEM_PROMPT = """
당신은 냉철하고 논리적인 시니어 퀀트 애널리스트입니다.
제공된 지식 그래프 구조와 뉴스 원문만을 근거로 투자 브리핑 리포트를 작성합니다.

규칙:
- 그래프에 없는 정보는 절대 만들어내지 않습니다 (할루시네이션 금지)
- 각 주장에 근거가 된 관계 경로나 뉴스를 명시합니다
- 불확실한 내용은 "확인 필요" 또는 "데이터 부족"으로 표시합니다
- 마크다운 형식으로 작성합니다
""".strip()

REPORT_PROMPT = """
아래 지식 그래프 컨텍스트를 바탕으로 투자 브리핑 리포트를 작성하세요.

---
{context}
---

다음 구조로 작성하세요:

## 1. 핵심 시그널 요약
그래프에서 확인된 주요 이슈와 방향성을 3~5개 bullet로 요약.
각 bullet 끝에 근거 경로를 표시: `[근거: A →관계→ B]`

## 2. 섹터별 영향 분석
긍정/부정 감성 엣지를 기준으로 섹터·기업별 영향을 서술.
연쇄 효과(A→B→C)가 있으면 경로 전체를 서술.

## 3. 주요 리스크
부정 감성 경로에서 도출된 리스크 요인만 작성.

## 4. 투자 시사점
위 분석을 종합한 단기/중기 시사점. 데이터 근거가 없는 추천은 하지 않음.

---
> ⚠️ 본 리포트는 DB에 수집된 뉴스와 그래프 데이터 기반으로 AI가 생성한 참고용 자료입니다.
> 분석 기준일: {date}
""".strip()


def run_agent2_analyzer(graph_data: dict) -> str:
    """
    지식 그래프 딕셔너리를 분석하여 마크다운 형식의 투자 브리핑 리포트를 반환합니다.

    Graph RAG 방식:
      1. graph_data의 nodes/edges로 그래프 컨텍스트 구성
      2. 노드 레이블로 DB에서 관련 뉴스 원문 검색 (Retrieval)
      3. 그래프 + 뉴스를 LLM 프롬프트에 주입 (Augmented Generation)
      4. 근거 기반 리포트 반환

    Args:
        graph_data (dict): {"nodes": [...], "edges": [...], "metadata": {...}} 구조.

    Returns:
        str: 마크다운 형식의 투자 브리핑 리포트
    """
    query = graph_data.get("metadata", {}).get("query", "")

    # ── Retrieval: 그래프 + 뉴스 컨텍스트 구성 ──────────────────────────────
    context = build_rag_context(graph_data, query=query)

    if not graph_data.get("nodes"):
        return "분석할 그래프 데이터가 없습니다. 먼저 뉴스를 수집하고 그래프를 업데이트하세요."

    # ── Augmented Generation: LLM 호출 ──────────────────────────────────────
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    try:
        response = client.chat.completions.create(
            model=os.environ.get("MODEL_NAME", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": ANALYST_SYSTEM_PROMPT},
                {"role": "user", "content": REPORT_PROMPT.format(
                    context=context,
                    date=datetime.now().strftime("%Y-%m-%d"),
                )},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content

    except Exception as e:
        return f"리포트 생성 중 오류 발생: {e}"
