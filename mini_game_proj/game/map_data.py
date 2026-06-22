"""유럽 전략 지도 데이터.

지도를 노드 그래프로 단순화한다. 각 노드는 도시/속주이며 화면 좌표,
소속 진영, 주요 도심 여부를 가진다. 간선(EDGES)은 군대가 한 턴에 이동할
수 있는 인접 관계를 정의한다.

좌표는 1280x800 화면 기준의 대략적인 유럽 위치다(정밀 지도가 아님).
"""

# 진영 정의: id -> (표시명, 색상)
FACTIONS = {
    "france": ("프랑스 제국", (40, 70, 160)),
    "britain": ("대영제국", (170, 50, 50)),
    "russia": ("러시아 제국", (70, 130, 90)),
    "austria": ("오스트리아", (200, 200, 210)),
    "prussia": ("프로이센", (70, 70, 80)),
    "ottoman": ("오스만 제국", (200, 150, 60)),
    "neutral": ("중립", (130, 130, 130)),
}

PLAYER_FACTION = "france"

# 노드: id -> dict(name, x, y, owner, major=주요 도심 여부)
# 좌표는 assets/europe_map.png(LAEA relief) 위 실제 위치에 맞춤(시각 보정).
NODES = {
    "london":    {"name": "런던",     "x": 242, "y": 376, "owner": "britain",  "major": True},
    "amsterdam": {"name": "암스테르담", "x": 314, "y": 414, "owner": "france",   "major": False},
    "paris":     {"name": "파리",     "x": 283, "y": 460, "owner": "france",   "major": True},
    "madrid":    {"name": "마드리드",  "x": 214, "y": 598, "owner": "neutral",  "major": True},
    "milan":     {"name": "밀라노",    "x": 360, "y": 521, "owner": "france",   "major": False},
    "rome":      {"name": "로마",     "x": 388, "y": 588, "owner": "neutral",  "major": True},
    "berlin":    {"name": "베를린",    "x": 414, "y": 414, "owner": "prussia",  "major": True},
    "vienna":    {"name": "빈",       "x": 460, "y": 476, "owner": "austria",  "major": True},
    "warsaw":    {"name": "바르샤바",  "x": 490, "y": 399, "owner": "prussia",  "major": False},
    "kiev":      {"name": "키예프",    "x": 598, "y": 430, "owner": "russia",   "major": False},
    "smolensk":  {"name": "스몰렌스크", "x": 613, "y": 368, "owner": "russia",   "major": False},
    "moscow":    {"name": "모스크바",  "x": 697, "y": 315, "owner": "russia",   "major": True},
    "istanbul":  {"name": "이스탄불",  "x": 660, "y": 590, "owner": "ottoman",  "major": True},
    "belgrade":  {"name": "베오그라드", "x": 506, "y": 537, "owner": "ottoman",  "major": False},
    # ---- 바다 노드(함대가 이동, 점령 대상 아님) ----
    "atlantic":  {"name": "대서양",   "x": 110, "y": 470, "owner": "neutral", "major": False, "sea": True},
    "north_sea": {"name": "북해",     "x": 330, "y": 300, "owner": "neutral", "major": False, "sea": True},
    "baltic":    {"name": "발트해",   "x": 510, "y": 258, "owner": "neutral", "major": False, "sea": True},
    "med_west":  {"name": "서지중해", "x": 345, "y": 624, "owner": "neutral", "major": False, "sea": True},
    "med_east":  {"name": "동지중해", "x": 560, "y": 628, "owner": "neutral", "major": False, "sea": True},
    "black_sea": {"name": "흑해",     "x": 735, "y": 545, "owner": "neutral", "major": False, "sea": True},
}

# 간선: 인접 노드 쌍 (양방향)
EDGES = [
    ("london", "amsterdam"),
    ("london", "paris"),
    ("amsterdam", "paris"),
    ("amsterdam", "berlin"),
    ("paris", "madrid"),
    ("paris", "milan"),
    ("madrid", "milan"),
    ("milan", "rome"),
    ("milan", "vienna"),
    ("rome", "vienna"),
    ("rome", "belgrade"),
    ("berlin", "vienna"),
    ("berlin", "warsaw"),
    ("vienna", "warsaw"),
    ("vienna", "belgrade"),
    ("warsaw", "kiev"),
    ("warsaw", "smolensk"),
    ("kiev", "smolensk"),
    ("kiev", "belgrade"),
    ("smolensk", "moscow"),
    ("belgrade", "istanbul"),
    ("kiev", "istanbul"),
]

