"""군대(스택) 모델.

지도 위의 '큰 Unit'은 한 진영의 병력 묶음(스택)이다. 장군/근위대 정보를
포함하며, 누가 어디에 얼마나 있는지 보여준다(CLAUDE.md 규칙).
"""

import itertools

_id_counter = itertools.count(1)


class Army:
    def __init__(self, faction, node_id, troops, general=None, domain="land"):
        self.id = next(_id_counter)
        self.faction = faction          # 진영 id
        self.node_id = node_id          # 현재 위치 노드 id
        self.troops = troops            # 병력 수 (함대는 총 승조원/전력)
        self.general = general          # 지휘관 이름 또는 None
        self.domain = domain            # 'land'(군대) 또는 'sea'(함대)
        self.moves_left = 0             # 이번 턴 남은 이동력

    @property
    def is_fleet(self):
        return self.domain == "sea"

    @property
    def has_guard(self):
        """장군이 있으면 근위대를 동반한 것으로 본다."""
        return self.general is not None

    def combat_power(self):
        """전투력 = 병력 * (장군 보정). 장군이 있으면 +15% 보너스."""
        bonus = 1.15 if self.has_guard else 1.0
        return self.troops * bonus

    def label(self):
        """지도/패널 표시용 짧은 라벨."""
        k = f"{self.troops // 1000}k"
        if self.is_fleet:
            return f"함대 ({k})"
        if self.general:
            return f"{self.general} ({k})"
        return f"부대 ({k})"

    def __repr__(self):
        return f"<Army {self.id} {self.faction} @{self.node_id} {self.troops}>"
