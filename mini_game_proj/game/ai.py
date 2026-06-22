"""간단한 AI 진영 행동.

각 AI 군대는: 인접한 적 군대가 있으면 (전투력 우위일 때) 공격하고,
없으면 인접한 적/중립 도시로 진격해 점령을 노린다. 마땅한 목표가 없으면
대기한다. 휴리스틱 수준의 MVP AI다.
"""

import random


def take_turn(state, faction, on_battle=None):
    """faction의 모든 군대를 1회씩 행동시킨다.

    on_battle: 전투 발생 시 호출할 핸들러(전술 전투 연동용).
    """
    armies = [a for a in state.player_armies(faction)]
    random.shuffle(armies)
    for army in armies:
        if army.moves_left <= 0:
            continue
        target = _choose_target(state, army)
        if target is not None:
            state.move_army(army, target, on_battle=on_battle)


def _choose_target(state, army):
    neighbors = list(state.adjacency[army.node_id])
    random.shuffle(neighbors)

    attack_targets = []   # (점수, node) 공격 가능 적
    expand_targets = []   # (점수, node) 비어있는 적/중립 도시
    own_moves = []        # 빈 아군/이동 후보

    for nid in neighbors:
        enemy = state.enemy_army_at(nid, army.faction)
        node = state.nodes[nid]
        if enemy is not None:
            # 전투력 우위일 때만 공격(약간의 도박 허용)
            if army.combat_power() >= enemy.combat_power() * 0.9:
                score = army.combat_power() - enemy.combat_power()
                if node["major"]:
                    score += 20000  # 주요 도심은 가치 높음
                attack_targets.append((score, nid))
        else:
            if node["owner"] != army.faction:
                score = 10000 + (15000 if node["major"] else 0)
                expand_targets.append((score, nid))
            else:
                own_moves.append((0, nid))

    for pool in (attack_targets, expand_targets):
        if pool:
            pool.sort(reverse=True)
            return pool[0][1]
    return None
