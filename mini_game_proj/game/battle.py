"""전투 판정 로직.

CLAUDE.md상 서로 부딪히면 전투맵으로 넘어가야 하지만, 전략 지도 MVP에서는
간단한 확률 기반 판정으로 대체한다(전투맵은 다음 단계). 전투력 비율에 약간의
난수를 더해 승패와 양측 손실을 계산한다.
"""

import random


def resolve(attacker, defender, on_city=False):
    """공격군 vs 방어군 전투를 판정한다.

    반환: dict(
        winner=Army, loser=Army,
        attacker_losses=int, defender_losses=int,
        log=str  # 사람이 읽을 수 있는 요약
    )
    패자는 전멸(troops=0) 처리하며, 호출 측에서 제거한다.
    """
    a_power = attacker.combat_power()
    d_power = defender.combat_power()

    # 도심 방어 보너스: 방어 측이 도심에 있으면 +25%
    if on_city:
        d_power *= 1.25

    # 난수 운(0.8~1.2)을 양측에 적용
    a_roll = a_power * random.uniform(0.8, 1.2)
    d_roll = d_power * random.uniform(0.8, 1.2)

    if a_roll >= d_roll:
        winner, loser = attacker, defender
    else:
        winner, loser = defender, attacker

    # 손실: 승자는 상대 전투력 비례 손실, 패자는 전멸
    ratio = loser.combat_power() / max(winner.combat_power(), 1.0)
    winner_losses = int(winner.troops * min(0.6, 0.25 + 0.35 * ratio))
    loser_losses = loser.troops

    winner.troops = max(1000, winner.troops - winner_losses)
    loser.troops = 0

    a_loss = winner_losses if winner is attacker else loser_losses
    d_loss = winner_losses if winner is defender else loser_losses

    from .map_data import FACTIONS
    wname = FACTIONS[winner.faction][0]
    log = (f"{wname} 승리! "
           f"공격 손실 {a_loss:,} / 방어 손실 {d_loss:,}")

    return {
        "winner": winner,
        "loser": loser,
        "attacker_losses": a_loss,
        "defender_losses": d_loss,
        "log": log,
    }
