# 오목 (Omok)

Pygame으로 만든 오목 게임. 1P(vs CPU) / 2P 플레이, 쌍삼(렌주) 금수 ON/OFF,
SQLite 리더보드를 지원합니다.

## 요구 사항
- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (가상환경 관리)

## 설치 & 실행

```bash
# 가상환경 생성 + 의존성 설치
uv venv --python 3.13
uv pip install pygame

# 실행
uv run python omok.py
```

> uv 없이 실행하려면: `py -m pip install pygame` 후 `py omok.py`

## 게임 방법
- **메뉴**: 모드(1P/2P), 쌍삼 금지(ON/OFF), 플레이어 이름을 설정하고 `게임 시작`
- **착수**: 바둑판 교차점을 클릭
- 가로·세로·대각선 중 **5목**을 먼저 만들면 승리
- 쌍삼 금지 ON이면 흑의 금수 자리가 빨간 ✕ 로 표시되고 착수가 막힙니다
- 게임이 끝나면 결과가 자동 기록되고 `재시작 / 리더보드 / 메뉴로` 버튼이 나타납니다

## 파일 구성
| 파일 | 설명 |
|------|------|
| `omok.py` | 메인 게임 (Pygame UI, 상태 머신) |
| `rules.py` | 5목 승리 판정 + 쌍삼 금수 검사 |
| `ai.py` | 1P 모드 CPU (공격·방어 휴리스틱) |
| `db.py` | SQLite(`omok.db`) 기록 / 리더보드 집계 |

## 리더보드
게임 결과는 `omok.db`의 `games` 테이블에 INSERT되며, 승수 기준으로 랭킹을 집계합니다(CPU 제외).
