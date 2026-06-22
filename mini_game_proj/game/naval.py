"""해전 전술 전투.

바다에서 함대가 충돌하면 이 모듈이 해전을 진행한다. 함대는 전열함·프리깃·
브릭·슬루프로 나뉘며(CLAUDE.md), 현측 포격(broadside, 원거리)으로 싸운다.
바람(풍향)이 이동에 영향을 준다: 순풍이면 빠르고 역풍이면 느리다.

진입점:
    run_battle(screen, clock, attacker_fleet, defender_fleet, on_city, place)
        -> result dict (battle.resolve와 동일한 형태)
"""

import heapq
import random

import pygame

from . import settings as S
from . import map_data
from . import sprites
from . import audio
from . import battle as strat_battle
from .ui import load_font

COLS, ROWS = 20, 13
TILE = 48
OX, OY = 28, 64
PANEL_X = OX + COLS * TILE + 12

# ---- 바다 지형 ----
SEA, SHALLOW, LAND = range(3)
TERRAIN = {
    SEA:     dict(name="외해", cost=1,    color=(46, 86, 138)),
    SHALLOW: dict(name="천해", cost=2,    color=(70, 120, 168)),
    LAND:    dict(name="해안", cost=None, color=(96, 116, 78)),
}

# ---- 함선 타입 ----
SHIP_STATS = {
    "ship_of_line": dict(name="전열함", atk=1.80, dfn=1.60, move=4, rng=4, letter="전"),
    "frigate":      dict(name="프리깃", atk=1.20, dfn=1.00, move=6, rng=3, letter="프"),
    "brig":         dict(name="브릭",   atk=0.85, dfn=0.70, move=7, rng=2, letter="브"),
    "sloop":        dict(name="슬루프", atk=0.65, dfn=0.55, move=8, rng=2, letter="슬"),
}

WIND_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
WIND_NAME = {(1, 0): "서풍 →", (-1, 0): "동풍 ←", (0, 1): "북풍 ↓", (0, -1): "남풍 ↑"}

MAX_PHASES = 30


def cheb(c1, r1, c2, r2):
    return max(abs(c1 - c2), abs(r1 - r2))


class Ship:
    _seq = 0

    def __init__(self, side, faction, stype, men):
        Ship._seq += 1
        self.id = Ship._seq
        self.side = side
        self.faction = faction
        self.type = stype
        self.men = men
        self.col = 0
        self.row = 0
        self.moved = False
        self.attacked = False

    @property
    def stats(self):
        return SHIP_STATS[self.type]

    @property
    def move(self):
        return self.stats["move"]

    @property
    def rng(self):
        return self.stats["rng"]


