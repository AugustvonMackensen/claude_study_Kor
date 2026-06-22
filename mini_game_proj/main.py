"""나폴레옹 전쟁 전략 게임 - 진입점.

전략 지도 MVP: 플레이어는 프랑스를 맡아 군대를 이동시키고 도시를 점령한다.
턴을 종료하면 AI 진영들이 행동한다. 모든 군사 진영을 제압하면 정복 승리.

실행:
    .venv/Scripts/python.exe mini_game_proj/main.py
"""

import sys

import pygame

from game import settings as S
from game import map_data
from game import ai
from game import battle as strat_battle
from game import tactical
from game import naval
from game import audio
from game.game_state import GameState
from game.ui import Renderer


def compute_move_targets(state, army):
    """선택된 군대가 이번 턴 이동 가능한 인접 노드 집합."""
    if army is None or army.moves_left <= 0:
        return set()
    return set(state.adjacency[army.node_id])


def make_battle_dispatcher(screen, clock, state):
    """전투 발생 시 호출되는 핸들러를 만든다.

    플레이어가 공격/방어로 관여하는 전투는 전술 전투맵으로 전환하고,
    그 외(AI vs AI)는 전략 즉시 판정으로 빠르게 처리한다.
    """
    def dispatcher(attacker, defender, on_city):
        if map_data.PLAYER_FACTION not in (attacker.faction, defender.faction):
            return strat_battle.resolve(attacker, defender, on_city=on_city)
        node = state.nodes[defender.node_id]
        if node.get("sea"):
            return naval.run_battle(screen, clock, attacker, defender,
                                    on_city, node["name"])
        kind = tactical.pick_kind(node)
        return tactical.run_battle(screen, clock, attacker, defender,
                                   on_city, kind, node["name"])
    return dispatcher


def run_ai_turns(state, on_battle):
    """플레이어 차례가 다시 올 때까지 AI 진영들을 진행한다."""
    while not state.game_over and state.current_faction != map_data.PLAYER_FACTION:
        ai.take_turn(state, state.current_faction, on_battle=on_battle)
        state.end_turn()


def main():
    pygame.init()
    audio.init()
    pygame.display.set_caption(S.TITLE)
    screen = pygame.display.set_mode((S.SCREEN_WIDTH, S.SCREEN_HEIGHT))
    clock = pygame.time.Clock()

    state = GameState()
    renderer = Renderer(screen)
    selected = None
    dispatcher = make_battle_dispatcher(screen, clock, state)

    running = True
    while running:
        move_targets = compute_move_targets(state, selected)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    if not state.game_over and state.current_faction == map_data.PLAYER_FACTION:
                        selected = None
                        state.end_turn()
                        run_ai_turns(state, dispatcher)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if state.game_over:
                    continue
                if state.current_faction != map_data.PLAYER_FACTION:
                    continue
                handled = handle_click(state, renderer, event.pos, selected, dispatcher)
                selected = handled

        renderer.draw(state, selected, move_targets)
        pygame.display.flip()
        clock.tick(S.FPS)

    pygame.quit()
    sys.exit(0)


def handle_click(state, renderer, pos, selected, dispatcher):
    """클릭 처리. 선택된 군대가 있으면 이동 노드 판정, 없으면 아군 선택.

    반환: 새로운 selected 군대(또는 None).
    """
    mx, my = pos

    # 1) 이미 군대를 선택한 상태면, 이동 가능한 노드를 클릭했는지 확인
    if selected is not None and selected.faction == map_data.PLAYER_FACTION:
        for nid in state.adjacency[selected.node_id]:
            n = state.nodes[nid]
            if (mx - n["x"]) ** 2 + (my - n["y"]) ** 2 <= (S.CITY_RADIUS + 10) ** 2:
                if state.can_move(selected, nid):
                    audio.play("sail" if selected.is_fleet else "move")
                    state.move_army(selected, nid, on_battle=dispatcher)
                    # 이동/전투 후에도 이동력이 남아 있으면 계속 선택 유지
                    if selected in state.armies and selected.moves_left > 0:
                        return selected
                    return None

    # 2) 아군 군대 아이콘 클릭 → 선택
    for army in state.armies:
        if army.faction != map_data.PLAYER_FACTION:
            continue
        if renderer.army_rect(state, army).collidepoint(mx, my):
            audio.play("select")
            return army

    # 3) 빈 곳 클릭 → 선택 해제
    return None


if __name__ == "__main__":
    main()
