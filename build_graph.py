# -*- coding: utf-8 -*-
"""busan_metro.csv → src/metro_data.py 자동 생성기 (+ 내장 검증).

CSV 를 "단일 진실 공급원"으로 삼아 인접 리스트(GRAPH)를 생성한다.

입력:  data/busan_metro.csv   (line, order, station, transfer)
출력:  src/metro_data.py      (GRAPH 인접 리스트, 자동 생성 헤더 포함)
실행:  python3 build_graph.py

생성 규칙
  1. 같은 노선의 연속(order) 역 사이에 양방향 에지 (이웃역, 2, 노선명) 추가
  2. transfer 컬럼에 표시된 역은 노선 간 단일 노드로 병합 (예: 서면)
  3. 환승 표시 없이 역명이 충돌하면 '역명(노선)' 접미사로 자동 분리 (예: 좌천)
  4. 출력 파일 상단에 자동 생성 경고 주석 삽입

표준 라이브러리(csv, collections)만 사용한다. 제출물 실행에는 불필요한 개발 도구로,
busan_subway.py 는 생성된 metro_data.py 만 import 한다.
"""

import csv
import os
from collections import OrderedDict, defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(ROOT, "data", "busan_metro.csv")
OUT_PATH = os.path.join(ROOT, "src", "metro_data.py")

EDGE_WEIGHT = 2  # 인접역 이동 2분 (환승 3분은 탐색 알고리즘에서 가산)

# §4-1 노선별 역 수 (정본). 생성 결과가 다르면 에러.
EXPECTED_LINE_COUNTS = OrderedDict([
    ("1호선", 40),
    ("2호선", 43),
    ("3호선", 17),
    ("4호선", 14),
    ("부산김해경전철", 21),
    ("동해선", 23),
])

# 총 노드 수 기대값 = 노선 합계(158) − 병합 환승역 수(12) = 146
EXPECTED_NODE_COUNT = 146

# 출력 파일에서 노선/노드를 노출하는 순서
LINE_ORDER = list(EXPECTED_LINE_COUNTS.keys())


class BuildError(Exception):
    """생성 실패(검증 위반)를 나타낸다."""


def read_rows(path):
    """CSV 를 읽어 행 리스트로 반환한다. 각 행은 dict."""
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            station = (raw["station"] or "").strip()
            line = (raw["line"] or "").strip()
            if not station or not line:
                continue
            rows.append({
                "line": line,
                "order": int(raw["order"]),
                "station": station,
                "transfer": (raw["transfer"] or "").strip(),
            })
    return rows


def resolve_node_ids(rows):
    """각 (line, order) 행을 최종 노드 id 로 매핑한다 (규칙 2·3).

    - transfer 표시가 있는 동명 행들은 하나의 노드로 병합 → 역명 그대로.
    - transfer 표시가 없는데 같은 역명이 둘 이상 충돌하면 '역명(노선)' 으로 분리.
    """
    by_name = defaultdict(list)
    for r in rows:
        by_name[r["station"]].append(r)

    node_of = {}
    for name, group in by_name.items():
        transfer_rows = [r for r in group if r["transfer"]]
        plain_rows = [r for r in group if not r["transfer"]]
        # 병합 환승역(있다면) 1그룹 + 비환승 행 각각 1그룹
        num_groups = (1 if transfer_rows else 0) + len(plain_rows)
        for r in transfer_rows:
            node_of[(r["line"], r["order"])] = name
        for r in plain_rows:
            if num_groups > 1:
                node_of[(r["line"], r["order"])] = "{}({})".format(name, r["line"])
            else:
                node_of[(r["line"], r["order"])] = name
    return node_of


def build_graph(rows, node_of):
    """규칙 1: 노선별 연속 역 사이 양방향 에지를 추가한다."""
    by_line = defaultdict(list)
    for r in rows:
        by_line[r["line"]].append(r)

    graph = OrderedDict()

    def add_edge(u, v, line):
        graph.setdefault(u, [])
        edge = (v, EDGE_WEIGHT, line)
        if edge not in graph[u]:
            graph[u].append(edge)

    # 출력 안정성을 위해 정해진 노선 순서 → order 오름차순으로 처리
    seen_lines = [ln for ln in LINE_ORDER if ln in by_line]
    seen_lines += [ln for ln in by_line if ln not in seen_lines]
    for line in seen_lines:
        seq = sorted(by_line[line], key=lambda r: r["order"])
        for a, b in zip(seq, seq[1:]):
            na = node_of[(a["line"], a["order"])]
            nb = node_of[(b["line"], b["order"])]
            add_edge(na, nb, line)
            add_edge(nb, na, line)
    return graph


