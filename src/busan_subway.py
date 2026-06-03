# -*- coding: utf-8 -*-
"""
부산 도시철도 역간 이동 경로 탐색 시스템 (객체지향 + 인접 리스트 데이터)
------------------------------------------------------------------
- 데이터: metro_data.py 의 GRAPH (이름 키 인접 리스트)
    GRAPH = { 역이름: [(이웃역, 소요시간(분), 노선명), ...] }
- 진짜 환승역(서면·연산 등)은 한 노드로 합쳐져 여러 노선 에지를 함께 가진다.
  → 주행 중 에지의 노선이 바뀌면 "환승"으로 보고 환승 3분을 더한다.
- BFS(0-1 BFS, deque)  : 최소 환승 경로
- 다익스트라(heapq)     : 최단 시간 경로

구성 클래스
  RouteResult : 탐색 결과(경로/환승/시간) 값 객체
  BusanMetro  : 인접 리스트 보관 + 경로 탐색(bfs/dijkstra)
  MetroApp    : 출력 및 사용자 입력 루프

외부 라이브러리 사용 금지: 표준 라이브러리(heapq, collections, dataclasses)만 사용.
Python 3.8 이상.
"""

import heapq
from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from metro_data import GRAPH


# ──────────────────────────────────────────────────────────────
# 값 객체: 탐색 결과
# ──────────────────────────────────────────────────────────────
@dataclass
class RouteResult:
    """경로 탐색 결과를 담는 값 객체."""
    stations: Optional[List[str]] = None   # 경유 역이름 리스트
    transfers: Optional[int] = None        # 환승 횟수
    total_time: Optional[int] = None       # 총 소요 시간(분)

    @property
    def found(self) -> bool:
        return self.stations is not None


# ──────────────────────────────────────────────────────────────
# 그래프 + 탐색 알고리즘
# ──────────────────────────────────────────────────────────────
class BusanMetro:
    """이름 키 인접 리스트와 경로 탐색 알고리즘을 캡슐화한다.

    노드 = 역이름(str), 에지 = (이웃역, 소요시간, 노선명).
    환승역은 한 노드에 여러 노선 에지가 모여 있으므로, 탐색 중 에지의 노선이
    직전 주행 노선과 다르면 환승으로 간주한다(환승 시간 가산).
    """

    TRANSFER_TIME = 3    # 환승 시간(분). 인접역 이동 시간은 에지 가중치(2분)에 포함.
    INF = float("inf")

    def __init__(self, graph: Optional[dict] = None):
        # 외부에서 다른 그래프를 주입할 수도 있다(테스트 등). 기본은 metro_data.GRAPH.
        self.graph = graph if graph is not None else GRAPH

    # ── 조회 헬퍼 ──────────────────────────────────────────
    def stations(self) -> set:
        """그래프에 존재하는 모든 역이름(키) 집합."""
        return set(self.graph)

    def has_station(self, name: str) -> bool:
        return name in self.graph

    # ── Algorithm Layer ────────────────────────────────────
    def bfs(self, start: str, end: str) -> RouteResult:
        """deque(0-1 BFS)로 최소 환승 경로를 탐색한다.

        상태: (환승횟수, 소요시간, 현재역, 현재노선, 경로)
          - 같은 노선으로 이동(환승 비용 0): deque 앞쪽(appendleft)
          - 노선이 바뀌는 이동(환승 비용 1) : deque 뒤쪽(append)
        방문 체크: (역, 노선)별 (환승횟수, 소요시간) 최소값으로 중복 방지.
        """
        if not self.has_station(start) or not self.has_station(end):
            return RouteResult()

        dq = deque()
        dq.append((0, 0, start, None, [start]))
        best = {(start, None): (0, 0)}  # (역, 노선) -> (환승, 시간)

        result = RouteResult()
        while dq:
            transfers, time, station, line, path = dq.popleft()
            if best.get((station, line), (self.INF, self.INF)) < (transfers, time):
                continue
            if station == end:
                if (not result.found
                        or (transfers, time) < (result.transfers, result.total_time)):
                    result = RouteResult(path, transfers, time)
                continue
            for nb, w, edge_line in self.graph[station]:
                is_transfer = (line is not None and edge_line != line)
                nt = transfers + (1 if is_transfer else 0)
                ntime = time + w + (self.TRANSFER_TIME if is_transfer else 0)
                key = (nb, edge_line)
                if (nt, ntime) < best.get(key, (self.INF, self.INF)):
                    best[key] = (nt, ntime)
                    state = (nt, ntime, nb, edge_line, path + [nb])
                    if is_transfer:
                        dq.append(state)
                    else:
                        dq.appendleft(state)

        return result

    def dijkstra(self, start: str, end: str) -> RouteResult:
        """heapq로 최단 시간 경로를 탐색한다.

        힙 상태: (소요시간, 환승횟수, 현재역, 현재노선, 경로)
        방문 체크: (역, 노선)별 최단 시간 딕셔너리(dist).
        """
        if not self.has_station(start) or not self.has_station(end):
            return RouteResult()

        heap = [(0, 0, start, None, [start])]
        dist = {(start, None): 0}

        while heap:
            time, transfers, station, line, path = heapq.heappop(heap)
            if time > dist.get((station, line), self.INF):
                continue
            if station == end:
                return RouteResult(path, transfers, time)
            for nb, w, edge_line in self.graph[station]:
                is_transfer = (line is not None and edge_line != line)
                ntime = time + w + (self.TRANSFER_TIME if is_transfer else 0)
                nt = transfers + (1 if is_transfer else 0)
                key = (nb, edge_line)
                if ntime < dist.get(key, self.INF):
                    dist[key] = ntime
                    heapq.heappush(heap, (ntime, nt, nb, edge_line, path + [nb]))

        return RouteResult()


