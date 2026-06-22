"""프로그램 생성 스프라이트(배·병사).

외부 이미지 없이 pygame.draw로 부대/함선 아이콘을 그려 캐시한다. 모두 진영
색상을 입혀 식별되며, 오른쪽(동쪽)을 바라보는 형태로 그린다.

    sprites.get_soldier(color, "infantry", 40)
    sprites.get_ship(color, "frigate", 44)
"""

import pygame

_cache = {}


def _darken(color, f=0.5):
    return (int(color[0] * f), int(color[1] * f), int(color[2] * f))


def _lighten(color, f=0.4):
    return (int(color[0] + (255 - color[0]) * f),
            int(color[1] + (255 - color[1]) * f),
            int(color[2] + (255 - color[2]) * f))


SKIN = (228, 196, 164)
BLACK = (28, 28, 32)
WOOD = (120, 84, 52)
WOOD_DK = (74, 50, 30)
SAIL = (236, 232, 220)


# ============ 병사 ============
def get_soldier(color, kind, size=40):
    key = ("sol", tuple(color), kind, size)
    if key not in _cache:
        _cache[key] = _draw_soldier(color, kind, size)
    return _cache[key]


def _draw_soldier(color, kind, size):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    w = h = size
    dk = _darken(color, 0.55)
    if kind == "cavalry":
        _draw_cavalry(s, w, h, color, dk)
    elif kind == "artillery":
        _draw_artillery(s, w, h, color, dk)
    elif kind == "guard":
        _draw_infantry(s, w, h, color, dk, guard=True)
    else:
        _draw_infantry(s, w, h, color, dk, guard=False)
    return s


def _draw_infantry(s, w, h, color, dk, guard=False):
    cx = w * 0.5
    # 다리
    pygame.draw.line(s, BLACK, (cx - w * 0.06, h * 0.92), (cx - w * 0.06, h * 0.70), 3)
    pygame.draw.line(s, BLACK, (cx + w * 0.06, h * 0.92), (cx + w * 0.06, h * 0.70), 3)
    # 몸통(외투)
    torso = pygame.Rect(0, 0, w * 0.26, h * 0.32)
    torso.center = (cx, h * 0.56)
    pygame.draw.rect(s, color, torso, border_radius=2)
    pygame.draw.rect(s, dk, torso, 1, border_radius=2)
    # 교차 벨트(흰색)
    pygame.draw.line(s, SAIL, torso.topleft, torso.bottomright, 1)
    # 머리
    pygame.draw.circle(s, SKIN, (int(cx), int(h * 0.34)), int(w * 0.08))
    # 모자
    if guard:
        hat = pygame.Rect(0, 0, w * 0.22, h * 0.22)   # 곰털모(베어스킨)
        hat.center = (cx, h * 0.24)
        pygame.draw.ellipse(s, BLACK, hat)
    else:
        hat = pygame.Rect(0, 0, w * 0.20, h * 0.14)   # 샤코
        hat.center = (cx, h * 0.27)
        pygame.draw.rect(s, BLACK, hat, border_radius=1)
    # 머스킷
    pygame.draw.line(s, WOOD_DK, (cx + w * 0.12, h * 0.74),
                     (cx + w * 0.20, h * 0.30), 2)


def _draw_cavalry(s, w, h, color, dk):
    # 말 몸통
    body = pygame.Rect(0, 0, w * 0.62, h * 0.28)
    body.center = (w * 0.48, h * 0.62)
    pygame.draw.ellipse(s, WOOD, body)
    pygame.draw.ellipse(s, WOOD_DK, body, 1)
    # 다리
    for dx in (-0.20, -0.06, 0.10, 0.24):
        x = w * 0.48 + w * dx
        pygame.draw.line(s, WOOD_DK, (x, h * 0.72), (x, h * 0.92), 2)
    # 말 머리/목
    pygame.draw.line(s, WOOD, (w * 0.74, h * 0.56), (w * 0.86, h * 0.40), 5)
    pygame.draw.circle(s, WOOD, (int(w * 0.86), int(h * 0.38)), int(w * 0.06))
    # 기수
    rider = pygame.Rect(0, 0, w * 0.16, h * 0.22)
    rider.center = (w * 0.42, h * 0.42)
    pygame.draw.rect(s, color, rider, border_radius=2)
    pygame.draw.circle(s, SKIN, (int(w * 0.42), int(h * 0.30)), int(w * 0.06))
    pygame.draw.rect(s, BLACK, (w * 0.37, h * 0.24, w * 0.10, h * 0.06))
    # 사브르
    pygame.draw.line(s, (210, 210, 215), (w * 0.50, h * 0.40), (w * 0.62, h * 0.26), 2)


