"""오목 게임 (Pygame)

- 1P(vs CPU) / 2P 모드
- 15x15 바둑판, 교차점에 흑/백 착수
- 가로/세로/대각 5목 승리
- 쌍삼(렌주) 금지 ON/OFF
- 게임 종료 시 SQLite(omok.db) 기록 + 재시작
"""

import sys
import time

import pygame

import db
import ai
from rules import (
    BLACK, WHITE, EMPTY, SIZE, DIRECTIONS,
    in_board, check_win, is_forbidden,
)

# ---------------------------------------------------------------- 화면 설정
MARGIN = 40
CELL = 40
BOARD_PX = MARGIN * 2 + CELL * (SIZE - 1)   # 바둑판 영역(정사각형)
PANEL_W = 260                               # 우측 정보 패널
WIDTH = BOARD_PX + PANEL_W
HEIGHT = BOARD_PX

# 색상
COL_BG = (240, 217, 181)      # 나무색 배경
COL_LINE = (60, 40, 20)
COL_BLACK = (20, 20, 20)
COL_WHITE = (245, 245, 245)
COL_PANEL = (250, 246, 238)
COL_TEXT = (40, 30, 20)
COL_BTN = (205, 170, 125)
COL_BTN_HOVER = (220, 190, 150)
COL_BTN_ON = (120, 170, 120)
COL_BTN_OFF = (200, 120, 120)
COL_STAR = (60, 40, 20)
COL_FORBID = (220, 60, 60)

# 게임 상태
ST_MENU = "menu"
ST_PLAY = "play"
ST_OVER = "over"
ST_BOARD = "leaderboard"


def load_font(size):
    """한글 지원 폰트(맑은 고딕)를 우선 시도, 없으면 기본 폰트."""
    try:
        return pygame.font.SysFont("malgungothic", size)
    except Exception:
        return pygame.font.Font(None, size)