# ──────────────────────────────────────────────────────────────
# 출력 / 사용자 입력
# ──────────────────────────────────────────────────────────────
@dataclass
class MetroApp:
    """경로 탐색 결과 출력과 사용자 입력 루프를 담당한다."""

    metro: BusanMetro
    test_cases: List[Tuple[str, str]] = field(default_factory=lambda: [
        ("남포", "노포"),
        ("남포", "수영"),
        ("장산", "대저"),
        ("노포", "안평"),
        ("다대포해수욕장", "대저"),
        ("남포", "가야대"),
        ("서면", "부전"),
    ])

    @staticmethod
    def _print_one(title: str, result: RouteResult) -> None:
        print(title)
        if not result.found:
            print("  경로를 찾을 수 없습니다.")
            print()
            return
        names = result.stations
        print("  경로 ({}개역): {}".format(len(names), " → ".join(names)))
        print("  환승: {}회 / 소요: 약 {}분".format(
            result.transfers, result.total_time))
        print()

    def print_result(self, start: str, end: str) -> None:
        """BFS와 다익스트라 결과를 나란히 출력한다."""
        print("=" * 60)
        print("  출발: {}  →  도착: {}".format(start, end))
        print("=" * 60)
        print()
        self._print_one("[BFS] 최소 환승 경로", self.metro.bfs(start, end))
        self._print_one("[다익스트라] 최단 시간 경로", self.metro.dijkstra(start, end))

    def run_tests(self) -> None:
        print("■ 테스트 케이스")
        print()
        for start, end in self.test_cases:
            self.print_result(start, end)

    def _resolve(self, name: str) -> Optional[str]:
        """입력한 역이름을 그래프 키로 해석한다(동명이역 처리).

        - 정확히 일치하는 키가 있으면 그대로 사용
        - 'X(노선)' 형태로만 존재하는 동명이역은 후보가 1개면 자동 선택,
          여러 개면 후보를 안내하고 None 반환
        실패 시 안내 메시지를 직접 출력하고 None 을 반환한다.
        """
        if name in self.metro.graph:
            return name
        cands = sorted(k for k in self.metro.graph if k.startswith(name + "("))
        if len(cands) == 1:
            return cands[0]
        if len(cands) > 1:
            print("  ! '{}' 은(는) 노선을 구분해서 입력하세요: {}\n".format(
                name, ", ".join(cands)))
        else:
            print("  ! '{}' 역을 찾을 수 없습니다. 다시 입력하세요.\n".format(name))
        return None

    def interactive(self) -> None:
        """출발역/도착역을 반복 입력받는다. q 입력 시 종료."""
        print("\n역 이름을 입력하세요. (종료: q)\n")
        while True:
            raw = input("출발역> ").strip()
            if raw.lower() == "q":
                break
            start = self._resolve(raw)
            if start is None:
                continue

            raw = input("도착역> ").strip()
            if raw.lower() == "q":
                break
            end = self._resolve(raw)
            if end is None:
                continue

            if start == end:
                print("  ! 출발역과 도착역이 같습니다.\n")
                continue

            print()
            self.print_result(start, end)

        print("프로그램을 종료합니다.")

    def run(self) -> None:
        print("부산 도시철도 경로 탐색 시스템")
        print("(노드 {}개)".format(len(self.metro.graph)))
        print()
        self.run_tests()
        self.interactive()


def main():
    metro = BusanMetro()
    app = MetroApp(metro)
    app.run()


if __name__ == "__main__":
    main()
