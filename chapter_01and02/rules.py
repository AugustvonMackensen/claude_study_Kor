"""오목 규칙: 승리 판정과 렌주(쌍삼 금지) 규칙 검사."""

EMPTY = 0
BLACK = 1
WHITE = 2

SIZE = 15
DIRECTIONS = [(1, 0), (0, 1), (1, 1), (1, -1)]  # 세로, 가로, ↘대각, ↗대각


def in_board(r, c):
    return 0 <= r < SIZE and 0 <= c < SIZE


def count_dir(board, r, c, dr, dc, player):
    """(r,c) 에서 (dr,dc) 한 방향으로 연속한 player 돌 개수."""
    n = 0
    nr, nc = r + dr, c + dc
    while in_board(nr, nc) and board[nr][nc] == player:
        n += 1
        nr += dr
        nc += dc
    return n


def check_win(board, r, c, player):
    """(r,c) 에 player 가 둔 직후 5목(이상) 완성 여부."""
    for dr, dc in DIRECTIONS:
        total = 1 + count_dir(board, r, c, dr, dc, player) + count_dir(board, r, c, -dr, -dc, player)
        if total >= 5:
            return True
    return False


def _line_string(board, r, c, dr, dc, player, reach=5):
    """(r,c) 를 중심으로 한 방향 축의 문자열을 만든다.

    X=player 돌, O=상대/벽(막힘), E=빈칸. 중심 인덱스도 함께 반환.
    """
    chars = []
    for i in range(-reach, reach + 1):
        nr, nc = r + dr * i, c + dc * i
        if not in_board(nr, nc):
            chars.append("O")
        elif board[nr][nc] == player:
            chars.append("X")
        elif board[nr][nc] == EMPTY:
            chars.append("E")
        else:
            chars.append("O")
    return "".join(chars), reach  # 중심 인덱스 = reach


def _has_open_four(line):
    """라인 문자열에 열린4(EXXXXE) 패턴이 있는가."""
    return "EXXXXE" in line


def _is_open_three(board, r, c, dr, dc):
    """(r,c) 에 흑이 놓인 상태에서, 이 축으로 '열린 3'(살아있는 3)인지.

    정의: 빈칸 한 곳에 흑을 더 두어 '열린 4(EXXXXE)'를 만들 수 있으면 열린 3.
    """
    # 이 축 위의 빈칸 후보들에 가상으로 흑을 두어 본다.
    for i in range(-4, 5):
        nr, nc = r + dr * i, c + dc * i
        if not in_board(nr, nc) or board[nr][nc] != EMPTY:
            continue
        board[nr][nc] = BLACK
        line, _ = _line_string(board, r, c, dr, dc, BLACK, reach=6)
        made = _has_open_four(line)
        board[nr][nc] = EMPTY
        if made:
            return True
    return False


def is_double_three(board, r, c):
    """(r,c) 에 흑을 두면 쌍삼(열린 3이 둘 이상)이 되는가.

    단, 그 수가 즉시 5목 승리이면 금수가 아니다(승리 우선).
    호출 전 board[r][c] 는 EMPTY 여야 한다.
    """
    if board[r][c] != EMPTY:
        return False
    board[r][c] = BLACK
    try:
        if check_win(board, r, c, BLACK):
            return False
        open_threes = 0
        for dr, dc in DIRECTIONS:
            if _is_open_three(board, r, c, dr, dc):
                open_threes += 1
        return open_threes >= 2
    finally:
        board[r][c] = EMPTY


def is_forbidden(board, r, c, player, renju_on):
    """렌주 규칙(쌍삼 금지)이 켜져 있고 흑의 차례일 때 금수인지."""
    if not renju_on or player != BLACK:
        return False
    return is_double_three(board, r, c)