# 바다 간선(함대 이동 경로). 육지와 연결하지 않아 도메인이 분리된다.
SEA_EDGES = [
    ("atlantic", "north_sea"),
    ("atlantic", "med_west"),
    ("north_sea", "baltic"),
    ("med_west", "med_east"),
    ("med_east", "black_sea"),
]

# 초기 군대 배치: list of dict(faction, node, troops, general)
# troops=병력, general=지휘관 이름(None이면 일반 부대)
INITIAL_ARMIES = [
    {"faction": "france",  "node": "paris",    "troops": 45000, "general": "나폴레옹"},
    {"faction": "france",  "node": "milan",    "troops": 22000, "general": "다부"},
    {"faction": "britain", "node": "london",   "troops": 28000, "general": "웰링턴"},
    {"faction": "russia",  "node": "moscow",   "troops": 38000, "general": "쿠투조프"},
    {"faction": "russia",  "node": "kiev",     "troops": 20000, "general": None},
    {"faction": "austria", "node": "vienna",   "troops": 30000, "general": "카를 대공"},
    {"faction": "prussia", "node": "berlin",   "troops": 26000, "general": "블뤼허"},
    {"faction": "ottoman", "node": "istanbul", "troops": 24000, "general": None},
]

# 초기 함대 배치: 해군 강국들의 함대(domain='sea')
INITIAL_FLEETS = [
    {"faction": "britain", "node": "north_sea", "troops": 40000},  # 최강 해군
    {"faction": "france",  "node": "atlantic",  "troops": 26000},
    {"faction": "russia",  "node": "black_sea",  "troops": 18000},
    {"faction": "ottoman", "node": "med_east",   "troops": 16000},
]


# ---- 대륙/바다 외형 (시각용 단순 폴리곤, 노드 좌표에 맞춰 그림) ----
# 유럽 본토: 영국해협~우랄, 발트~지중해/흑해/아나톨리아까지 한 덩어리로 단순화.
MAINLAND = [
    (330, 185), (420, 165), (560, 150), (740, 140), (940, 150), (1090, 165),
    (1160, 210), (1200, 300), (1150, 400), (1080, 450),          # 동부/러시아 해안
    (1000, 470), (900, 520), (840, 575), (805, 610), (760, 585), # 흑해~이스탄불
    (720, 545), (690, 505),                                       # 발칸
    (660, 545), (640, 520),                                       # 그리스 돌출
    (610, 470), (560, 470),                                       # 아드리아 동안
    (545, 500), (525, 545), (515, 592), (498, 592), (492, 520),   # 이탈리아 반도
    (470, 490), (440, 500), (400, 490),                           # 프랑스 남부
    (360, 470), (300, 500),                                       # 이베리아 방향
    (250, 520), (180, 578), (140, 560), (150, 505), (210, 475),   # 이베리아
    (270, 440), (300, 400),                                       # 비스케이
    (290, 360), (305, 300),                                       # 프랑스 대서양안
    (320, 250), (330, 210),                                       # 시작점 복귀
]

# 영국 섬 (런던)
BRITAIN = [
    (215, 150), (280, 160), (302, 200), (292, 252), (250, 272),
    (208, 262), (193, 208), (198, 172),
]

# 스칸디나비아 (장식용, 노드 없음)
SCANDINAVIA = [
    (470, 78), (520, 58), (565, 92), (548, 145), (505, 152), (472, 118),
]

LANDMASSES = [MAINLAND, BRITAIN, SCANDINAVIA]

# 바다 이름 라벨: (텍스트, x, y)
SEA_LABELS = [
    ("대서양", 120, 360),
    ("북해", 360, 150),
    ("지중해", 430, 618),
    ("흑해", 905, 430),
    ("발트해", 600, 200),
]


def build_adjacency():
    """EDGES+SEA_EDGES로부터 node_id -> set(인접 node_id) 인접 리스트를 만든다."""
    adj = {nid: set() for nid in NODES}
    for a, b in EDGES + SEA_EDGES:
        adj[a].add(b)
        adj[b].add(a)
    return adj
