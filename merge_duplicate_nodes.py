"""
merge_duplicate_nodes.py — 중복·유사 노드 통폐합

대상:
  1. 띄어쓰기만 다른 노드 (국제유가 vs 국제 유가)
  2. 같은 의미 별칭 노드 (인플레 vs 인플레이션)
  3. 세부/일반명 중복 (철강업계 vs 철강 → 철강으로 통합)
  4. 완전히 동일한 WTI 표기 중복
  5. 비금융 노드 삭제 (스포츠, 예능 관련)

작동 방식:
  - keep_id: 유지할 노드 ID
  - remove_ids: 삭제할 노드 ID 목록
  - 엣지 리다이렉트 후 노드 삭제
"""

from db import init_db, get_conn

init_db()

def merge_nodes(keep_id: str, remove_ids: list[str], dry_run: bool = False):
    """remove_ids → keep_id 로 모든 엣지를 리다이렉트 후 노드 삭제"""
    conn = get_conn()
    merged_count = 0

    for old_id in remove_ids:
        # 노드 존재 확인
        row = conn.execute("SELECT id, label, mention_count FROM graph_nodes WHERE id = ?", (old_id,)).fetchone()
        if not row:
            print(f"    ⚠ '{old_id}' 노드 없음, 건너뜀")
            continue

        if dry_run:
            print(f"    [DRY] '{old_id}' → '{keep_id}'")
            continue

        with conn:
            # 엣지 source 리다이렉트 (중복 발생 시 기존 엣지 weight 합산)
            old_edges = conn.execute(
                "SELECT id, source, target, relation FROM graph_edges WHERE source = ?", (old_id,)
            ).fetchall()
            for e in old_edges:
                # 동일 (target, relation) 엣지가 keep_id로 이미 있는지 확인
                existing = conn.execute(
                    "SELECT id FROM graph_edges WHERE source=? AND target=? AND relation=?",
                    (keep_id, e["target"], e["relation"])
                ).fetchone()
                if existing:
                    # weight 합산
                    conn.execute(
                        "UPDATE graph_edges SET weight = weight + 1 WHERE id = ?", (existing["id"],)
                    )
                    conn.execute("DELETE FROM graph_edges WHERE id = ?", (e["id"],))
                else:
                    conn.execute(
                        "UPDATE graph_edges SET source = ? WHERE id = ?", (keep_id, e["id"])
                    )

            # 엣지 target 리다이렉트
            old_edges_t = conn.execute(
                "SELECT id, source, target, relation FROM graph_edges WHERE target = ?", (old_id,)
            ).fetchall()
            for e in old_edges_t:
                existing = conn.execute(
                    "SELECT id FROM graph_edges WHERE source=? AND target=? AND relation=?",
                    (e["source"], keep_id, e["relation"])
                ).fetchone()
                if existing:
                    conn.execute(
                        "UPDATE graph_edges SET weight = weight + 1 WHERE id = ?", (existing["id"],)
                    )
                    conn.execute("DELETE FROM graph_edges WHERE id = ?", (e["id"],))
                else:
                    conn.execute(
                        "UPDATE graph_edges SET target = ? WHERE id = ?", (keep_id, e["id"])
                    )

            # mention_count 합산
            conn.execute(
                "UPDATE graph_nodes SET mention_count = mention_count + ? WHERE id = ?",
                (row["mention_count"], keep_id)
            )

            # 별칭 등록
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO node_aliases (alias, canonical_id) VALUES (?, ?)",
                    (old_id, keep_id)
                )
                conn.execute(
                    "INSERT OR IGNORE INTO node_aliases (alias, canonical_id) VALUES (?, ?)",
                    (row["label"], keep_id)
                )
            except Exception:
                pass

            # 노드 삭제
            conn.execute("DELETE FROM graph_nodes WHERE id = ?", (old_id,))

        print(f"    ✓ '{old_id}' ({row['label']}, {row['mention_count']}회) → '{keep_id}' 통합")
        merged_count += 1

    conn.close()
    return merged_count


