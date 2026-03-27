"""
inject_framework_knowledge.py — agent_framework.md 배경지식 → DB 주입

1단계: 프레임워크 배경지식 기반 관계 주입
  - 12개 표준 섹터 노드 생성
  - Transmission Map(섹터 간 파급 경로) 엣지 주입
  - 기존 기업·섹터 노드 → 표준 섹터 연결
  - 대표 이슈-섹터 영향 관계 주입
"""

from db import init_db, upsert_node, upsert_edge, get_conn

init_db()

# ── 1. 표준 섹터 노드 정의 (agent_framework.md Section 2) ────────────────────
SECTORS = [
    ("금융",       "FIN", "은행·증권·보험·카드·핀테크·저축은행 포함"),
    ("부동산",      "RE",  "리츠·PF·주택금융·상업용부동산·시행·시공 포함"),
    ("반도체·제조",  "MFG", "반도체(메모리·파운드리)·디스플레이·전자·기계·방산 포함"),
    ("자동차",      "AUTO","완성차(현대·기아)·자동차부품·전기차·이차전지 포함"),
    ("IT·플랫폼",   "IT",  "포털·이커머스·클라우드·AI솔루션·SW·게임·핀테크 포함"),
    ("에너지·자원",  "ENE", "전력·석유·가스·신재생에너지·원자력·광물 포함"),
    ("유통·소비재",  "RET", "대형마트·이커머스·식품·뷰티·패션·물류 포함"),
    ("바이오·헬스",  "BIO", "제약·바이오텍·의료기기·디지털헬스·CRO 포함"),
    ("건설·인프라",  "CON", "대형건설사·SOC·플랜트·스마트건설 포함"),
    ("철강·소재",   "STL", "철강(POSCO 등)·시멘트·화학·비철금속 포함"),
    ("농업·식품",   "AGR", "농작물·식품가공·수산·농기계·스마트팜 포함"),
    ("공공·정책",   "GOV", "정부정책·인허가·국채·공기업·규제기관 포함"),
]

print("=" * 60)
print("Step 1-A: 표준 섹터 노드 생성")
print("=" * 60)

for label, code, desc in SECTORS:
    upsert_node(
        node_id=f"SECTOR_{code}",
        label=label,
        node_type="Sector",
        subtype="Primary",
        description=desc,
        sentiment_delta=0.0,
    )
    print(f"  ✓ [{code}] {label}")

print(f"\n  → {len(SECTORS)}개 표준 섹터 노드 완료\n")