def _draw_artillery(s, w, h, color, dk):
    # 바퀴
    pygame.draw.circle(s, WOOD_DK, (int(w * 0.36), int(h * 0.74)), int(w * 0.13), 0)
    pygame.draw.circle(s, BLACK, (int(w * 0.36), int(h * 0.74)), int(w * 0.13), 2)
    # 포신
    pygame.draw.line(s, _darken((120, 120, 130), 0.8),
                     (w * 0.28, h * 0.62), (w * 0.74, h * 0.50), 6)
    pygame.draw.circle(s, (60, 60, 66), (int(w * 0.74), int(h * 0.50)), int(w * 0.05))
    # 포가
    pygame.draw.line(s, WOOD, (w * 0.30, h * 0.62), (w * 0.50, h * 0.74), 3)
    # 포병(진영색)
    pygame.draw.circle(s, color, (int(w * 0.20), int(h * 0.56)), int(w * 0.07))
    pygame.draw.circle(s, SKIN, (int(w * 0.20), int(h * 0.46)), int(w * 0.05))


# ============ 함선 ============
SHIP_MASTS = {"ship_of_line": 3, "frigate": 3, "brig": 2, "sloop": 1}
SHIP_SCALE = {"ship_of_line": 1.0, "frigate": 0.86, "brig": 0.74, "sloop": 0.64}


def get_ship(color, kind, size=46):
    key = ("ship", tuple(color), kind, size)
    if key not in _cache:
        _cache[key] = _draw_ship(color, kind, size)
    return _cache[key]


def _draw_ship(color, kind, size):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    w = h = size
    sc = SHIP_SCALE.get(kind, 0.8)
    masts = SHIP_MASTS.get(kind, 2)

    y_deck = h * (0.60 - 0.04 * (1 - sc))
    half = w * 0.42 * sc
    cx = w * 0.5
    # 선체
    hull = [
        (cx - half, y_deck),
        (cx + half, y_deck),
        (cx + half + w * 0.06, y_deck + h * 0.10),   # 뱃머리(우)
        (cx + half - w * 0.04, y_deck + h * 0.22),
        (cx - half + w * 0.04, y_deck + h * 0.22),
        (cx - half - w * 0.04, y_deck + h * 0.10),
    ]
    pygame.draw.polygon(s, WOOD, hull)
    pygame.draw.polygon(s, WOOD_DK, hull, 2)
    # 진영색 선체 띠
    pygame.draw.line(s, color, (cx - half, y_deck + h * 0.05),
                     (cx + half, y_deck + h * 0.05), 3)
    # 포문
    n_ports = {3: 5, 2: 3, 1: 2}.get(masts, 3)
    for i in range(n_ports):
        px = cx - half + (2 * half) * (i + 0.5) / n_ports
        pygame.draw.circle(s, BLACK, (int(px), int(y_deck + h * 0.13)), 2)
    # 돛대 + 돛
    top = h * 0.10
    positions = [cx] if masts == 1 else \
        [cx + (i - (masts - 1) / 2) * (2 * half / masts) for i in range(masts)]
    for i, mx in enumerate(positions):
        pygame.draw.line(s, WOOD_DK, (mx, y_deck), (mx, top), 2)
        sail = pygame.Rect(0, 0, w * 0.18 * sc, (y_deck - top) * 0.8)
        sail.center = (mx, (y_deck + top) / 2)
        pygame.draw.rect(s, SAIL, sail, border_radius=2)
        pygame.draw.rect(s, (190, 186, 176), sail, 1, border_radius=2)
    # 진영 페넌트(가장 뒤 돛대 꼭대기)
    fx = positions[0]
    pygame.draw.polygon(s, color, [(fx, top), (fx, top - h * 0.10),
                                   (fx - w * 0.12, top - h * 0.06)])
    return s
