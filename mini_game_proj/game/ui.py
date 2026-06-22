"""렌더링 및 폰트 헬퍼.

전략 지도(노드/간선), 군대 스택, 선택/이동범위 하이라이트, 우측 정보 패널,
하단 로그를 그린다. 진영 국기(나폴레옹 전쟁기, Wikimedia)를 로드해 표시한다.
"""

import os

import pygame

from . import settings as S
from . import map_data
from . import sprites

ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
FLAG_DIR = os.path.join(ASSET_DIR, "flags")

# 지도 뷰포트(상단 바 36px ~ 하단 로그 650px, 우측 패널 980px 좌측)
MAP_VIEWPORT = pygame.Rect(0, 36, S.SCREEN_WIDTH - 300, S.SCREEN_HEIGHT - 150 - 36)


def load_europe_map():
    """유럽 지형도를 로드해 뷰포트를 채우도록(cover) 스케일한 (Surface, (x,y))를 반환.

    실패하면 None(폴리곤 폴백)을 반환한다.
    """
    path = os.path.join(ASSET_DIR, "europe_map.png")
    if not os.path.exists(path):
        return None
    img = pygame.image.load(path).convert()
    iw, ih = img.get_size()
    vp = MAP_VIEWPORT
    scale = max(vp.width / iw, vp.height / ih)   # cover: 뷰포트를 가득 채움
    scaled = pygame.transform.smoothscale(img, (int(iw * scale), int(ih * scale)))
    x = vp.centerx - scaled.get_width() // 2
    y = vp.centery - scaled.get_height() // 2
    return scaled, (x, y)


def load_flags(height=14):
    """진영 id -> Surface 로 국기를 로드한다(높이 고정, 비율 유지). 실패 시 생략."""
    flags = {}
    for fid in map_data.FACTIONS:
        path = os.path.join(FLAG_DIR, fid + ".png")
        if not os.path.exists(path):
            continue
        img = pygame.image.load(path).convert_alpha()
        w = int(img.get_width() * height / img.get_height())
        flags[fid] = pygame.transform.smoothscale(img, (w, height))
    return flags


def load_font(size, bold=False):
    """한글을 지원하는 시스템 폰트를 우선 로드한다."""
    for name in S.PREFERRED_FONTS:
        path = pygame.font.match_font(name, bold=bold)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.SysFont(None, size, bold=bold)


