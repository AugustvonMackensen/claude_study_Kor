"""게임 상태와 턴 진행 로직.

월드 상태(노드 소유권, 군대 목록, 현재 턴/진영)를 보유하고, 군대 이동과
전투 발생, 도시 점령, 턴 종료/승리 판정을 처리한다.
"""

import copy

from . import map_data, battle
from .army import Army


class GameState:
    def __init__(self):
        self.nodes = copy.deepcopy(map_data.NODES)
        self.adjacency = map_data.build_adjacency()
        self.armies = [
            Army(a["faction"], a["node"], a["troops"], a["general"])
            for a in map_data.INITIAL_ARMIES
        ]
        self.armies += [
            Army(f["faction"], f["node"], f["troops"], None, domain="sea")
            for f in map_data.INITIAL_FLEETS
        ]
        # 진영 턴 순서: 플레이어(프랑스)가 먼저, 이후 AI 진영
        self.faction_order = ["france", "britain", "prussia",
                              "austria", "russia", "ottoman"]
        self.turn_number = 1
        self.current_faction = self.faction_order[0]
        self.log_lines = ["나폴레옹 전쟁이 시작되었다. 유럽을 정복하라."]
        self.game_over = False
        self.winner = None
        self._start_faction_turn(self.current_faction)

    # ---- 조회 헬퍼 ----
    def armies_at(self, node_id):
        return [a for a in self.armies if a.node_id == node_id]

    def army_at(self, node_id, faction=None):
        for a in self.armies:
            if a.node_id == node_id and (faction is None or a.faction == faction):
                return a
        return None

    def enemy_army_at(self, node_id, faction):
        for a in self.armies:
            if a.node_id == node_id and a.faction != faction:
                return a
        return None

    def player_armies(self, faction):
        return [a for a in self.armies if a.faction == faction]

    def log(self, msg):
        self.log_lines.append(msg)
        # 최근 8줄만 유지
        self.log_lines = self.log_lines[-8:]

    # ---- 턴 진행 ----
    def _start_faction_turn(self, faction):
        from .settings import ARMY_BASE_MOVE
        for a in self.player_armies(faction):
            a.moves_left = ARMY_BASE_MOVE

    def can_move(self, army, target_node):
        """army가 이번 턴에 target_node로 이동 가능한지."""
        if army.moves_left <= 0:
            return False
        return target_node in self.adjacency[army.node_id]

    def move_army(self, army, target_node, on_battle=None):
        """군대를 인접 노드로 이동. 적이 있으면 전투, 비었으면 점령.

        on_battle: 전투 발생 시 호출할 핸들러 (attacker, defender, on_city) -> result.
                   None이면 전략 즉시 판정(battle.resolve)을 사용한다.
        반환: 전투 결과 dict 또는 None.
        """
        if not self.can_move(army, target_node):
            return None

        army.moves_left -= 1
        enemy = self.enemy_army_at(target_node, army.faction)

        if enemy is None:
            army.node_id = target_node
            self._capture(target_node, army.faction)
            return None

        # 전투 발생
        on_city = self.nodes[target_node]["major"]
        if on_battle is not None:
            result = on_battle(army, enemy, on_city)
        else:
            result = battle.resolve(army, enemy, on_city=on_city)
        self.log(f"[{self.nodes[target_node]['name']}] {result['log']}")

        # 패자 제거
        loser = result["loser"]
        if loser in self.armies:
            self.armies.remove(loser)

        # 승자가 공격군이면 전진하여 점령
        if result["winner"] is army:
            army.node_id = target_node
            self._capture(target_node, army.faction)

        self._check_victory()
        return result

    def _capture(self, node_id, faction):
        node = self.nodes[node_id]
        if node.get("sea"):
            return  # 바다는 점령 대상이 아니다
        if node["owner"] != faction:
            old = map_data.FACTIONS[node["owner"]][0]
            new = map_data.FACTIONS[faction][0]
            node["owner"] = faction
            tag = " (주요 도심)" if node["major"] else ""
            self.log(f"{new}이(가) {node['name']}{tag}을(를) 점령! (이전: {old})")

    def end_turn(self):
        """현재 진영의 턴을 종료하고 다음 진영으로 넘긴다."""
        if self.game_over:
            return
        idx = self.faction_order.index(self.current_faction)
        next_idx = (idx + 1) % len(self.faction_order)
        if next_idx == 0:
            self.turn_number += 1
        self.current_faction = self.faction_order[next_idx]
        # 소멸한 진영은 건너뛴다
        guard = 0
        while not self._faction_alive(self.current_faction) and guard < len(self.faction_order):
            idx = self.faction_order.index(self.current_faction)
            next_idx = (idx + 1) % len(self.faction_order)
            if next_idx == 0:
                self.turn_number += 1
            self.current_faction = self.faction_order[next_idx]
            guard += 1
        self._start_faction_turn(self.current_faction)
        self._check_victory()

    def _faction_alive(self, faction):
        """진영이 군대나 도시를 하나라도 보유하면 생존."""
        if any(a.faction == faction for a in self.armies):
            return True
        return any(n["owner"] == faction for n in self.nodes.values())

    def _check_victory(self):
        """승리 판정: 플레이어 외 모든 군사 진영이 소멸하면 정복 승리."""
        military_factions = [f for f in self.faction_order]
        alive = [f for f in military_factions if self._faction_alive(f)]
        if len(alive) == 1:
            self.game_over = True
            self.winner = alive[0]
            self.log(f"*** {map_data.FACTIONS[alive[0]][0]} 정복 승리! ***")
        elif map_data.PLAYER_FACTION not in alive:
            self.game_over = True
            self.winner = alive[0] if alive else None
            self.log("*** 프랑스 패망... 게임 종료 ***")