def delete_node(node_id: str, reason: str = ""):
    """노드 및 연결된 모든 엣지 삭제"""
    conn = get_conn()
    row = conn.execute("SELECT id, label FROM graph_nodes WHERE id = ?", (node_id,)).fetchone()
    if not row:
        conn.close()
        return False
    with conn:
        conn.execute("DELETE FROM graph_edges WHERE source = ? OR target = ?", (node_id, node_id))
        conn.execute("DELETE FROM graph_nodes WHERE id = ?", (node_id,))
        conn.execute("DELETE FROM node_aliases WHERE canonical_id = ?", (node_id,))
    conn.close()
    print(f"    🗑 '{node_id}' ({row['label']}) 삭제 — {reason}")
    return True


# ── 통합 규칙 정의 ─────────────────────────────────────────────────────────────
MERGE_RULES = [
    # (keep_id, [remove_ids], 설명)

    # ── 거시 지표 중복 ─────────────────────────────────────────────────────────
    ("국제유가",    ["국제 유가"],                       "띄어쓰기 중복"),
    ("원달러 환율", ["원·달러 환율"],                    "표기법 중복"),
    ("인플레이션",  ["인플레"],                          "약어 → 정식명 통합"),
    ("기준금리",    ["금리", "시장금리", "단기채금리"],    "금리 관련 통합"),
    ("금융기관 가중평균금리", ["금융기관 가중평균 금리"],  "띄어쓰기 중복"),

    # ── WTI 유가 중복 ──────────────────────────────────────────────────────────
    ("서부텍사스산원유", ["서부 텍사스산 원유", "서부텍사스산원유(WTI)"], "WTI 표기 통합"),

    # ── 철강 섹터 중복 ─────────────────────────────────────────────────────────
    ("철강",        ["철강업계"],                        "철강업계 → 철강 통합"),

    # ── 석유화학 섹터 중복 ─────────────────────────────────────────────────────
    ("석유화학",    ["석유화학 업황"],                    "업황 → 섹터 통합"),

    # ── 정유 섹터 중복 ─────────────────────────────────────────────────────────
    ("정유",        ["정유업계"],                        "정유업계 → 정유 통합"),

    # ── 서울 외환시장 중복 ─────────────────────────────────────────────────────
    ("서울 외환시장", ["서울외환시장"],                   "띄어쓰기 중복"),

    # ── 가스공사 중복 ──────────────────────────────────────────────────────────
    ("한국가스공사", ["가스공사"],                        "약칭 → 정식명 통합"),

    # ── 중동 전쟁 관련 중복 이벤트 ────────────────────────────────────────────
    ("중동 전쟁",   ["중동전쟁", "중동 분쟁", "중동 지역 분쟁",
                    "이란 전쟁", "이스라엘-이란 전쟁",
                    "미국·이란 전쟁", "미국 이란 전쟁"],  "중동 분쟁 이벤트 통합"),

    # ── 주가/시장 지수 중복 ────────────────────────────────────────────────────
    ("코스피",      ["코스닥"],                          "주식시장 지수 — 코스닥을 코스피로 흡수"),

    # ── 유가 관련 ──────────────────────────────────────────────────────────────
    ("국제유가",    ["유가", "원유 가격", "원유 수급"],    "유가 관련 통합"),
    ("국제유가",    ["에너지 가격"],                      "에너지 가격 → 유가로 통합"),

    # ── 환율 관련 ──────────────────────────────────────────────────────────────
    ("고환율",      ["원재료 가격"],                      "원재료가격(환율 연동) → 고환율 통합"),

    # ── 이익 관련 ──────────────────────────────────────────────────────────────
    ("영업이익",    ["당기순이익", "순이익"],              "이익 지표 통합"),

    # ── 중동 지역 ──────────────────────────────────────────────────────────────
    ("중동 지역",   ["중동", "중동 에너지"],              "중동 관련 통합"),

    # ── 연도 이벤트 정리 ────────────────────────────────────────────────────────
    # (연도 노드들은 아래 삭제 대상으로 처리)
]