# ── 2. Transmission Map 엣지 주입 (Section 5) ────────────────────────────────
# (source_id, target_id, relation, sentiment, confidence, temporal, description)
TRANSMISSION_EDGES = [
    # FIN 금융 충격 파급
    ("SECTOR_FIN", "SECTOR_CON", "AFFECTS", "negative", 0.9, "MEDIUM",
     "PF 부실 → 건설 대출 막힘"),
    ("SECTOR_FIN", "SECTOR_RE",  "AFFECTS", "negative", 0.85, "MEDIUM",
     "신용 위축 → 부동산 유동성 감소"),
    ("SECTOR_FIN", "SECTOR_RET", "AFFECTS", "negative", 0.8, "SHORT",
     "소비자 신용 위축 → 소비 감소"),

    # MFG 반도체·제조 충격
    ("SECTOR_MFG", "SECTOR_GOV", "AFFECTS", "negative", 0.75, "MEDIUM",
     "수출 감소 → 법인세·무역수지 악화"),
    ("SECTOR_MFG", "SECTOR_ENE", "AFFECTS", "negative", 0.7, "MEDIUM",
     "생산 축소 → 산업용 전력·가스 수요 감소"),

    # AUTO 자동차 충격
    ("SECTOR_AUTO", "SECTOR_STL", "AFFECTS", "negative", 0.85, "SHORT",
     "자동차 수출 감소 → 철강·부품 수요 감소"),
    ("SECTOR_AUTO", "SECTOR_MFG", "AFFECTS", "negative", 0.8, "SHORT",
     "전기차 수요 감소 → 반도체·배터리 주문 감소"),

    # ENE 에너지 급등 파급
    ("SECTOR_ENE", "SECTOR_MFG", "AFFECTS", "negative", 0.9, "SHORT",
     "에너지 급등 → 전 제조업 원가 상방"),
    ("SECTOR_ENE", "SECTOR_RET", "AFFECTS", "negative", 0.85, "SHORT",
     "물류·운반 비용 상승 → 소비재 가격 압박"),
    ("SECTOR_ENE", "SECTOR_AGR", "AFFECTS", "negative", 0.8, "SHORT",
     "농업용 에너지 비용 상승 → 식품 물가"),

    # GOV 규제·정책 변화
    ("SECTOR_GOV", "SECTOR_FIN", "REGULATES", "neutral", 0.95, "MEDIUM",
     "기준금리·인세 변화 → 대출·투자 조건 변화"),
    ("SECTOR_GOV", "SECTOR_RE",  "REGULATES", "neutral", 0.9, "LONG",
     "부동산 규제·공급 정책 → 시장 방향성 결정"),
    ("SECTOR_GOV", "SECTOR_CON", "REGULATES", "neutral", 0.85, "LONG",
     "SOC 예산·인허가 → 건설 수주 영향"),

    # IT AI 붐 파급
    ("SECTOR_IT", "SECTOR_MFG", "DRIVES",    "positive", 0.95, "SHORT",
     "AI 붐 → HBM 수요 급증 → 반도체 수출 급증"),
    ("SECTOR_IT", "SECTOR_ENE", "AFFECTS",   "negative", 0.8, "MEDIUM",
     "데이터센터 증가 → 전력 수요 급증"),
    ("SECTOR_IT", "SECTOR_FIN", "AFFECTS",   "positive", 0.75, "MEDIUM",
     "AI·핀테크 성장 → 기술주 자금 유입"),

    # RE 부동산 충격
    ("SECTOR_RE", "SECTOR_FIN", "AFFECTS",   "negative", 0.9, "MEDIUM",
     "담보가치 하락 → 은행 건전성 위협"),
    ("SECTOR_RE", "SECTOR_CON", "AFFECTS",   "negative", 0.85, "MEDIUM",
     "부동산 침체 → 건설 수주·착공 감소"),

    # GEO 지정학 리스크
    ("SECTOR_GOV", "SECTOR_AGR", "AFFECTS",  "negative", 0.75, "SHORT",
     "지정학 리스크 → 환율 급등 → 수입 식료품 가격 상승"),
    ("SECTOR_GOV", "SECTOR_RET", "AFFECTS",  "negative", 0.75, "SHORT",
     "지정학 리스크 → 소비심리 위축"),
    ("SECTOR_GOV", "SECTOR_ENE", "AFFECTS",  "negative", 0.8, "SHORT",
     "지정학 리스크 → 원자재 공급 불안"),

    # STL 철강·소재 관계
    ("SECTOR_STL", "SECTOR_AUTO", "SUPPLIES_TO", "neutral", 0.9, "MEDIUM",
     "철강 소재 → 자동차 차체 공급"),
    ("SECTOR_STL", "SECTOR_CON",  "SUPPLIES_TO", "neutral", 0.9, "MEDIUM",
     "철근·형강 → 건설 현장 공급"),

    # BIO 바이오
    ("SECTOR_BIO", "SECTOR_GOV", "BENEFITS_FROM", "positive", 0.8, "LONG",
     "신약 허가·건보 등재 → 정책 수혜"),
    ("SECTOR_FIN", "SECTOR_BIO", "INVESTS_IN", "positive", 0.7, "LONG",
     "벤처캐피털·기관 → 바이오 투자 확대"),
]

print("Step 1-B: Transmission Map 엣지 주입")
print("=" * 60)

for src, tgt, rel, sent, conf, scope, desc in TRANSMISSION_EDGES:
    edge_id = upsert_edge(src, tgt, rel, sentiment=sent, confidence=conf, temporal_scope=scope)
    print(f"  ✓ {src} →[{rel}/{sent}]→ {tgt}  ({desc})")

print(f"\n  → {len(TRANSMISSION_EDGES)}개 Transmission 엣지 완료\n")


