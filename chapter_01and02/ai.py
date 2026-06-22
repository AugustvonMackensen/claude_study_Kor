"""1P 모드용 간단한 휴리스틱 CPU.

각 빈칸에 대해 '내가 두었을 때의 공격 점수'와 '상대가 두었을 때의 방어 점수'를
합산하여 가장 높은 칸을 고른다.
"""

import random

from rules import BLACK, WHITE, EMPTY, SIZE, DIRECTIONS, in_board, is_forbidden

# 한 방향(라인) 패턴 점수표
_SCORES = {
    5: 1_000_000,   # 5목
    "open4": 100_000,
    "four": 10_000,    # 막힌 4
    "open3": 5_000,
    "three": 500,      # 막힌 3
    "open2": 200,
    "two": 50,
}


def _line_score(board, r, c, dr, dc, player):
    """(r,c) 에 player 돌이 있다고 보고 한 축의 패턴 점수를 매긴다."""
    # 연속 개수와 양끝 상태를 본다.
    cnt = 1
    open_ends = 0

    nr, nc = r + dr, c + dc
    while in_board(nr, nc) and board[nr][nc] == player:
        cnt += 1
        nr += dr
        nc += dc
    if in_board(nr, nc) and board[nr][nc] == EMPTY:
        open_ends += 1

    nr, nc = r - dr, c - dc
    while in_board(nr, nc) and board[nr][nc] == player:
        cnt += 1
        nr -= dr
        nc -= dc
    if in_board(nr, nc) and board[nr][nc] == EMPTY:
        open_ends += 1

    if cnt >= 5:
        return _SCORES[5]
    if open_ends == 0:
        return 0  # 양끝 다 막힘 → 가치 없음
    if cnt == 4:
        return _SCORES["open4"] if open_ends == 2 else _SCORES["four"]
    if cnt == 3:
        return _SCORES["open3"] if open_ends == 2 else _SCORES["three"]
    if cnt == 2:
        return _SCORES["open2"] if open_ends == 2 else _SCORES["two"]
    return 1


def _point_value(board, r, c, player):
    """(r,c) 에 player 가 두었을 때의 총 점수(4방향 합)."""
    board[r][c] = player
    total = sum(_line_score(board, r, c, dr, dc, player) for dr, dc in DIRECTIONS)
    board[r][c] = EMPTY
    return total


def _has_neighbor(board, r, c, dist=2):
    """주변 dist 칸 안에 돌이 있는지(탐색 범위 축소용)."""
    for dr in range(-dist, dist + 1):
        for dc in range(-dist, dist + 1):
            nr, nc = r + dr, c + dc
            if in_board(nr, nc) and board[nr][nc] != EMPTY:
                return True
    return False


def choose_move(board, player, renju_on):
    """CPU(player) 가 둘 위치 (r, c) 를 반환한다."""
    opponent = BLACK if player == WHITE else WHITE

    empties = [
        (r, c)
        for r in range(SIZE)
        for c in range(SIZE)
        if board[r][c] == EMPTY and _has_neighbor(board, r, c)
    ]
    if not empties:  # 첫 수: 중앙
        return SIZE // 2, SIZE // 2

    best_score = -1
    best_moves = []
    for r, c in empties:
        # 흑이면 금수 자리는 둘 수 없다.
        if is_forbidden(board, r, c, player, renju_on):
            continue
        attack = _point_value(board, r, c, player)
        defense = _point_value(board, r, c, opponent)
        score = attack + defense * 0.9
        if score > best_score:
            best_score = score
            best_moves = [(r, c)]
        elif score == best_score:
            best_moves.append((r, c))

    if not best_moves:  # 전부 금수인 극단적 상황
        return random.choice(empties)
    return random.choice(best_moves)