class Renderer:
    def __init__(self, screen):
        self.screen = screen
        self.font_sm = load_font(15)
        self.font_md = load_font(18, bold=True)
        self.font_lg = load_font(30, bold=True)
        self.panel_x = S.SCREEN_WIDTH - 300
        self.flags = load_flags(height=14)          # 패널/현황용 작은 국기
        self.flags_big = load_flags(height=22)       # 상단 바용 국기
        self.europe = load_europe_map()             # (Surface, pos) 또는 None

    def draw(self, state, selected, move_targets):
        self.screen.fill(S.COLOR_SEA)
        self._draw_land()
        self._draw_edges(state)
        self._draw_move_targets(state, move_targets)
        self._draw_nodes(state, selected)
        self._draw_armies(state, selected)
        self._draw_panel(state, selected)
        self._draw_log(state)
        self._draw_topbar(state)
        if state.game_over:
            self._draw_gameover(state)

    # ---- 지도 ----
    def _draw_land(self):
        if self.europe is not None:
            surf, pos = self.europe
            prev = self.screen.get_clip()
            self.screen.set_clip(MAP_VIEWPORT)
            self.screen.blit(surf, pos)
            self.screen.set_clip(prev)
            return
        # 폴백: 단순 폴리곤 대륙
        for poly in map_data.LANDMASSES:
            pygame.draw.polygon(self.screen, S.COLOR_LAND, poly)
            pygame.draw.polygon(self.screen, S.COLOR_LAND_DARK, poly, 3)
        for text, x, y in map_data.SEA_LABELS:
            t = self.font_sm.render(text, True, S.COLOR_TEXT_DIM)
            self.screen.blit(t, (x - t.get_width() // 2, y))

    def _draw_edges(self, state):
        for a, b in map_data.EDGES:
            pa = (state.nodes[a]["x"], state.nodes[a]["y"])
            pb = (state.nodes[b]["x"], state.nodes[b]["y"])
            pygame.draw.line(self.screen, S.COLOR_EDGE, pa, pb, 2)
        for a, b in map_data.SEA_EDGES:    # 항로
            pa = (state.nodes[a]["x"], state.nodes[a]["y"])
            pb = (state.nodes[b]["x"], state.nodes[b]["y"])
            pygame.draw.line(self.screen, (90, 130, 165), pa, pb, 2)

    def _draw_move_targets(self, state, move_targets):
        for nid in move_targets:
            n = state.nodes[nid]
            pygame.draw.circle(self.screen, S.COLOR_MOVE_RANGE,
                               (n["x"], n["y"]), S.CITY_RADIUS + 8, 3)

    def _draw_nodes(self, state, selected):
        for nid, n in state.nodes.items():
            if n.get("sea"):
                # 바다 노드: 작은 청색 표식(점령 대상 아님)
                pygame.draw.circle(self.screen, (52, 96, 150), (n["x"], n["y"]), 10)
                pygame.draw.circle(self.screen, (150, 190, 220), (n["x"], n["y"]), 10, 2)
            else:
                color = map_data.FACTIONS[n["owner"]][1]
                r = S.CITY_RADIUS + (4 if n["major"] else 0)
                pygame.draw.circle(self.screen, color, (n["x"], n["y"]), r)
                pygame.draw.circle(self.screen, (15, 15, 20), (n["x"], n["y"]), r, 2)
                if n["major"]:
                    pygame.draw.circle(self.screen, S.COLOR_HIGHLIGHT,
                                       (n["x"], n["y"]), r + 3, 2)
            r = 10 if n.get("sea") else S.CITY_RADIUS + (4 if n["major"] else 0)
            label = self.font_sm.render(n["name"], True, S.COLOR_TEXT)
            lx = n["x"] - label.get_width() // 2
            ly = n["y"] + r + 2
            bg = pygame.Surface((label.get_width() + 6, label.get_height() + 2),
                                pygame.SRCALPHA)
            bg.fill((10, 14, 20, 170))
            self.screen.blit(bg, (lx - 3, ly - 1))
            self.screen.blit(label, (lx, ly))

    def _draw_armies(self, state, selected):
        # 노드별로 군대/함대를 약간 위쪽에 표시
        for army in state.armies:
            n = state.nodes[army.node_id]
            ax, ay = n["x"] + 18, n["y"] - 20
            color = map_data.FACTIONS[army.faction][1]
            rect = pygame.Rect(0, 0, 28, 22)
            rect.center = (ax, ay)
            # 배경 칩(진영색) + 아이콘
            pygame.draw.rect(self.screen, color, rect, border_radius=4)
            if army.is_fleet:
                spr = sprites.get_ship(color, "frigate", 22)
            else:
                spr = sprites.get_soldier(color, "guard" if army.has_guard else "infantry", 22)
            self.screen.blit(spr, (rect.centerx - 11, rect.centery - 11))
            border = S.COLOR_SELECT if army is selected else (15, 15, 20)
            width = 3 if army is selected else 2
            pygame.draw.rect(self.screen, border, rect, width, border_radius=4)
            if army.has_guard:
                pygame.draw.circle(self.screen, S.COLOR_HIGHLIGHT,
                                   (rect.right - 4, rect.top + 4), 3)
            # 병력 수(칩 아래)
            txt = self.font_sm.render(f"{army.troops // 1000}k", True, S.COLOR_TEXT)
            bg = pygame.Surface((txt.get_width() + 4, txt.get_height()), pygame.SRCALPHA)
            bg.fill((10, 14, 20, 160))
            self.screen.blit(bg, (rect.centerx - txt.get_width() // 2 - 2, rect.bottom))
            self.screen.blit(txt, (rect.centerx - txt.get_width() // 2, rect.bottom))

    # ---- 우측 패널 ----
    def _draw_panel(self, state, selected):
        x = self.panel_x
        panel = pygame.Rect(x, 40, 300, S.SCREEN_HEIGHT - 220)
        pygame.draw.rect(self.screen, S.COLOR_PANEL, panel)
        pygame.draw.rect(self.screen, S.COLOR_PANEL_BORDER, panel, 2)

        y = 54
        title = self.font_md.render("부대 정보", True, S.COLOR_HIGHLIGHT)
        self.screen.blit(title, (x + 14, y))
        y += 34

        if selected is None:
            hint = self.font_sm.render("아군 부대를 클릭하세요.", True, S.COLOR_TEXT_DIM)
            self.screen.blit(hint, (x + 14, y))
        else:
            lines = [
                f"진영: {map_data.FACTIONS[selected.faction][0]}",
                f"위치: {state.nodes[selected.node_id]['name']}",
                f"병력: {selected.troops:,}",
                f"지휘관: {selected.general or '없음'}",
                f"근위대: {'있음' if selected.has_guard else '없음'}",
                f"전투력: {int(selected.combat_power()):,}",
                f"남은 이동: {selected.moves_left}",
            ]
            for ln in lines:
                t = self.font_sm.render(ln, True, S.COLOR_TEXT)
                self.screen.blit(t, (x + 14, y))
                y += 24

        # 진영별 도시 수 집계
        y += 16
        sub = self.font_md.render("세력 현황", True, S.COLOR_HIGHLIGHT)
        self.screen.blit(sub, (x + 14, y))
        y += 30
        counts = {}
        for n in state.nodes.values():
            counts[n["owner"]] = counts.get(n["owner"], 0) + 1
        for fid in state.faction_order:
            name = map_data.FACTIONS[fid][0]
            c = counts.get(fid, 0)
            troops = sum(a.troops for a in state.armies if a.faction == fid)
            flag = self.flags.get(fid)
            if flag:
                self.screen.blit(flag, (x + 14, y + 2))
                pygame.draw.rect(self.screen, (15, 15, 20),
                                 (x + 14, y + 2, flag.get_width(), flag.get_height()), 1)
                tx = x + 14 + flag.get_width() + 8
            else:
                color = map_data.FACTIONS[fid][1]
                pygame.draw.rect(self.screen, color, (x + 14, y + 3, 12, 12))
                tx = x + 32
            t = self.font_sm.render(f"{name}: 도시 {c} / 병력 {troops // 1000}k",
                                    True, S.COLOR_TEXT)
            self.screen.blit(t, (tx, y))
            y += 22

    # ---- 상단 바 ----
    def _draw_topbar(self, state):
        bar = pygame.Rect(0, 0, S.SCREEN_WIDTH, 36)
        pygame.draw.rect(self.screen, S.COLOR_PANEL, bar)
        fac = map_data.FACTIONS[state.current_faction][0]
        is_player = state.current_faction == map_data.PLAYER_FACTION
        turn_txt = f"턴 {state.turn_number}  |  현재 진영: {fac}"
        if is_player:
            turn_txt += "  (당신)"
        t = self.font_md.render(turn_txt, True, S.COLOR_TEXT)
        self.screen.blit(t, (14, 8))
        flag = self.flags_big.get(state.current_faction)
        if flag:
            fx = 14 + t.get_width() + 12
            self.screen.blit(flag, (fx, 7))
            pygame.draw.rect(self.screen, (15, 15, 20),
                             (fx, 7, flag.get_width(), flag.get_height()), 1)
        hint = self.font_sm.render(
            "좌클릭: 선택/이동   |   Space/Enter: 턴 종료   |   Esc: 종료",
            True, S.COLOR_TEXT_DIM)
        self.screen.blit(hint, (S.SCREEN_WIDTH - hint.get_width() - 14, 11))

    # ---- 하단 로그 ----
    def _draw_log(self, state):
        h = 150
        panel = pygame.Rect(0, S.SCREEN_HEIGHT - h, S.SCREEN_WIDTH, h)
        pygame.draw.rect(self.screen, S.COLOR_PANEL, panel)
        pygame.draw.rect(self.screen, S.COLOR_PANEL_BORDER, panel, 2)
        y = S.SCREEN_HEIGHT - h + 8
        title = self.font_md.render("전황 일지", True, S.COLOR_HIGHLIGHT)
        self.screen.blit(title, (14, y))
        y += 28
        for ln in state.log_lines:
            t = self.font_sm.render(ln, True, S.COLOR_TEXT)
            self.screen.blit(t, (14, y))
            y += 18

    def _draw_gameover(self, state):
        overlay = pygame.Surface((S.SCREEN_WIDTH, S.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))
        if state.winner:
            msg = f"{map_data.FACTIONS[state.winner][0]} 승리!"
        else:
            msg = "게임 종료"
        t = self.font_lg.render(msg, True, S.COLOR_HIGHLIGHT)
        self.screen.blit(t, (S.SCREEN_WIDTH // 2 - t.get_width() // 2,
                             S.SCREEN_HEIGHT // 2 - 20))

    # ---- 입력 보조 ----
    def army_rect(self, state, army):
        """군대 아이콘의 클릭 판정용 사각형."""
        n = state.nodes[army.node_id]
        rect = pygame.Rect(0, 0, 28, 22)
        rect.center = (n["x"] + 18, n["y"] - 20)
        return rect