def make_ships(fleet, side):
    troops = fleet.troops
    n = max(3, min(8, troops // 5000))
    types = []
    for i in range(n):
        if i < max(1, n // 4) and troops >= 16000:
            types.append("ship_of_line")
        elif i < n // 2:
            types.append("frigate")
        elif i < n * 3 // 4:
            types.append("brig")
        else:
            types.append("sloop")
    base = troops // n
    rem = troops - base * n
    ships = []
    for i, t in enumerate(types):
        men = base + (rem if i == 0 else 0)
        ships.append(Ship(side, fleet.faction, t, men))
    return ships


class NavalBattle:
    def __init__(self, attacker_fleet, defender_fleet, on_city, place):
        self.attacker_fleet = attacker_fleet
        self.defender_fleet = defender_fleet
        self.on_city = on_city
        self.place = place
        self.attacker_faction = attacker_fleet.faction
        self.defender_faction = defender_fleet.faction

        self.terrain = [[SEA] * COLS for _ in range(ROWS)]
        self._generate_sea()
        self.wind = random.choice(WIND_DIRS)

        self.ships = []
        self._deploy(attacker_fleet, "attacker")
        self._deploy(defender_fleet, "defender")

        self.player_side = ("attacker" if self.attacker_faction == map_data.PLAYER_FACTION
                            else "defender" if self.defender_faction == map_data.PLAYER_FACTION
                            else None)
        self.phase = 0
        self.side = "attacker"
        self.selected = set()
        self.finished = False
        self.victor = None
        self.result = None
        self.flash = []
        self._begin_phase()

    # ---------- 지형 ----------
    def _generate_sea(self):
        # 가장자리에 약간의 해안/천해(섬·연안). 가운데는 외해.
        for r in range(ROWS):
            for c in range(COLS):
                edge = (c < 1 or c >= COLS - 1 or r < 1 or r >= ROWS - 1)
                if edge and random.random() < 0.30:
                    self.terrain[r][c] = LAND
        # 작은 섬 1~2개
        for _ in range(random.randint(1, 2)):
            ic = random.randint(4, COLS - 5)
            ir = random.randint(3, ROWS - 4)
            self.terrain[ir][ic] = LAND
            for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if 0 <= ic + dc < COLS and 0 <= ir + dr < ROWS and random.random() < 0.5:
                    self.terrain[ir + dr][ic + dc] = SHALLOW
        # 해안 주변 천해
        for r in range(ROWS):
            for c in range(COLS):
                if self.terrain[r][c] != SEA:
                    continue
                for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nc, nr = c + dc, r + dr
                    if 0 <= nc < COLS and 0 <= nr < ROWS and self.terrain[nr][nc] == LAND:
                        if random.random() < 0.4:
                            self.terrain[r][c] = SHALLOW
                        break

    def _wind_factor(self, sdx, sdy):
        """진행 방향이 풍향과 같으면 빠르게(0.6), 반대면 느리게(1.8)."""
        dot = sdx * self.wind[0] + sdy * self.wind[1]
        if dot > 0:
            return 0.6
        if dot < 0:
            return 1.8
        return 1.0

    # ---------- 배치 ----------
    def _deploy(self, fleet, side):
        ships = make_ships(fleet, side)
        cols = list(range(0, 3)) if side == "attacker" else list(range(COLS - 3, COLS))
        if side == "defender":
            cols.reverse()
        center = ROWS // 2
        tiles = []
        for c in cols:
            for r in range(ROWS):
                if self.terrain[r][c] != LAND and self.ship_at(c, r) is None:
                    tiles.append((c, r))
        tiles.sort(key=lambda cr: (abs(cr[1] - center),
                                   cr[0] if side == "attacker" else -cr[0]))
        for u, (c, r) in zip(ships, tiles):
            u.col, u.row = c, r
            self.ships.append(u)

    # ---------- 조회 ----------
    def ship_at(self, c, r):
        for u in self.ships:
            if u.col == c and u.row == r:
                return u
        return None

    def side_ships(self, side):
        return [u for u in self.ships if u.side == side]

    def enemy_side(self, side):
        return "defender" if side == "attacker" else "attacker"

    def reachable(self, ship):
        start = (ship.col, ship.row)
        dist = {start: 0.0}
        pq = [(0.0, start)]
        move = ship.move
        while pq:
            d, (c, r) = heapq.heappop(pq)
            if d > dist.get((c, r), 1e9):
                continue
            for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nc, nr = c + dc, r + dr
                if not (0 <= nc < COLS and 0 <= nr < ROWS):
                    continue
                base = TERRAIN[self.terrain[nr][nc]]["cost"]
                if base is None:
                    continue
                if self.ship_at(nc, nr) is not None:
                    continue
                nd = d + base * self._wind_factor(dc, dr)
                if nd <= move + 1e-6 and nd < dist.get((nc, nr), 1e9):
                    dist[(nc, nr)] = nd
                    heapq.heappush(pq, (nd, (nc, nr)))
        dist.pop(start, None)
        return dist

    # ---------- 전투(현측 포격) ----------
    def attack(self, atk, dfn):
        at, dt = atk.stats, dfn.stats
        a_power = atk.men * at["atk"] * random.uniform(0.85, 1.15)
        d_power = dfn.men * dt["dfn"] * random.uniform(0.85, 1.15)
        frac = max(0.08, min(0.65, 0.30 * (a_power / max(d_power, 1))))
        d_loss = int(dfn.men * frac)
        dfn.men -= d_loss
        self.flash.append([dfn.col, dfn.row, f"-{d_loss}", 30])
        audio.play("cannon")

        if dfn.men > 0 and cheb(atk.col, atk.row, dfn.col, dfn.row) == 1:
            cfrac = max(0.05, min(0.5, 0.22 * (d_power / max(a_power, 1))))
            a_loss = int(atk.men * cfrac)
            atk.men -= a_loss
            self.flash.append([atk.col, atk.row, f"-{a_loss}", 30])
        atk.attacked = True
        atk.moved = True
        self.remove_sunk()

    def remove_sunk(self):
        sunk = [u for u in self.ships if u.men <= 150]
        for u in sunk:
            self.ships.remove(u)
            self.selected.discard(u.id)

    # ---------- 명령 ----------
    def move_toward(self, ship, tc, tr):
        if ship.moved:
            return
        reach = self.reachable(ship)
        if not reach:
            ship.moved = True
            return
        best = min(reach, key=lambda cr: (cheb(cr[0], cr[1], tc, tr), reach[cr]))
        ship.col, ship.row = best
        ship.moved = True
        audio.play("sail")

    def try_attack(self, ship, target):
        if ship.attacked:
            return False
        if cheb(ship.col, ship.row, target.col, target.row) <= ship.rng:
            self.attack(ship, target)
            return True
        if ship.moved:
            return False
        reach = self.reachable(ship)
        cand = [cr for cr in reach
                if cheb(cr[0], cr[1], target.col, target.row) <= ship.rng]
        if not cand:
            return False
        best = min(cand, key=lambda cr: reach[cr])
        ship.col, ship.row = best
        ship.moved = True
        if cheb(ship.col, ship.row, target.col, target.row) <= ship.rng:
            self.attack(ship, target)
            return True
        return False

    # ---------- 페이즈/승패 ----------
    def _begin_phase(self):
        for u in self.side_ships(self.side):
            u.moved = False
            u.attacked = False
        self.selected.clear()
        self._check_finish()

    def end_phase(self):
        if self.finished:
            return
        self.phase += 1
        self.side = self.enemy_side(self.side)
        if self.phase >= MAX_PHASES:
            self._decide_by_strength()
            return
        self._begin_phase()

    def _check_finish(self):
        att = self.side_ships("attacker")
        dfn = self.side_ships("defender")
        if not dfn and not att:
            self._finish("defender")
        elif not dfn:
            self._finish("attacker")
        elif not att:
            self._finish("defender")

    def _decide_by_strength(self):
        a = sum(u.men for u in self.side_ships("attacker"))
        d = sum(u.men for u in self.side_ships("defender"))
        self._finish("attacker" if a > d else "defender")

    def _finish(self, victor):
        self.finished = True
        self.victor = victor
        self.result = self._build_result()
        if self.player_side:
            audio.play("victory" if victor == self.player_side else "defeat")

    def _build_result(self):
        att_men = sum(u.men for u in self.side_ships("attacker"))
        def_men = sum(u.men for u in self.side_ships("defender"))
        att0, def0 = self.attacker_fleet.troops, self.defender_fleet.troops
        if self.victor == "attacker":
            winner, loser = self.attacker_fleet, self.defender_fleet
            winner.troops = max(1000, att_men)
            loser.troops = 0
        else:
            winner, loser = self.defender_fleet, self.attacker_fleet
            winner.troops = max(1000, def_men)
            loser.troops = 0
        a_loss = att0 - (att_men if self.victor == "attacker" else 0)
        d_loss = def0 - (def_men if self.victor == "defender" else 0)
        wname = map_data.FACTIONS[winner.faction][0]
        log = f"{wname} 해전 승리! 공격 손실 {max(0,a_loss):,} / 방어 손실 {max(0,d_loss):,}"
        return {"winner": winner, "loser": loser,
                "attacker_losses": max(0, a_loss),
                "defender_losses": max(0, d_loss), "log": log}

    def auto_resolve(self):
        self.result = strat_battle.resolve(self.attacker_fleet, self.defender_fleet,
                                            on_city=self.on_city)
        self.victor = ("attacker" if self.result["winner"] is self.attacker_fleet
                       else "defender")
        self.finished = True

    # ---------- AI ----------
    def ai_phase(self):
        side = self.side
        enemy = self.enemy_side(side)
        for u in list(self.side_ships(side)):
            if u not in self.ships:
                continue
            targets = self.side_ships(enemy)
            if not targets:
                break
            target = min(targets, key=lambda t: cheb(u.col, u.row, t.col, t.row))
            if not self.try_attack(u, target):
                self.move_toward(u, target.col, target.row)
                t2 = min(self.side_ships(enemy),
                         key=lambda t: cheb(u.col, u.row, t.col, t.row), default=None)
                if t2 and cheb(u.col, u.row, t2.col, t2.row) <= u.rng and not u.attacked:
                    self.attack(u, t2)

    # ---------- 입력 ----------
    def tile_at_pixel(self, mx, my):
        c = (mx - OX) // TILE
        r = (my - OY) // TILE
        if 0 <= c < COLS and 0 <= r < ROWS:
            return int(c), int(r)
        return None

    def box_select(self, rect):
        self.selected.clear()
        for u in self.side_ships(self.player_side):
            px = OX + u.col * TILE + TILE // 2
            py = OY + u.row * TILE + TILE // 2
            if rect.collidepoint(px, py):
                self.selected.add(u.id)

    def click_action(self, c, r, additive=False):
        clicked = self.ship_at(c, r)
        if clicked and clicked.side == self.player_side:
            if additive:
                self.selected.symmetric_difference_update({clicked.id})
            else:
                self.selected = {clicked.id}
            audio.play("select")
            return
        sel = [u for u in self.ships if u.id in self.selected and u.side == self.player_side]
        if not sel:
            return
        if clicked and clicked.side != self.player_side:
            for u in sel:
                self.try_attack(u, clicked)
        else:
            for u in sel:
                self.move_toward(u, c, r)

    # ---------- 렌더링 ----------
    def draw(self, screen, fonts):
        f_sm, f_md, f_lg = fonts
        screen.fill((18, 30, 48))
        self._draw_sea(screen)
        self._draw_reachable(screen)
        self._draw_ships(screen, f_sm)
        self._draw_flash(screen, f_sm)
        self._draw_panel(screen, f_sm, f_md)
        self._draw_topbar(screen, f_md)
        if self.finished:
            self._draw_overlay(screen, f_lg, f_md)

    def _draw_sea(self, screen):
        for r in range(ROWS):
            for c in range(COLS):
                t = self.terrain[r][c]
                rect = pygame.Rect(OX + c * TILE, OY + r * TILE, TILE, TILE)
                pygame.draw.rect(screen, TERRAIN[t]["color"], rect)
                pygame.draw.rect(screen, (24, 36, 54), rect, 1)
                if t == SEA:
                    pygame.draw.arc(screen, (70, 110, 156),
                                    rect.inflate(-14, -22), 3.4, 6.0, 2)

    def _draw_reachable(self, screen):
        sel = [u for u in self.ships if u.id in self.selected]
        if len(sel) != 1 or sel[0].moved:
            return
        for (c, r) in self.reachable(sel[0]):
            s = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
            s.fill((120, 200, 230, 70))
            screen.blit(s, (OX + c * TILE, OY + r * TILE))

    def _draw_ships(self, screen, f_sm):
        for u in self.ships:
            x = OX + u.col * TILE
            y = OY + u.row * TILE
            color = map_data.FACTIONS[u.faction][1]
            spr = sprites.get_ship(color, u.type, TILE)
            if u.side == "defender":
                spr = pygame.transform.flip(spr, True, False)   # 마주보게
            screen.blit(spr, (x, y))
            if u.id in self.selected:
                pygame.draw.rect(screen, (255, 240, 160),
                                 (x + 2, y + 2, TILE - 4, TILE - 4), 2, border_radius=4)
            elif u.moved:
                s = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
                s.fill((0, 0, 0, 80))
                screen.blit(s, (x, y))
            men = f_sm.render(f"{u.men // 1000}k", True, (245, 245, 230))
            bg = pygame.Surface((men.get_width() + 4, men.get_height()), pygame.SRCALPHA)
            bg.fill((10, 14, 20, 160))
            screen.blit(bg, (x + TILE // 2 - men.get_width() // 2 - 2, y + TILE - 15))
            screen.blit(men, (x + TILE // 2 - men.get_width() // 2, y + TILE - 15))

    def _draw_flash(self, screen, f_sm):
        for fl in self.flash:
            c, r, text, frames = fl
            t = f_sm.render(text, True, (255, 180, 90))
            screen.blit(t, (OX + c * TILE + 6, OY + r * TILE - 4))
            fl[3] -= 1
        self.flash = [fl for fl in self.flash if fl[3] > 0]

    def _draw_panel(self, screen, f_sm, f_md):
        x = PANEL_X
        w = S.SCREEN_WIDTH - x - 12
        panel = pygame.Rect(x, OY, w, ROWS * TILE)
        pygame.draw.rect(screen, S.COLOR_PANEL, panel)
        pygame.draw.rect(screen, S.COLOR_PANEL_BORDER, panel, 2)
        y = OY + 12
        screen.blit(f_md.render("함대", True, S.COLOR_HIGHLIGHT), (x + 12, y)); y += 28
        screen.blit(f_sm.render(f"바람: {WIND_NAME[self.wind]}", True, (150, 210, 240)),
                    (x + 12, y)); y += 26

        sel = [u for u in self.ships if u.id in self.selected]
        if sel:
            for u in sel[:6]:
                line = f"{u.stats['name']} {u.men:,} (이동 {u.move}/사거리 {u.rng})"
                screen.blit(f_sm.render(line, True, S.COLOR_TEXT), (x + 12, y)); y += 22
        else:
            screen.blit(f_sm.render("함선 클릭/드래그로 선택", True, S.COLOR_TEXT_DIM),
                        (x + 12, y)); y += 22
        y += 12
        for side, label in (("attacker", "공격 함대"), ("defender", "방어 함대")):
            us = self.side_ships(side)
            men = sum(u.men for u in us)
            fac = self.attacker_faction if side == "attacker" else self.defender_faction
            color = map_data.FACTIONS[fac][1]
            pygame.draw.rect(screen, color, (x + 12, y + 3, 12, 12))
            screen.blit(f_sm.render(f"{label} {map_data.FACTIONS[fac][0]}: {len(us)}척 / {men // 1000}k",
                                    True, S.COLOR_TEXT), (x + 30, y)); y += 24
        y += 14
        for h in ["[좌클릭] 선택/이동/포격", "[드래그] 함대 묶어 선택",
                  "[Shift+클릭] 추가 선택", "[우클릭] 선택 해제",
                  "[Space] 턴 종료", "[A] 자동 전투"]:
            screen.blit(f_sm.render(h, True, S.COLOR_TEXT_DIM), (x + 12, y)); y += 20

    def _draw_topbar(self, screen, f_md):
        pygame.draw.rect(screen, S.COLOR_PANEL, (0, 0, S.SCREEN_WIDTH, 40))
        side_fac = self.attacker_faction if self.side == "attacker" else self.defender_faction
        you = " (당신)" if self.side == self.player_side else ""
        txt = (f"{self.place} 해전  |  바람 {WIND_NAME[self.wind]}  |  페이즈 {self.phase + 1}  |  "
               f"행동: {map_data.FACTIONS[side_fac][0]}{you}")
        screen.blit(f_md.render(txt, True, S.COLOR_TEXT), (14, 9))

    def _draw_overlay(self, screen, f_lg, f_md):
        ov = pygame.Surface((S.SCREEN_WIDTH, S.SCREEN_HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 170))
        screen.blit(ov, (0, 0))
        vfac = self.attacker_faction if self.victor == "attacker" else self.defender_faction
        won = (self.victor == self.player_side)
        msg = ("승리!" if won else "패배...") if self.player_side else "해전 종료"
        t = f_lg.render(f"{map_data.FACTIONS[vfac][0]} {msg}", True, S.COLOR_HIGHLIGHT)
        screen.blit(t, (S.SCREEN_WIDTH // 2 - t.get_width() // 2, S.SCREEN_HEIGHT // 2 - 30))
        sub = f_md.render("아무 키나 눌러 전략 지도로", True, S.COLOR_TEXT)
        screen.blit(sub, (S.SCREEN_WIDTH // 2 - sub.get_width() // 2, S.SCREEN_HEIGHT // 2 + 16))


def run_battle(screen, clock, attacker_fleet, defender_fleet, on_city, place):
    fonts = (load_font(15), load_font(18, bold=True), load_font(34, bold=True))
    b = NavalBattle(attacker_fleet, defender_fleet, on_city, place)
    drag_start = None
    dragging = False
    running = True
    while running:
        ai_turn = (b.player_side is None) or (b.side != b.player_side)
        if b.finished:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    running = False
            b.draw(screen, fonts); pygame.display.flip(); clock.tick(S.FPS)
            continue
        if ai_turn:
            b.draw(screen, fonts); pygame.display.flip(); pygame.time.delay(350)
            b.ai_phase()
            b.draw(screen, fonts); pygame.display.flip(); pygame.time.delay(350)
            b.end_phase()
            continue
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    b.end_phase()
                elif event.key == pygame.K_a:
                    b.auto_resolve()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    drag_start = event.pos
                    dragging = False
                elif event.button == 3:
                    b.selected.clear()
            elif event.type == pygame.MOUSEMOTION:
                if drag_start and event.buttons[0]:
                    if abs(event.pos[0] - drag_start[0]) > 6 or abs(event.pos[1] - drag_start[1]) > 6:
                        dragging = True
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if drag_start is None:
                    continue
                if dragging:
                    x0, y0 = drag_start
                    x1, y1 = event.pos
                    b.box_select(pygame.Rect(min(x0, x1), min(y0, y1),
                                             abs(x1 - x0), abs(y1 - y0)))
                else:
                    tile = b.tile_at_pixel(*event.pos)
                    if tile:
                        additive = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
                        b.click_action(tile[0], tile[1], additive)
                drag_start = None
                dragging = False
        b.draw(screen, fonts)
        if dragging and drag_start:
            mx, my = pygame.mouse.get_pos()
            x0, y0 = drag_start
            pygame.draw.rect(screen, (255, 240, 160),
                             pygame.Rect(min(x0, mx), min(y0, my), abs(mx - x0), abs(my - y0)), 1)
        pygame.display.flip()
        clock.tick(S.FPS)
    return b.result if b.result else strat_battle.resolve(
        attacker_fleet, defender_fleet, on_city=on_city)