class Button:
    def __init__(self, rect, text, color=COL_BTN):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.color = color

    def draw(self, surf, font, hover=False):
        c = COL_BTN_HOVER if hover else self.color
        pygame.draw.rect(surf, c, self.rect, border_radius=8)
        pygame.draw.rect(surf, COL_LINE, self.rect, 2, border_radius=8)
        label = font.render(self.text, True, COL_TEXT)
        surf.blit(label, label.get_rect(center=self.rect.center))

    def hit(self, pos):
        return self.rect.collidepoint(pos)


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("오목 (Omok)")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()

        self.font_s = load_font(20)
        self.font_m = load_font(26)
        self.font_l = load_font(40)
        self.font_xl = load_font(64)

        db.init_db()

        # 메뉴 설정값
        self.mode = "1P"          # '1P' | '2P'
        self.renju_on = True      # 쌍삼 금지 여부
        self.names = {"black": "", "white": ""}
        self.active_input = None  # 'black' | 'white' | None

        self.state = ST_MENU
        self.reset_game()

    # ----------------------------------------------------- 게임 초기화
    def reset_game(self):
        self.board = [[EMPTY] * SIZE for _ in range(SIZE)]
        self.turn = BLACK
        self.move_count = 0
        self.last_move = None
        self.winner = None        # 'BLACK' | 'WHITE' | 'DRAW' | None
        self.start_time = time.time()
        self.message = ""
        self.recorded = False

    def player_name(self, color):
        """color('black'/'white') 의 표시 이름."""
        if self.mode == "1P" and color == "white":
            return "CPU"
        name = self.names[color].strip()
        return name if name else ("흑" if color == "black" else "백")

    # ----------------------------------------------------- 좌표 변환
    def cell_to_px(self, r, c):
        return MARGIN + c * CELL, MARGIN + r * CELL

    def px_to_cell(self, x, y):
        c = round((x - MARGIN) / CELL)
        r = round((y - MARGIN) / CELL)
        if in_board(r, c):
            return r, c
        return None

    # ===================================================== 메인 루프
    def run(self):
        while True:
            hover = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if self.state == ST_MENU:
                    self.handle_menu_event(event)
                elif self.state == ST_PLAY:
                    self.handle_play_event(event)
                elif self.state == ST_OVER:
                    self.handle_over_event(event)
                elif self.state == ST_BOARD:
                    self.handle_board_event(event)

            if self.state == ST_MENU:
                self.draw_menu(hover)
            elif self.state in (ST_PLAY, ST_OVER):
                self.draw_play(hover)
                if self.state == ST_PLAY and self.mode == "1P" and self.turn == WHITE and not self.winner:
                    pygame.display.flip()
                    self.cpu_turn()
            elif self.state == ST_BOARD:
                self.draw_leaderboard(hover)

            pygame.display.flip()
            self.clock.tick(60)

    # ===================================================== 메뉴 화면
    def menu_buttons(self):
        cx = WIDTH // 2
        return {
            "1P": Button((cx - 160, 170, 150, 50), "1P (vs CPU)",
                         COL_BTN_ON if self.mode == "1P" else COL_BTN),
            "2P": Button((cx + 10, 170, 150, 50), "2P",
                         COL_BTN_ON if self.mode == "2P" else COL_BTN),
            "renju": Button((cx + 10, 250, 150, 50),
                            "ON (금지)" if self.renju_on else "OFF (허용)",
                            COL_BTN_ON if self.renju_on else COL_BTN_OFF),
            "input_black": Button((cx - 160, 340, 320, 44), "", COL_PANEL),
            "input_white": Button((cx - 160, 410, 320, 44), "", COL_PANEL),
            "start": Button((cx - 160, 480, 150, 56), "게임 시작", COL_BTN_ON),
            "board": Button((cx + 10, 480, 150, 56), "리더보드"),
        }

    def handle_menu_event(self, event):
        btns = self.menu_buttons()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            self.active_input = None
            if btns["1P"].hit(pos):
                self.mode = "1P"
            elif btns["2P"].hit(pos):
                self.mode = "2P"
            elif btns["renju"].hit(pos):
                self.renju_on = not self.renju_on
            elif btns["input_black"].hit(pos):
                self.active_input = "black"
            elif btns["input_white"].hit(pos) and self.mode == "2P":
                self.active_input = "white"
            elif btns["start"].hit(pos):
                self.reset_game()
                self.state = ST_PLAY
            elif btns["board"].hit(pos):
                self.state = ST_BOARD
        elif event.type == pygame.KEYDOWN and self.active_input:
            if event.key == pygame.K_BACKSPACE:
                self.names[self.active_input] = self.names[self.active_input][:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_TAB):
                self.active_input = None
        elif event.type == pygame.TEXTINPUT and self.active_input:
            if len(self.names[self.active_input]) < 12:
                self.names[self.active_input] += event.text

    def draw_menu(self, hover):
        self.screen.fill(COL_BG)
        title = self.font_xl.render("오목 Omok", True, COL_TEXT)
        self.screen.blit(title, title.get_rect(center=(WIDTH // 2, 90)))

        labels = [
            (110, 195, "모드"),
            (110, 275, "쌍삼 금지"),
            (110, 362, "흑 이름"),
            (110, 432, "백 이름" + (" (CPU)" if self.mode == "1P" else "")),
        ]
        for x, y, text in labels:
            lab = self.font_m.render(text, True, COL_TEXT)
            self.screen.blit(lab, lab.get_rect(midright=(x + 90, y)))

        btns = self.menu_buttons()
        for key, b in btns.items():
            if key == "input_white" and self.mode == "1P":
                b.color = (225, 225, 225)
            b.draw(self.screen, self.font_m, b.hit(hover) and not key.startswith("input"))

        # 입력 박스 텍스트
        self._draw_input_text(btns["input_black"], self.player_name("black") if self.names["black"] else "흑돌 이름 입력", "black")
        if self.mode == "2P":
            self._draw_input_text(btns["input_white"], self.names["white"] or "백돌 이름 입력", "white")
        else:
            txt = self.font_s.render("CPU 자동", True, (120, 120, 120))
            self.screen.blit(txt, txt.get_rect(midleft=(btns["input_white"].rect.x + 12, btns["input_white"].rect.centery)))

    def _draw_input_text(self, box, placeholder, which):
        active = self.active_input == which
        pygame.draw.rect(self.screen, (255, 255, 255), box.rect, border_radius=6)
        border = COL_BTN_ON if active else COL_LINE
        pygame.draw.rect(self.screen, border, box.rect, 2, border_radius=6)
        val = self.names[which]
        if val:
            txt = self.font_m.render(val + ("|" if active else ""), True, COL_TEXT)
        else:
            txt = self.font_s.render(placeholder + ("|" if active else ""), True, (150, 150, 150))
        self.screen.blit(txt, txt.get_rect(midleft=(box.rect.x + 12, box.rect.centery)))

    # ===================================================== 플레이 화면
    def handle_play_event(self, event):
        if self.winner:
            return
        # 2P 이거나, 1P 의 흑(사람) 차례일 때만 클릭 입력
        if self.mode == "1P" and self.turn == WHITE:
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            cell = self.px_to_cell(*event.pos)
            if cell:
                self.try_place(*cell)

    def try_place(self, r, c):
        if self.board[r][c] != EMPTY:
            return False
        if is_forbidden(self.board, r, c, self.turn, self.renju_on):
            self.message = "쌍삼 금수! 다른 곳에 두세요."
            return False
        self.message = ""
        self.board[r][c] = self.turn
        self.move_count += 1
        self.last_move = (r, c)

        if check_win(self.board, r, c, self.turn):
            self.winner = "BLACK" if self.turn == BLACK else "WHITE"
            self.finish_game()
        elif self.move_count >= SIZE * SIZE:
            self.winner = "DRAW"
            self.finish_game()
        else:
            self.turn = WHITE if self.turn == BLACK else BLACK
        return True

    def cpu_turn(self):
        pygame.time.delay(300)  # 생각하는 척
        r, c = ai.choose_move(self.board, WHITE, self.renju_on)
        self.try_place(r, c)

    def finish_game(self):
        self.state = ST_OVER
        if self.recorded:
            return
        duration = int(time.time() - self.start_time)
        db.record_game(
            mode=self.mode,
            black_name=self.player_name("black"),
            white_name=self.player_name("white"),
            winner=self.winner,
            renju_rule=self.renju_on,
            move_count=self.move_count,
            duration_s=duration,
        )
        self.recorded = True

    def handle_over_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for key, b in self.over_buttons().items():
                if b.hit(event.pos):
                    if key == "restart":
                        self.reset_game()
                        self.state = ST_PLAY
                    elif key == "menu":
                        self.state = ST_MENU
                    elif key == "board":
                        self.state = ST_BOARD

    def over_buttons(self):
        x = BOARD_PX + 20
        return {
            "restart": Button((x, HEIGHT - 200, PANEL_W - 40, 48), "재시작", COL_BTN_ON),
            "board": Button((x, HEIGHT - 142, PANEL_W - 40, 48), "리더보드"),
            "menu": Button((x, HEIGHT - 84, PANEL_W - 40, 48), "메뉴로"),
        }

    def draw_play(self, hover):
        self.screen.fill(COL_BG)
        self._draw_board_grid()
        self._draw_stones()
        self._draw_panel(hover)

    def _draw_board_grid(self):
        # 격자선
        for i in range(SIZE):
            x0, y0 = self.cell_to_px(i, 0)
            x1, y1 = self.cell_to_px(i, SIZE - 1)
            pygame.draw.line(self.screen, COL_LINE, (x0, y0), (x1, y1), 1)
            x0, y0 = self.cell_to_px(0, i)
            x1, y1 = self.cell_to_px(SIZE - 1, i)
            pygame.draw.line(self.screen, COL_LINE, (x0, y0), (x1, y1), 1)
        # 화점 (천원 + 4귀)
        stars = [3, 7, 11]
        for r in stars:
            for c in stars:
                x, y = self.cell_to_px(r, c)
                pygame.draw.circle(self.screen, COL_STAR, (x, y), 5)

    def _draw_stones(self):
        for r in range(SIZE):
            for c in range(SIZE):
                if self.board[r][c] == EMPTY:
                    continue
                x, y = self.cell_to_px(r, c)
                color = COL_BLACK if self.board[r][c] == BLACK else COL_WHITE
                pygame.draw.circle(self.screen, color, (x, y), CELL // 2 - 2)
                pygame.draw.circle(self.screen, COL_LINE, (x, y), CELL // 2 - 2, 1)
        # 마지막 착수 표시
        if self.last_move:
            x, y = self.cell_to_px(*self.last_move)
            pygame.draw.circle(self.screen, COL_FORBID, (x, y), 5)

        # 흑 차례에 쌍삼 금수 자리를 X 로 표시
        if self.renju_on and self.turn == BLACK and not self.winner:
            for r in range(SIZE):
                for c in range(SIZE):
                    if self.board[r][c] == EMPTY and is_forbidden(self.board, r, c, BLACK, True):
                        x, y = self.cell_to_px(r, c)
                        pygame.draw.line(self.screen, COL_FORBID, (x - 8, y - 8), (x + 8, y + 8), 2)
                        pygame.draw.line(self.screen, COL_FORBID, (x - 8, y + 8), (x + 8, y - 8), 2)

    def _draw_panel(self, hover):
        x = BOARD_PX
        pygame.draw.rect(self.screen, COL_PANEL, (x, 0, PANEL_W, HEIGHT))
        pygame.draw.line(self.screen, COL_LINE, (x, 0), (x, HEIGHT), 2)
        px = x + 20
        y = 24

        title = self.font_l.render("오목", True, COL_TEXT)
        self.screen.blit(title, (px, y))
        y += 60

        info = [
            f"모드: {self.mode}",
            f"쌍삼 금지: {'ON' if self.renju_on else 'OFF'}",
            f"착수: {self.move_count}",
        ]
        for line in info:
            self.screen.blit(self.font_s.render(line, True, COL_TEXT), (px, y))
            y += 28
        y += 8

        # 플레이어 표시
        for color, label in (("black", "흑"), ("white", "백")):
            dot = COL_BLACK if color == "black" else COL_WHITE
            pygame.draw.circle(self.screen, dot, (px + 10, y + 10), 10)
            pygame.draw.circle(self.screen, COL_LINE, (px + 10, y + 10), 10, 1)
            is_turn = (not self.winner) and (
                (color == "black" and self.turn == BLACK) or
                (color == "white" and self.turn == WHITE)
            )
            name = self.player_name(color)
            txt = self.font_m.render(name + ("  ◀" if is_turn else ""), True, COL_TEXT)
            self.screen.blit(txt, (px + 30, y))
            y += 34
        y += 10

        # 상태 메시지
        if self.state == ST_OVER:
            if self.winner == "DRAW":
                msg = "무승부!"
            else:
                wname = self.player_name("black" if self.winner == "BLACK" else "white")
                msg = f"{wname} 승리!"
            win_txt = self.font_l.render(msg, True, COL_FORBID)
            self.screen.blit(win_txt, (px, y))
            for key, b in self.over_buttons().items():
                b.draw(self.screen, self.font_m, b.hit(hover))
        else:
            if self.message:
                m = self.font_s.render(self.message, True, COL_FORBID)
                self.screen.blit(m, (px, y))
            hint = self.font_s.render("교차점을 클릭해 착수", True, (120, 110, 100))
            self.screen.blit(hint, (px, HEIGHT - 40))

    # ===================================================== 리더보드 화면
    def handle_board_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.back_button().hit(event.pos):
                self.state = ST_OVER if self.winner else ST_MENU

    def back_button(self):
        return Button((WIDTH // 2 - 90, HEIGHT - 70, 180, 48), "뒤로", COL_BTN)

    def draw_leaderboard(self, hover):
        self.screen.fill(COL_BG)
        title = self.font_l.render("리더보드 (승수 랭킹)", True, COL_TEXT)
        self.screen.blit(title, title.get_rect(center=(WIDTH // 2, 50)))

        # 컬럼 x좌표 (비례 폰트라 문자열 패딩 대신 좌표로 정렬한다)
        left_x = WIDTH // 2 - 250
        col_rank = left_x
        col_name = left_x + 90
        col_wins = left_x + 440      # 우측 정렬 기준선
        bottom_limit = HEIGHT - 90   # '뒤로' 버튼과 겹치지 않도록

        def blit_right(text, font, right_x, y, color=COL_TEXT):
            t = font.render(text, True, color)
            self.screen.blit(t, t.get_rect(topright=(right_x, y)))

        rows = db.get_leaderboard(8)
        y = 110
        if not rows:
            empty = self.font_m.render("아직 기록이 없습니다.", True, COL_TEXT)
            self.screen.blit(empty, empty.get_rect(center=(WIDTH // 2, y + 40)))
            y += 90
        else:
            self.screen.blit(self.font_s.render("순위", True, COL_TEXT), (col_rank, y))
            self.screen.blit(self.font_s.render("이름", True, COL_TEXT), (col_name, y))
            blit_right("승", self.font_s, col_wins, y)
            y += 30
            pygame.draw.line(self.screen, COL_LINE, (col_rank, y - 4), (col_wins, y - 4), 1)
            y += 6
            for i, (name, wins) in enumerate(rows, 1):
                medal = {1: "1위", 2: "2위", 3: "3위"}.get(i, f"{i}위")
                self.screen.blit(self.font_m.render(medal, True, COL_TEXT), (col_rank, y))
                self.screen.blit(self.font_m.render(str(name), True, COL_TEXT), (col_name, y))
                blit_right(f"{wins} 승", self.font_m, col_wins, y)
                y += 36

        # 최근 게임 (남는 세로 공간만큼만 표시)
        y += 24
        recent = db.get_recent_games(6)
        if recent and y < bottom_limit:
            self.screen.blit(self.font_m.render("최근 게임", True, COL_TEXT), (col_rank, y))
            y += 34
            for played_at, mode, bn, wn, winner, mc, dur in recent:
                if y > bottom_limit:
                    break
                wlabel = {"BLACK": bn, "WHITE": wn, "DRAW": "무승부"}.get(winner, winner)
                line = f"{played_at[5:16]}  [{mode}]  {bn} vs {wn}  -> {wlabel}"
                self.screen.blit(self.font_s.render(line, True, COL_TEXT), (col_rank, y))
                y += 26

        b = self.back_button()
        b.draw(self.screen, self.font_m, b.hit(hover))


if __name__ == "__main__":
    Game().run()
