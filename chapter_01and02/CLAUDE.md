# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# 오목 게임 구현

## 현재 상태
- 아직 소스 코드가 없는 초기 단계다. 이 문서의 명세를 기준으로 구현을 시작한다.
- 빌드/린트/테스트 도구는 아직 설정되어 있지 않다. 새로 추가할 때 이 문서에 명령을 함께 기록한다.

## 개발 명령
- 의존성 설치: `pip install pygame`
- 실행: 메인 엔트리포인트(예: `python main.py`)로 게임을 띄운다.
- 리더보드 DB 확인: `sqlite3 omok.db "SELECT * FROM games;"`

## 아키텍처 메모
- 게임 루프(Pygame)는 메뉴 화면과 인게임 화면 상태를 전환한다. 메뉴에서 1P/2P 모드와 쌍삼 ON/OFF를 고른 뒤 게임을 시작한다.
- 보드 상태(좌표별 빈칸/흑/백)와 승리 판정(가로·세로·양 대각선 5목)은 렌더링과 분리해 둔다. 쌍삼 금지 규칙은 착수 유효성 검사 단계에서 적용한다.
- 게임 종료 시 결과를 `omok.db`의 `games` 테이블에 INSERT 한다. 이 기록 로직은 `.claude/skills/record-leaderboard` 스킬의 규칙(시작 시 스키마 생성, 종료 시 INSERT)을 따른다.
- 1P 모드에서는 한쪽 플레이어 이름이 `'CPU'`이며, 리더보드 집계에서 `CPU`는 제외한다.

## 사용 기술 스택
- Python 3.13
- Pygame

## 플레이
- 1P 플레이, 2P 플레이 나누어서 구현한다.
- 바둑판 점에 흑돌과 백돌을 놓는다.
- 가로, 세로, 대각선 어느 한 부분이든 5줄을 만들면 이긴다.

## 주의사항
- 쌍삼은 허용여부를 메뉴창에서 ON/OFF 체크할 수 있도록 한다.
- 게임이 끝나면 무조건 기록하며, 재시작 버튼을 추가한다.

## 게임 리더보드 스키마
- SQLite 파일(`omok.db`) 하나에 게임 결과를 가볍게 기록한다.
- 게임이 끝날 때마다 `games` 테이블에 1행을 INSERT 한다.
- 테이블 정의는 다음과 같다.

```sql
CREATE TABLE IF NOT EXISTS games (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,  -- 게임 고유 번호
    played_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),  -- 게임 종료 시각
    mode        TEXT    NOT NULL,    -- '1P' 또는 '2P'
    black_name  TEXT    NOT NULL,    -- 흑돌 플레이어 이름 (1P일 때 한쪽은 'CPU')
    white_name  TEXT    NOT NULL,    -- 백돌 플레이어 이름
    winner      TEXT    NOT NULL,    -- 'BLACK' | 'WHITE' | 'DRAW'
    renju_rule  INTEGER NOT NULL,    -- 쌍삼 금지 여부 (1=ON/금지, 0=OFF/허용)
    move_count  INTEGER NOT NULL,    -- 총 착수 수
    duration_s  INTEGER NOT NULL     -- 게임 소요 시간(초)
);
```

- 리더보드는 위 테이블을 집계해 승수 기준으로 보여준다.

```sql
-- 플레이어별 승수 랭킹
SELECT name, COUNT(*) AS wins
FROM (
    SELECT black_name AS name FROM games WHERE winner = 'BLACK'
    UNION ALL
    SELECT white_name AS name FROM games WHERE winner = 'WHITE'
)
WHERE name != 'CPU'
GROUP BY name
ORDER BY wins DESC;
```

