"""효과음 합성 모듈.

외부 음원 없이 표준 라이브러리(math/array/random)로 짧은 효과음을 합성한다.
mixer 초기화에 실패하면(예: 더미 오디오) 모든 호출이 조용히 무시된다.

사용:
    audio.init()
    audio.play("cannon")
"""

import array
import math
import random

import pygame

RATE = 44100
_sounds = {}
_ok = False
_enabled = True


def _env_exp(i, n, tau):
    """지수 감쇠 엔벨로프."""
    return math.exp(-(i / RATE) / tau)


def _to_sound(mono, volume=0.35):
    """모노 float 리스트(-1..1)를 스테레오 16bit pygame Sound로 변환."""
    data = array.array("h")
    peak = max((abs(x) for x in mono), default=1.0) or 1.0
    scale = volume * 32767 / peak
    for x in mono:
        v = int(max(-32768, min(32767, x * scale)))
        data.append(v)   # L
        data.append(v)   # R
    return pygame.mixer.Sound(buffer=data.tobytes())


def _synth_cannon():
    dur = 0.5
    n = int(RATE * dur)
    out = []
    for i in range(n):
        t = i / RATE
        env = _env_exp(i, n, 0.16)
        low = math.sin(2 * math.pi * 65 * t) + 0.6 * math.sin(2 * math.pi * 110 * t)
        noise = random.uniform(-1, 1) * (0.8 if t < 0.05 else 0.4)
        out.append((low * 0.7 + noise) * env)
    return _to_sound(out, volume=0.5)


def _synth_musket():
    dur = 0.16
    n = int(RATE * dur)
    out = []
    prev = 0.0
    for i in range(n):
        env = _env_exp(i, n, 0.035)
        raw = random.uniform(-1, 1)
        hp = raw - prev   # 간이 하이패스(크랙 느낌)
        prev = raw
        out.append(hp * env)
    return _to_sound(out, volume=0.4)


def _synth_thump():
    dur = 0.14
    n = int(RATE * dur)
    out = []
    for i in range(n):
        t = i / RATE
        env = _env_exp(i, n, 0.05)
        out.append(math.sin(2 * math.pi * 95 * t) * env)
    return _to_sound(out, volume=0.35)


def _synth_blip(freq=660, dur=0.06):
    n = int(RATE * dur)
    out = []
    for i in range(n):
        t = i / RATE
        env = _env_exp(i, n, 0.04)
        out.append(math.sin(2 * math.pi * freq * t) * env)
    return _to_sound(out, volume=0.3)


def _synth_whoosh():
    dur = 0.32
    n = int(RATE * dur)
    out = []
    for i in range(n):
        frac = i / n
        env = math.sin(math.pi * frac)            # 서서히 커졌다 작아짐
        out.append(random.uniform(-1, 1) * env * 0.5)
    return _to_sound(out, volume=0.25)


def _synth_arpeggio(freqs, note=0.16):
    out = []
    for f in freqs:
        n = int(RATE * note)
        for i in range(n):
            t = i / RATE
            env = _env_exp(i, n, 0.12)
            out.append(0.5 * math.sin(2 * math.pi * f * t) * env)
    return _to_sound(out, volume=0.4)


def init():
    """mixer를 초기화하고 효과음을 합성한다. 실패해도 예외를 던지지 않는다."""
    global _ok
    try:
        pygame.mixer.init(RATE, -16, 2, 512)
    except Exception:
        _ok = False
        return False
    try:
        _sounds["cannon"] = _synth_cannon()
        _sounds["musket"] = _synth_musket()
        _sounds["move"] = _synth_thump()
        _sounds["select"] = _synth_blip(720, 0.05)
        _sounds["sail"] = _synth_whoosh()
        _sounds["victory"] = _synth_arpeggio([523, 659, 784, 1047])
        _sounds["defeat"] = _synth_arpeggio([392, 330, 262], note=0.22)
        _ok = True
    except Exception:
        _ok = False
    return _ok


def play(name):
    if _ok and _enabled and name in _sounds:
        try:
            _sounds[name].play()
        except Exception:
            pass


def set_enabled(flag):
    global _enabled
    _enabled = flag


def is_ready():
    return _ok