# ── 3. 기존 DB 노드 → 표준 섹터 연결 ───────────────────────────────────────
# 이미 존재하는 회사/섹터 노드를 표준 섹터에 연결
COMPANY_SECTOR_MAP = [
    # 기업 → 섹터
    ("삼성전자",        "SECTOR_MFG",  "SUBSIDIARY_OF", "neutral"),
    ("SK하이닉스",      "SECTOR_MFG",  "SUBSIDIARY_OF", "neutral"),
    ("LG화학",         "SECTOR_STL",  "LEADS_SECTOR",  "neutral"),
    ("LG에너지솔루션",   "SECTOR_AUTO", "SUPPLIES_TO",   "neutral"),
    ("포스코",          "SECTOR_STL",  "LEADS_SECTOR",  "neutral"),
    ("포스코홀딩스",     "SECTOR_STL",  "SUBSIDIARY_OF", "neutral"),
    ("SK이노베이션",     "SECTOR_ENE",  "LEADS_SECTOR",  "neutral"),
    ("금호석유화학",     "SECTOR_STL",  "LEADS_SECTOR",  "neutral"),
    ("현대로템",        "SECTOR_AUTO", "SUBSIDIARY_OF", "neutral"),
    ("NH투자증권",      "SECTOR_FIN",  "LEADS_SECTOR",  "neutral"),
    ("한국은행",        "SECTOR_GOV",  "REGULATES",     "neutral"),
    ("기업은행",        "SECTOR_FIN",  "SUBSIDIARY_OF", "neutral"),
    ("하나은행",        "SECTOR_FIN",  "SUBSIDIARY_OF", "neutral"),
    ("국민연금",        "SECTOR_FIN",  "INVESTS_IN",    "neutral"),
    ("SK텔레콤",        "SECTOR_IT",   "LEADS_SECTOR",  "neutral"),
    ("KT",             "SECTOR_IT",   "LEADS_SECTOR",  "neutral"),
    ("한국가스공사",     "SECTOR_ENE",  "SUBSIDIARY_OF", "neutral"),
    ("가스공사",        "SECTOR_ENE",  "SUBSIDIARY_OF", "neutral"),
]

# 기존 섹터 노드 → 표준 섹터 연결
SECTOR_SECTOR_MAP = [
    ("반도체",         "SECTOR_MFG",  "LEADS_SECTOR",   "neutral"),
    ("철강",           "SECTOR_STL",  "LEADS_SECTOR",   "neutral"),
    ("철강업계",        "SECTOR_STL",  "LEADS_SECTOR",   "neutral"),
    ("석유화학",        "SECTOR_STL",  "LEADS_SECTOR",   "neutral"),
    ("석유화학 업황",   "SECTOR_STL",  "LEADS_SECTOR",   "neutral"),
    ("정유",           "SECTOR_ENE",  "LEADS_SECTOR",   "neutral"),
    ("정유업계",        "SECTOR_ENE",  "LEADS_SECTOR",   "neutral"),
    ("이차전지 소재",   "SECTOR_AUTO", "SUPPLIES_TO",    "neutral"),
    ("첨단소재",        "SECTOR_MFG",  "SUPPLIES_TO",    "neutral"),
    ("제약·바이오",     "SECTOR_BIO",  "LEADS_SECTOR",   "neutral"),
    ("로봇",           "SECTOR_MFG",  "LEADS_SECTOR",   "neutral"),
    ("5G",             "SECTOR_IT",   "LEADS_SECTOR",   "neutral"),
    ("통신업계",        "SECTOR_IT",   "LEADS_SECTOR",   "neutral"),
    ("은행권",          "SECTOR_FIN",  "LEADS_SECTOR",   "neutral"),
    ("저축은행",        "SECTOR_FIN",  "LEADS_SECTOR",   "neutral"),
    ("금융시장",        "SECTOR_FIN",  "LEADS_SECTOR",   "neutral"),
    ("부동산 프로젝트파이낸싱", "SECTOR_RE", "LEADS_SECTOR", "neutral"),
]

print("Step 1-C: 기존 노드 → 표준 섹터 연결")
print("=" * 60)

conn = get_conn()
existing_ids = {r[0] for r in conn.execute("SELECT id FROM graph_nodes").fetchall()}
conn.close()

linked = 0
for src, tgt, rel, sent in COMPANY_SECTOR_MAP + SECTOR_SECTOR_MAP:
    if src in existing_ids:
        upsert_edge(src, tgt, rel, sentiment=sent, confidence=0.95, temporal_scope="LONG")
        print(f"  ✓ {src} →[{rel}]→ {tgt}")
        linked += 1
    else:
        print(f"  ⚠ {src} 노드 없음 (건너뜀)")

print(f"\n  → {linked}개 연결 엣지 완료\n")