def validate(rows, node_of, graph):
    """§5 내장 검증. 위반 시 BuildError."""
    errors = []

    # (1) 노선별 역 수 ↔ §4-1 표
    line_counts = defaultdict(int)
    for r in rows:
        line_counts[r["line"]] += 1
    for line, expected in EXPECTED_LINE_COUNTS.items():
        got = line_counts.get(line, 0)
        if got != expected:
            errors.append("노선 '{}' 역 수 불일치: 기대 {}, 실제 {}".format(
                line, expected, got))
    extra = set(line_counts) - set(EXPECTED_LINE_COUNTS)
    if extra:
        errors.append("예상치 못한 노선: {}".format(", ".join(sorted(extra))))

    # (2) 접미사 처리 후에도 남는 이름 충돌
    #     하나의 노드 id 에 여러 행이 묶였는데 전부 환승역이 아니면 충돌이다.
    rows_per_node = defaultdict(list)
    for r in rows:
        rows_per_node[node_of[(r["line"], r["order"])]].append(r)
    for node, rs in rows_per_node.items():
        if len(rs) > 1 and not all(r["transfer"] for r in rs):
            lines = ", ".join(sorted(r["line"] for r in rs))
            errors.append("이름 충돌(병합 불가): 노드 '{}' ← {}".format(node, lines))

    # (3) 모든 에지의 대칭성 (A→B 있으면 B→A 존재)
    for u, edges in graph.items():
        for v, w, line in edges:
            back = (u, w, line)
            if v not in graph or back not in graph[v]:
                errors.append("비대칭 에지: {} →({}) {} 의 역방향 없음".format(u, line, v))

    # (4) 총 노드 수 ↔ 기대값 (노선 합계 − 병합 환승역 수)
    total = len(graph)
    if total != EXPECTED_NODE_COUNT:
        errors.append("총 노드 수 불일치: 기대 {}, 실제 {}".format(
            EXPECTED_NODE_COUNT, total))

    if errors:
        raise BuildError("\n".join(" - " + e for e in errors))

    return {
        "line_counts": dict(line_counts),
        "node_count": total,
        "merged": sorted(n for n, rs in rows_per_node.items() if len(rs) > 1),
    }


def render(graph):
    """GRAPH 딕셔너리를 metro_data.py 소스 문자열로 직렬화한다."""
    lines = [
        "# -*- coding: utf-8 -*-",
        "# AUTO-GENERATED by build_graph.py — 직접 수정 금지",
        "# 원본 데이터: data/busan_metro.csv (수정은 CSV 에서 하고 재생성)",
        '"""부산 도시철도 인접 리스트 데이터 (build_graph.py 가 busan_metro.csv 로부터 생성).',
        "",
        "형식: GRAPH = { 역이름: [(이웃역, 소요시간(분), 노선명), ...] }",
        "- 일반 인접역 이동: 2분",
        "- 진짜 환승역(서면·연산 등)은 한 노드로 합쳐져 여러 노선 에지를 함께 가진다.",
        "  (환승 3분은 주행 중 노선이 바뀔 때 알고리즘에서 더한다)",
        '- 환승 표시가 없는 동명이역(좌천·동래)만 "좌천(동해선)"처럼 노선으로 구분한다.',
        '"""',
        "",
        "GRAPH = {",
    ]
    for node, edges in graph.items():
        lines.append("    {}: [".format(repr(node)))
        for v, w, line in edges:
            lines.append("        ({}, {}, {}),".format(repr(v), w, repr(line)))
        lines.append("    ],")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def main():
    rows = read_rows(CSV_PATH)
    node_of = resolve_node_ids(rows)
    graph = build_graph(rows, node_of)
    info = validate(rows, node_of, graph)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(render(graph))

    print("[build_graph] 검증 통과")
    for line in LINE_ORDER:
        print("  - {:<8} {:>3}역".format(line, info["line_counts"].get(line, 0)))
    print("  - 병합 환승역 {}개: {}".format(
        len(info["merged"]), ", ".join(info["merged"])))
    print("  - 총 노드 수: {} (기대 {})".format(
        info["node_count"], EXPECTED_NODE_COUNT))
    print("[build_graph] 생성 완료 → {}".format(
        os.path.relpath(OUT_PATH, ROOT)))


if __name__ == "__main__":
    main()