# 삭제 대상 (비금융/스포츠/잡음 노드)
DELETE_NODES = [
    # 스포츠
    ("kt",                              "프로농구팀 (KT 통신사와 혼동)"),
    ("kt wiz",                          "야구팀, 비금융"),
    ("2025-2026 LG전자 프로농구 정규리그", "스포츠 이벤트"),
    ("수원 kt소닉붐 아레나",               "스포츠 시설"),
    ("3연패 탈출",                        "스포츠 이벤트"),
    ("신기록 달성",                        "스포츠 이벤트"),
    ("2026 신한 SOL KBO리그",             "스포츠 이벤트"),
    ("프로야구",                           "스포츠 섹터, 비금융"),
    ("프로농구",                           "스포츠 섹터, 비금융"),
    ("클라이맥스",                         "스포츠 관련 제품"),
    ("클린존",                            "스포츠 관련 제품"),

    # 너무 일반적인 연도/시점 노드
    ("4월",     "시점 노드, 정보 없음"),
    ("하반기",   "시점 노드, 정보 없음"),
    ("2025년도", "연도 노드"),
    ("2024년도", "연도 노드"),
    ("2021년도", "연도 노드"),
    ("2026년도", "연도 노드"),
    ("2023년 11월", "시점 노드"),
    ("45만원",   "가격 노드, 맥락 없음"),
    ("42만원",   "가격 노드, 맥락 없음"),

    # 비금융 제품
    ("웰메이드 드라마",  "비금융 콘텐츠"),
    ("아이폰 17 시리즈", "Apple 제품, 국내 증권 무관"),
    ("아이폰17",         "Apple 제품, 국내 증권 무관"),
    ("iOS 26.4",        "Apple OS, 비금융"),
    ("아이폰 5G SA",    "Apple 제품, 비금융"),
    ("아너",             "중국 스마트폰 브랜드, 맥락 없음"),

    # 지나치게 일반적이거나 잡음
    ("OK",              "의미 불명확"),
    ("SBI",             "맥락 없는 단독 노드"),
    ("코리니",           "소형 기업, 맥락 없음"),
    ("인베스팅닷컴",     "정보 사이트, 노드로 부적합"),
    ("CME FedWatch",    "도구명, 노드로 부적합"),
    ("LyondellBasell",  "외국 화학기업, 국내 증권 연관성 낮음"),
    ("중국 시누크",      "중국 기업, 맥락 불충분"),

    # 연예/드라마
    ("스폰서십 계약",    "스포츠/연예 관련"),
]


print("=" * 60)
print("Step 2-A: 중복 노드 통폐합")
print("=" * 60)

total_merged = 0
for keep_id, remove_ids, desc in MERGE_RULES:
    print(f"\n  [{desc}] → '{keep_id}' 유지")
    # keep 노드 존재 여부 확인
    conn = get_conn()
    keep_row = conn.execute("SELECT id FROM graph_nodes WHERE id = ?", (keep_id,)).fetchone()
    conn.close()
    if not keep_row:
        print(f"    ⚠ keep 노드 '{keep_id}' 없음, 건너뜀")
        continue
    total_merged += merge_nodes(keep_id, remove_ids)

print(f"\n  → 총 {total_merged}개 노드 통합 완료\n")


print("=" * 60)
print("Step 2-B: 비금융·잡음 노드 삭제")
print("=" * 60)

deleted = 0
for node_id, reason in DELETE_NODES:
    if delete_node(node_id, reason):
        deleted += 1

print(f"\n  → 총 {deleted}개 노드 삭제 완료\n")


# ── 최종 현황 ─────────────────────────────────────────────────────────────────
from db import get_graph_stats
stats = get_graph_stats()
print("=" * 60)
print("최종 그래프 현황")
print(f"  노드: {stats['node_count']}개")
print(f"  엣지: {stats['edge_count']}개")
print(f"  별칭: {stats['alias_count']}개")
print(f"  근거문장: {stats['evidence_count']}개")
print("\n  Top 10 핵심 노드:")
for n in stats["top_nodes"]:
    print(f"    [{n['type']:10}] {n['label']:25} {n['mention_count']}회")
print("=" * 60)
