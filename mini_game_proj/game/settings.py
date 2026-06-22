"""전역 설정값과 색상 팔레트.

전략 지도 MVP에서 사용하는 화면 크기, 색상, 폰트, 게임 파라미터를 모은다.
"""

# ---- 화면 ----
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 800
FPS = 60
TITLE = "Napoleon: 전략 지도"

# ---- 색상 (R, G, B) ----
COLOR_SEA = (40, 62, 92)
COLOR_LAND = (78, 96, 70)
COLOR_LAND_DARK = (60, 76, 54)
COLOR_EDGE = (120, 130, 110)
COLOR_TEXT = (235, 235, 225)
COLOR_TEXT_DIM = (170, 175, 165)
COLOR_PANEL = (24, 28, 34)
COLOR_PANEL_BORDER = (90, 100, 110)
COLOR_HIGHLIGHT = (255, 220, 120)
COLOR_MOVE_RANGE = (120, 220, 140)
COLOR_SELECT = (255, 240, 160)
COLOR_DANGER = (210, 80, 70)

# ---- 게임 파라미터 ----
ARMY_BASE_MOVE = 1          # 한 턴에 이동 가능한 간선 수
CITY_RADIUS = 16
ARMY_RADIUS = 13

# ---- 폰트 ----
# 한글 표시를 위해 시스템 폰트를 우선 사용한다 (settings 사용처에서 처리).
PREFERRED_FONTS = ["malgungothic", "applegothic", "notosanscjkkr", "arial"]
