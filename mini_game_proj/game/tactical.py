"""육상 전투맵(전술 전투).

전략 지도에서 군대가 충돌하면 이 모듈이 전술 전투를 진행한다. 한 진영의 군대는
여러 '부대(연대)'로 나뉘며(개인 유닛이 아님 — CLAUDE.md), 플레이어는 부대를
드래그로 묶어 이동/공격시킨다. 지형은 강·다리·평원·설원·산맥·도심으로 구성되고
이동·전투에 영향을 준다.

핵심 진입점:
    run_battle(screen, clock, attacker_army, defender_army, on_city, kind, place)
        -> result dict (battle.resolve와 동일한 형태)

result 형태: dict(winner, loser, attacker_losses, defender_losses, log)
승자/패자 Army의 troops는 생존 병력으로 갱신되며, 패자는 0이 된다.
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

# ---- 그리드 레이아웃 ----
COLS, ROWS = 20, 13
TILE = 48
OX, OY = 28, 64                     # 그리드 좌상단 오프셋
PANEL_X = OX + COLS * TILE + 12     # 우측 정보 패널

# ---- 지형 ----
PLAINS, SNOW, MOUNTAIN, RIVER, BRIDGE, CITY = range(6)
TERRAIN = {
    PLAINS:   dict(name="평원", cost=1,    datk=1.00, ddef=1.00, color=(104, 134, 74)),
    SNOW:     dict(name="설원", cost=2,    datk=0.90, ddef=1.00, color=(214, 222, 232)),
    MOUNTAIN: dict(name="산맥", cost=2,    datk=0.90, ddef=1.35, color=(126, 116, 102)),
    RIVER:    dict(name="강",   cost=None, datk=1.00, ddef=1.00, color=(58, 108, 168)),
    BRIDGE:   dict(name="다리", cost=1,    datk=1.00, ddef=0.90, color=(150, 118, 78)),
    CITY:     dict(name="도심", cost=1,    datk=1.00, ddef=1.40, color=(168, 160, 150)),
}

# ---- 부대 타입 ----
UNIT_STATS = {
    "infantry":  dict(name="보병", atk=1.00, dfn=1.00, move=4, rng=1, letter="보"),
    "cavalry":   dict(name="기병", atk=1.40, dfn=0.80, move=7, rng=1, letter="기"),
    "artillery": dict(name="포병", atk=1.90, dfn=0.50, move=3, rng=4, letter="포"),
    "guard":     dict(name="근위", atk=1.50, dfn=1.40, move=4, rng=1, letter="근"),
}

MAX_PHASES = 32  # 무한 교착 방지(약 16턴)


def cheb(c1, r1, c2, r2):
    return max(abs(c1 - c2), abs(r1 - r2))


class Unit:
    _seq = 0

    def __init__(self, side, faction, utype, men):
        Unit._seq += 1
        self.id = Unit._seq
        self.side = side            # 'attacker' / 'defender'
        self.faction = faction
        self.type = utype
        self.men = men
        self.col = 0
        self.row = 0
        self.moved = False
        self.attacked = False

    @property
    def stats(self):
        return UNIT_STATS[self.type]

    @property
    def move(self):
        return self.stats["move"]

    @property
    def rng(self):
        return self.stats["rng"]


def make_units(army, side):
    """Army(병력)를 여러 부대로 분할한다."""
    troops = army.troops
    n = max(3, min(8, troops // 6000))
    types = ["infantry"] * n
    if troops >= 14000:
        types[0] = "artillery"
    cav = max(1, n // 4)
    for i in range(cav):
        idx = 1 + i
        if idx < n:
            types[idx] = "cavalry"
    if army.has_guard:
        types[-1] = "guard"

    base = troops // n
    rem = troops - base * n
    units = []
    for i, t in enumerate(types):
        men = base + (rem if i == 0 else 0)
        units.append(Unit(side, army.faction, t, men))
    return units


class TacticalBattle:
    def __init__(self, attacker_army, defender_army, on_city, kind, place):
        self.attacker_army = attacker_army
        self.defender_army = defender_army
        self.on_city = on_city
        self.kind = kind
        self.place = place
        self.attacker_faction = attacker_army.faction
        self.defender_faction = defender_army.faction

        self.terrain = [[PLAINS] * COLS for _ in range(ROWS)]
        self.city_tiles = set()
        self._generate_terrain(kind)

        self.units = []
        self._deploy(attacker_army, "attacker")
        self._deploy(defender_army, "defender")

        # 플레이어가 조작하는 쪽
        self.player_side = ("attacker" if self.attacker_faction == map_data.PLAYER_FACTION
                            else "defender" if self.defender_faction == map_data.PLAYER_FACTION
                            else None)

        self.phase = 0
        self.side = "attacker"          # 현재 행동 진영
        self.selected = set()           # 선택된 부대 id
        self.reachable_cache = {}
        self.finished = False
        self.victor = None              # 'attacker'/'defender'
        self.result = None
        self.flash = []                 # (col,row,text,frames) 전투 표시
        self.log = f"{place} 전투 개시!"
        self._begin_phase()

    # ---------- 지형 생성 ----------
    def _generate_terrain(self, kind):
        cx, cy = COLS // 2, ROWS // 2
        if kind == "city":
            for c in range(COLS - 7, COLS - 4):
                for r in range(cy - 2, cy + 3):
                    if 0 <= r < ROWS:
                        self.terrain[r][c] = CITY
                        self.city_tiles.add((c, r))
            # 도시 앞 강 + 다리
            rc = COLS - 9
            for r in range(ROWS):
                self.terrain[r][rc] = RIVER
            self.terrain[cy][rc] = BRIDGE
            self.terrain[cy - 3][rc] = BRIDGE
        elif kind == "snow":
            for r in range(ROWS):
                for c in range(COLS):
                    if random.random() < 0.55:
                        self.terrain[r][c] = SNOW
                    elif random.random() < 0.08:
                        self.terrain[r][c] = MOUNTAIN
        elif kind == "mountain":
            # 가운데를 가로지르는 산맥 능선(통로 몇 곳)
            ridge = cx
            passes = {2, cy, ROWS - 3}
            for r in range(ROWS):
                if r in passes:
                    continue
                self.terrain[r][ridge] = MOUNTAIN
                if random.random() < 0.5:
                    self.terrain[r][ridge - 1] = MOUNTAIN
                if random.random() < 0.5:
                    self.terrain[r][ridge + 1] = MOUNTAIN
        else:  # plains: 강을 가로질러 다리로 건넘
            rc = cx
            for r in range(ROWS):
                self.terrain[r][rc] = RIVER
            self.terrain[cy][rc] = BRIDGE
            self.terrain[2][rc] = BRIDGE
            self.terrain[ROWS - 3][rc] = BRIDGE

    # ---------- 배치 ----------
    def _deploy(self, army, side):
        units = make_units(army, side)
        if side == "attacker":
            cols = list(range(0, 3))
        else:
            cols = list(range(COLS - (8 if self.kind == "city" else 3), COLS))
            cols.reverse()
        center = ROWS // 2
        tiles = []
        for c in cols:
            for r in range(ROWS):
                if TERRAIN[self.terrain[r][c]]["cost"] is not None and self.unit_at(c, r) is None:
                    tiles.append((c, r))
        tiles.sort(key=lambda cr: (abs(cr[1] - center),
                                   cr[0] if side == "attacker" else -cr[0]))
        for u, (c, r) in zip(units, tiles):
            u.col, u.row = c, r
            self.units.append(u)

    # ---------- 조회 ----------
    def unit_at(self, c, r):
        for u in self.units:
            if u.col == c and u.row == r:
                return u
        return None

    def side_units(self, side):
        return [u for u in self.units if u.side == side]

    def enemy_side(self, side):
        return "defender" if side == "attacker" else "attacker"

    def reachable(self, unit):
        """Dijkstra로 이동 가능한 타일 -> 비용 dict(시작/점유 타일 제외)."""
        start = (unit.col, unit.row)
        dist = {start: 0}
        pq = [(0, start)]
        move = unit.move
        while pq:
            d, (c, r) = heapq.heappop(pq)
            if d > dist.get((c, r), 1e9):
                continue
            for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nc, nr = c + dc, r + dr
                if not (0 <= nc < COLS and 0 <= nr < ROWS):
                    continue
                cost = TERRAIN[self.terrain[nr][nc]]["cost"]
                if cost is None:
                    continue
                if self.unit_at(nc, nr) is not None:
                    continue
                nd = d + cost
                if nd <= move and nd < dist.get((nc, nr), 1e9):
                    dist[(nc, nr)] = nd
                    heapq.heappush(pq, (nd, (nc, nr)))
        dist.pop(start, None)
        return dist

    # ---------- 전투 ----------
    def attack(self, atk, dfn):
        at, dt = atk.stats, dfn.stats
        a_terr = TERRAIN[self.terrain[atk.row][atk.col]]
        d_terr = TERRAIN[self.terrain[dfn.row][dfn.col]]
        a_power = atk.men * at["atk"] * a_terr["datk"] * random.uniform(0.85, 1.15)
        d_power = dfn.men * dt["dfn"] * d_terr["ddef"] * random.uniform(0.85, 1.15)

        frac = max(0.10, min(0.75, 0.35 * (a_power / max(d_power, 1))))
        d_loss = int(dfn.men * frac)
        dfn.men -= d_loss
        self.flash.append([dfn.col, dfn.row, f"-{d_loss}", 30])

        adjacent = cheb(atk.col, atk.row, dfn.col, dfn.row) == 1
        if dfn.men > 0 and adjacent:
            cfrac = max(0.05, min(0.5, 0.20 * (d_power / max(a_power, 1))))
            a_loss = int(atk.men * cfrac)
            atk.men -= a_loss
            self.flash.append([atk.col, atk.row, f"-{a_loss}", 30])

        atk.attacked = True
        atk.moved = True
        audio.play("cannon" if atk.type == "artillery" else "musket")
        self.remove_dead()

    def remove_dead(self):
        dead = [u for u in self.units if u.men <= 200]
        for u in dead:
            self.units.remove(u)
            self.selected.discard(u.id)

    # ---------- 명령(플레이어/AI 공용) ----------
    def order_move(self, unit, dest_c, dest_r):
        if unit.moved:
            return False
        reach = self.reachable(unit)
        if (dest_c, dest_r) in reach:
            unit.col, unit.row = dest_c, dest_r
            unit.moved = True
            return True
        return False

    def move_toward(self, unit, tc, tr):
        """목표 타일에 가장 가까운 도달 가능 타일로 이동."""
        if unit.moved:
            return
        reach = self.reachable(unit)
        if not reach:
            unit.moved = True
            return
        best = min(reach, key=lambda cr: (cheb(cr[0], cr[1], tc, tr), reach[cr]))
        unit.col, unit.row = best
        unit.moved = True

    def try_attack(self, unit, target):
        """사거리 안이면 즉시 공격, 아니면 사거리로 이동 후 공격."""
        if unit.attacked:
            return False
        if cheb(unit.col, unit.row, target.col, target.row) <= unit.rng:
            self.attack(unit, target)
            return True
        if unit.moved:
            return False
        reach = self.reachable(unit)
        cand = [cr for cr in reach
                if cheb(cr[0], cr[1], target.col, target.row) <= unit.rng]
        if not cand:
            return False
        best = min(cand, key=lambda cr: reach[cr])
        unit.col, unit.row = best
        unit.moved = True
        if cheb(unit.col, unit.row, target.col, target.row) <= unit.rng:
            self.attack(unit, target)
            return True
        return False

    # ---------- 페이즈/승패 ----------
    def _begin_phase(self):
        for u in self.side_units(self.side):
            u.moved = False
            u.attacked = False
        self.selected.clear()
        self._check_finish(start_side=self.side)

    def end_phase(self):
        if self.finished:
            return
        self.phase += 1
        self.side = self.enemy_side(self.side)
        if self.phase >= MAX_PHASES:
            self._decide_by_strength()
            return
        self._begin_phase()

    def _check_finish(self, start_side=None):
        att = self.side_units("attacker")
        dfn = self.side_units("defender")
        if not att and not dfn:
            self._finish("defender")
        elif not dfn:
            self._finish("attacker")
        elif not att:
            self._finish("defender")
        elif start_side == "attacker" and self.city_tiles:
            # 공격군이 도심을 점령하면 승리
            if any((u.col, u.row) in self.city_tiles for u in att):
                self._finish("attacker")

    def _decide_by_strength(self):
        a = sum(u.men for u in self.side_units("attacker"))
        d = sum(u.men for u in self.side_units("defender"))
        self._finish("attacker" if a > d else "defender")

    def _finish(self, victor):
        self.finished = True
        self.victor = victor
        self.result = self._build_result()
        if self.player_side:
            audio.play("victory" if victor == self.player_side else "defeat")

    def _build_result(self):
        att_men = sum(u.men for u in self.side_units("attacker"))
        def_men = sum(u.men for u in self.side_units("defender"))
        att0 = self.attacker_army.troops
        def0 = self.defender_army.troops

        if self.victor == "attacker":
            winner, loser = self.attacker_army, self.defender_army
            winner.troops = max(1000, att_men)
            loser.troops = 0
        else:
            winner, loser = self.defender_army, self.attacker_army
            winner.troops = max(1000, def_men)
            loser.troops = 0

        a_loss = att0 - (att_men if self.victor == "attacker" else 0)
        d_loss = def0 - (def_men if self.victor == "defender" else 0)
        wname = map_data.FACTIONS[winner.faction][0]
        log = f"{wname} 승리! 공격 손실 {max(0,a_loss):,} / 방어 손실 {max(0,d_loss):,}"
        return {"winner": winner, "loser": loser,
                "attacker_losses": max(0, a_loss),
                "defender_losses": max(0, d_loss), "log": log}

    def auto_resolve(self):
        """남은 전투를 전략 판정으로 즉시 종결(자동 전투)."""
        self.result = strat_battle.resolve(self.attacker_army, self.defender_army,
                                            on_city=self.on_city)
        self.victor = ("attacker" if self.result["winner"] is self.attacker_army
                       else "defender")
        self.finished = True

    # ---------- AI ----------
    def ai_phase(self):
        side = self.side
        enemy = self.enemy_side(side)
        for u in list(self.side_units(side)):
            if u not in self.units:
                continue
            targets = self.side_units(enemy)
            if not targets:
                break
            target = min(targets, key=lambda t: cheb(u.col, u.row, t.col, t.row))
            if not self.try_attack(u, target):
                self.move_toward(u, target.col, target.row)
                # 이동 후 다시 공격 시도
                t2 = min(self.side_units(enemy),
                         key=lambda t: cheb(u.col, u.row, t.col, t.row),
                         default=None)
                if t2 is not None and cheb(u.col, u.row, t2.col, t2.row) <= u.rng:
                    if not u.attacked:
                        self.attack(u, t2)

    # ---------- 플레이어 입력 ----------
    def tile_at_pixel(self, mx, my):
        c = (mx - OX) // TILE
        r = (my - OY) // TILE
        if 0 <= c < COLS and 0 <= r < ROWS:
            return int(c), int(r)
        return None

    def box_select(self, rect):
        self.selected.clear()
        for u in self.side_units(self.player_side):
            px = OX + u.col * TILE + TILE // 2
            py = OY + u.row * TILE + TILE // 2
            if rect.collidepoint(px, py):
                self.selected.add(u.id)

    def click_action(self, c, r, additive=False):
        """플레이어 클릭 처리: 아군 선택 / 이동 / 공격."""
        clicked = self.unit_at(c, r)
        if clicked and clicked.side == self.player_side:
            if additive:
                self.selected.symmetric_difference_update({clicked.id})
            else:
                self.selected = {clicked.id}
            audio.play("select")
            return
        sel_units = [u for u in self.units if u.id in self.selected
                     and u.side == self.player_side]
        if not sel_units:
            return
        if clicked and clicked.side != self.player_side:
            for u in sel_units:
                self.try_attack(u, clicked)
        else:
            for u in sel_units:
                self.move_toward(u, c, r)
            audio.play("move")

    # ---------- 렌더링 ----------
    def draw(self, screen, fonts):
        f_sm, f_md, f_lg = fonts
        screen.fill((20, 24, 30))
        self._draw_terrain(screen, f_sm)
        self._draw_reachable(screen)
        self._draw_units(screen, f_sm)
        self._draw_flash(screen, f_sm)
        self._draw_panel(screen, f_sm, f_md)
        self._draw_topbar(screen, f_md)
        if self.finished:
            self._draw_overlay(screen, f_lg, f_md)

    def _draw_terrain(self, screen, f_sm):
        for r in range(ROWS):
            for c in range(COLS):
                t = self.terrain[r][c]
                rect = pygame.Rect(OX + c * TILE, OY + r * TILE, TILE, TILE)
                pygame.draw.rect(screen, TERRAIN[t]["color"], rect)
                pygame.draw.rect(screen, (30, 34, 40), rect, 1)
                if (c, r) in self.city_tiles:
                    pygame.draw.rect(screen, (110, 100, 90), rect.inflate(-10, -10), 2)

    def _draw_reachable(self, screen):
        sel = [u for u in self.units if u.id in self.selected]
        if len(sel) != 1:
            return
        u = sel[0]
        if u.moved:
            return
        for (c, r) in self.reachable(u):
            s = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
            s.fill((120, 220, 140, 70))
            screen.blit(s, (OX + c * TILE, OY + r * TILE))

    def _draw_units(self, screen, f_sm):
        for u in self.units:
            x = OX + u.col * TILE
            y = OY + u.row * TILE
            color = map_data.FACTIONS[u.faction][1]
            rect = pygame.Rect(x + 3, y + 3, TILE - 6, TILE - 6)
            # 진영색 칩 + 병종 스프라이트
            chip = pygame.Surface(rect.size, pygame.SRCALPHA)
            chip.fill((*color, 90))
            screen.blit(chip, rect.topleft)
            spr = sprites.get_soldier(color, u.type, rect.width)
            if u.side == "defender":
                spr = pygame.transform.flip(spr, True, False)
            screen.blit(spr, rect.topleft)
            if u.id in self.selected:
                pygame.draw.rect(screen, (255, 240, 160), rect, 3, border_radius=5)
            elif u.moved:
                s = pygame.Surface(rect.size, pygame.SRCALPHA)
                s.fill((0, 0, 0, 90))
                screen.blit(s, rect.topleft)
            pygame.draw.rect(screen, (15, 15, 20), rect, 1, border_radius=5)
            men = f_sm.render(f"{u.men // 1000}k", True, (245, 245, 235))
            bg = pygame.Surface((men.get_width() + 4, men.get_height()), pygame.SRCALPHA)
            bg.fill((10, 14, 20, 170))
            screen.blit(bg, (rect.centerx - men.get_width() // 2 - 2, rect.bottom - 15))
            screen.blit(men, (rect.centerx - men.get_width() // 2, rect.bottom - 15))

    def _draw_flash(self, screen, f_sm):
        for fl in self.flash:
            c, r, text, frames = fl
            t = f_sm.render(text, True, (255, 120, 110))
            screen.blit(t, (OX + c * TILE + 6, OY + r * TILE - 6))
            fl[3] -= 1
        self.flash = [fl for fl in self.flash if fl[3] > 0]

    def _draw_panel(self, screen, f_sm, f_md):
        x = PANEL_X
        w = S.SCREEN_WIDTH - x - 12
        panel = pygame.Rect(x, OY, w, ROWS * TILE)
        pygame.draw.rect(screen, S.COLOR_PANEL, panel)
        pygame.draw.rect(screen, S.COLOR_PANEL_BORDER, panel, 2)
        y = OY + 12
        title = f_md.render("부대", True, S.COLOR_HIGHLIGHT)
        screen.blit(title, (x + 12, y)); y += 30

        sel = [u for u in self.units if u.id in self.selected]
        if sel:
            for u in sel[:6]:
                line = f"{u.stats['name']} {u.men:,} (이동 {u.move}/사거리 {u.rng})"
                t = f_sm.render(line, True, S.COLOR_TEXT)
                screen.blit(t, (x + 12, y)); y += 22
        else:
            t = f_sm.render("부대 클릭/드래그로 선택", True, S.COLOR_TEXT_DIM)
            screen.blit(t, (x + 12, y)); y += 22

        y += 14
        for side, label in (("attacker", "공격군"), ("defender", "방어군")):
            us = self.side_units(side)
            men = sum(u.men for u in us)
            fac = (self.attacker_faction if side == "attacker" else self.defender_faction)
            color = map_data.FACTIONS[fac][1]
            pygame.draw.rect(screen, color, (x + 12, y + 3, 12, 12))
            t = f_sm.render(f"{label} {map_data.FACTIONS[fac][0]}: {len(us)}부대 / {men // 1000}k",
                            True, S.COLOR_TEXT)
            screen.blit(t, (x + 30, y)); y += 24

        y += 16
        hints = ["[좌클릭] 선택/이동/공격",
                 "[드래그] 부대 묶어 선택",
                 "[Shift+클릭] 추가 선택",
                 "[우클릭] 선택 해제",
                 "[Space] 턴 종료",
                 "[A] 자동 전투"]
        for h in hints:
            t = f_sm.render(h, True, S.COLOR_TEXT_DIM)
            screen.blit(t, (x + 12, y)); y += 20

    def _draw_topbar(self, screen, f_md):
        bar = pygame.Rect(0, 0, S.SCREEN_WIDTH, 40)
        pygame.draw.rect(screen, S.COLOR_PANEL, bar)
        side_fac = (self.attacker_faction if self.side == "attacker"
                    else self.defender_faction)
        you = " (당신)" if self.side == self.player_side else ""
        kind_name = {"city": "도심", "snow": "설원", "mountain": "산맥",
                     "plains": "평원"}.get(self.kind, "평원")
        txt = (f"{self.place} 전투 [{kind_name}]  |  페이즈 {self.phase + 1}  |  "
               f"행동: {map_data.FACTIONS[side_fac][0]}{you}")
        t = f_md.render(txt, True, S.COLOR_TEXT)
        screen.blit(t, (14, 9))

    def _draw_overlay(self, screen, f_lg, f_md):
        ov = pygame.Surface((S.SCREEN_WIDTH, S.SCREEN_HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 170))
        screen.blit(ov, (0, 0))
        vfac = (self.attacker_faction if self.victor == "attacker"
                else self.defender_faction)
        won = (self.victor == self.player_side)
        msg = ("승리!" if won else "패배...") if self.player_side else "전투 종료"
        t = f_lg.render(f"{map_data.FACTIONS[vfac][0]} {msg}", True, S.COLOR_HIGHLIGHT)
        screen.blit(t, (S.SCREEN_WIDTH // 2 - t.get_width() // 2, S.SCREEN_HEIGHT // 2 - 30))
        sub = f_md.render("아무 키나 눌러 전략 지도로", True, S.COLOR_TEXT)
        screen.blit(sub, (S.SCREEN_WIDTH // 2 - sub.get_width() // 2, S.SCREEN_HEIGHT // 2 + 16))


def pick_kind(node):
    """전투 위치 노드로부터 전장 종류를 고른다."""
    if node.get("major"):
        return "city"
    nid_owner = node
    SNOW = {"moscow", "smolensk", "kiev"}
    MOUNTAIN = {"milan", "vienna", "belgrade"}
    name_to_id = {v["name"]: k for k, v in map_data.NODES.items()}
    nid = name_to_id.get(node["name"])
    if nid in SNOW:
        return "snow"
    if nid in MOUNTAIN:
        return "mountain"
    return "plains"


def run_battle(screen, clock, attacker_army, defender_army, on_city, kind, place):
    """전술 전투를 실행하고 결과 dict를 반환한다."""
    fonts = (load_font(15), load_font(18, bold=True), load_font(34, bold=True))
    b = TacticalBattle(attacker_army, defender_army, on_city, kind, place)

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
            b.draw(screen, fonts)
            pygame.display.flip()
            clock.tick(S.FPS)
            continue

        if ai_turn:
            b.draw(screen, fonts)
            pygame.display.flip()
            pygame.time.delay(350)
            b.ai_phase()
            b.draw(screen, fonts)
            pygame.display.flip()
            pygame.time.delay(350)
            b.end_phase()
            continue

        # 플레이어 페이즈
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
                if drag_start and (event.buttons[0]):
                    if abs(event.pos[0] - drag_start[0]) > 6 or abs(event.pos[1] - drag_start[1]) > 6:
                        dragging = True
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if drag_start is None:
                    continue
                if dragging:
                    x0, y0 = drag_start
                    x1, y1 = event.pos
                    rect = pygame.Rect(min(x0, x1), min(y0, y1),
                                       abs(x1 - x0), abs(y1 - y0))
                    b.box_select(rect)
                else:
                    tile = b.tile_at_pixel(*event.pos)
                    if tile:
                        mods = pygame.key.get_mods()
                        additive = bool(mods & pygame.KMOD_SHIFT)
                        b.click_action(tile[0], tile[1], additive)
                drag_start = None
                dragging = False

        b.draw(screen, fonts)
        if dragging and drag_start:
            mx, my = pygame.mouse.get_pos()
            x0, y0 = drag_start
            rect = pygame.Rect(min(x0, mx), min(y0, my), abs(mx - x0), abs(my - y0))
            pygame.draw.rect(screen, (255, 240, 160), rect, 1)
        pygame.display.flip()
        clock.tick(S.FPS)

    return b.result if b.result else strat_battle.resolve(
        attacker_army, defender_army, on_city=on_city)