# ── 4. 주요 거시 변수 → 섹터 영향 관계 (Section 8 이벤트 레퍼런스 기반) ──────
MACRO_SECTOR_EDGES = [
    # 거시 변수 → 섹터 영향
    ("관세",       "SECTOR_AUTO", "THREATENS",   "negative", 0.9,  "SHORT",  "트럼프 관세 → 자동차 수출 직격"),
    ("관세",       "SECTOR_MFG",  "THREATENS",   "negative", 0.9,  "SHORT",  "수출 제조업 전반 타격"),
    ("관세",       "SECTOR_STL",  "THREATENS",   "negative", 0.85, "SHORT",  "철강·소재 수출 위협"),
    ("관세",       "SECTOR_FIN",  "AFFECTS",     "negative", 0.75, "SHORT",  "무역 축소 → 기업 신용 위험 증가"),
    ("국제유가",    "SECTOR_ENE",  "AFFECTS_PRICE","positive", 0.9, "SHORT",  "유가 상승 → 에너지 기업 수익 개선"),
    ("국제유가",    "SECTOR_MFG",  "AFFECTS",     "negative", 0.85, "SHORT",  "원가 부담 증가 → 제조업 마진 압박"),
    ("국제유가",    "SECTOR_RET",  "AFFECTS",     "negative", 0.8,  "SHORT",  "물류비 상승 → 소비재 유통 비용 증가"),
    ("고환율",      "SECTOR_MFG",  "BENEFITS_FROM","positive", 0.85,"SHORT",  "원화 약세 → 수출 제조업 가격 경쟁력"),
    ("고환율",      "SECTOR_RET",  "AFFECTS",     "negative", 0.8,  "SHORT",  "수입 물가 상승 → 소비재 원가 압박"),
    ("고환율",      "SECTOR_ENE",  "AFFECTS",     "negative", 0.85, "SHORT",  "수입 에너지 비용 증가"),
    ("고환율",      "SECTOR_FIN",  "AFFECTS",     "negative", 0.75, "SHORT",  "외화부채 기업 신용 리스크"),
    ("원달러 환율", "SECTOR_MFG",  "AFFECTS_PRICE","positive", 0.85,"SHORT",  "달러 강세 → 수출 제조업 수익 환산 이익"),
    ("금리",        "SECTOR_FIN",  "AFFECTS",     "neutral",  0.9,  "SHORT",  "기준금리 → 은행 NIM 직접 영향"),
    ("금리",        "SECTOR_RE",   "AFFECTS",     "negative", 0.9,  "SHORT",  "금리 상승 → 부동산 대출 부담 증가"),
    ("기준금리",    "SECTOR_FIN",  "AFFECTS",     "neutral",  0.95, "SHORT",  "기준금리 결정 → 금융업 직접 영향"),
    ("기준금리",    "SECTOR_RE",   "AFFECTS",     "negative", 0.9,  "SHORT",  "금리 인상 시 부동산 시장 위축"),
    ("인플레이션",  "SECTOR_GOV",  "THREATENS",   "negative", 0.8,  "MEDIUM", "물가 상승 → 긴축 압력 → 정책 변화"),
    ("인플레이션",  "SECTOR_RET",  "AFFECTS",     "negative", 0.85, "SHORT",  "소비자물가 상승 → 실질 구매력 하락"),
    ("인플레",      "SECTOR_RET",  "AFFECTS",     "negative", 0.85, "SHORT",  "인플레이션 → 소비 위축"),
    ("양극재",      "SECTOR_AUTO", "SUPPLIES_TO", "neutral",  0.95, "MEDIUM", "배터리 양극재 → 전기차 생산 원가"),
    ("양극재",      "SECTOR_MFG",  "SUPPLIES_TO", "neutral",  0.9,  "MEDIUM", "양극재 소재 → 이차전지 제조"),
]

print("Step 1-D: 거시변수·이슈 → 섹터 영향 관계 주입")
print("=" * 60)

conn = get_conn()
existing_ids = {r[0] for r in conn.execute("SELECT id FROM graph_nodes").fetchall()}
conn.close()

macro_linked = 0
for src, tgt, rel, sent, conf, scope, desc in MACRO_SECTOR_EDGES:
    if src in existing_ids:
        upsert_edge(src, tgt, rel, sentiment=sent, confidence=conf, temporal_scope=scope)
        print(f"  ✓ {src} →[{rel}/{sent}]→ {tgt}  ({desc})")
        macro_linked += 1
    else:
        print(f"  ⚠ {src} 노드 없음 (건너뜀)")

print(f"\n  → {macro_linked}개 거시-섹터 엣지 완료\n")


# ── 최종 현황 출력 ─────────────────────────────────────────────────────────────
from db import get_graph_stats
stats = get_graph_stats()
print("=" * 60)
print("최종 그래프 현황")
print(f"  노드: {stats['node_count']}개")
print(f"  엣지: {stats['edge_count']}개")
print(f"  근거문장: {stats['evidence_count']}개")
print("=" * 60)
