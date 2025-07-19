import math
from enum import Enum
from typing import List, Tuple

# Glicko2 기반 상수/파라미터
SCALE = 173.7178
SIGMA_DEF = 0.1
TAU = 0.5
T_REF_H = 24
RD_MAX = 400
N_TRIGGER = 12
DEFAULT_RATING = 1500


class MatchScore(Enum):
    WIN = 1.0
    DRAW = 0.5
    LOSS = 0.0


Game = Tuple[float, float, MatchScore]


# --- Glicko2 핵심 함수 ---
def make_mue(rating: int) -> float:
    return (rating - DEFAULT_RATING) / SCALE


def make_pie(rd: float) -> float:
    return float(rd / SCALE)


def make_g(pie: float) -> float:
    return float(1 / math.sqrt(1 + (3 * pie**2 / math.pi**2)))


def is_can_win(white_mue: float, black_mue: float, white_pie: float) -> float:
    return float(1 / (1 + math.exp(-1 * make_g(white_pie) * (black_mue - white_mue))))


def update_sigma(pie: float, sigma: float, delta: float, v: float) -> float:
    a = math.log(sigma**2)
    square_pie = pie**2
    square_delta = delta**2

    def f(x):
        e = math.exp(x)
        numerator = e * (square_delta - square_pie - v - e)
        denominator = 2 * ((square_pie + v + e) ** 2)
        return float((numerator / denominator) - ((x - a) / (TAU**2)))

    eps = 1e-6
    a_result = a
    if square_delta > square_pie + v:
        b_result = math.log(square_delta - square_pie - v)
    else:
        k = 1
        while f(a - k * TAU) < 0:
            k += 1
        b_result = a - (k * TAU)

    fa_result, fb_result = f(a_result), f(b_result)
    while abs(b_result - a_result) > eps:
        c_result = a_result + (a_result - b_result) * fa_result / (fb_result - fa_result)
        fc_result = f(c_result)
        if fc_result * fb_result <= 0:
            a_result, fa_result = b_result, fb_result
        else:
            fa_result = fa_result / 2.0
        b_result, fb_result = c_result, fc_result
    return math.exp(a_result / 2.0)


def inflate_rd(rd: float, sigma: float, last_update, now=None) -> float:
    from datetime import datetime, timezone

    now = now or datetime.now(timezone.utc)
    hours = (now - last_update).total_seconds() / 3600.0
    if hours <= 0:
        return rd
    pie = make_pie(rd)
    pie = math.sqrt(pie**2 + sigma**2 * (hours / T_REF_H))
    return min(pie * SCALE, RD_MAX)


def full_update(mmr: float, rd: float, sigma: float, games: List[Game]) -> Tuple[float, float, float]:
    if not games:
        return mmr, rd, sigma
    mue = make_mue(int(mmr))
    pie = make_pie(rd)
    sum_a, sum_b = 0.0, 0.0
    for enemy_mmr, enemy_rd, is_win in games:
        mue_j = make_mue(int(enemy_mmr))
        pie_j = make_pie(enemy_rd)
        e = is_can_win(mue_j, mue, pie_j)
        g = make_g(pie_j)
        sum_a += g**2 * e * (1.0 - e)
        sum_b += g * (is_win.value - e)
    v = 1.0 / sum_a
    delta = v * sum_b
    new_sigma = update_sigma(pie, sigma, delta, v)
    pie_star = math.sqrt(pie**2 + new_sigma**2)
    new_pie = 1.0 / math.sqrt(1.0 / (pie_star**2) + 1.0 / v)
    new_mue = mue + new_pie**2 * sum_b
    new_rating = SCALE * new_mue + DEFAULT_RATING
    new_rd = min(SCALE * new_pie, RD_MAX)
    return new_rating, new_rd, new_sigma


# --- 언더독/강제풀 등 보상 정책 함수 ---
def calc_mmr_delta(player_mmr, opponent_mmr, result, is_forced=False):
    gap = opponent_mmr - player_mmr
    if not is_forced:
        base_delta = 30
        if result == "win":
            return base_delta
        elif result == "draw":
            return 0
        else:
            return -base_delta
    else:
        if result == "win":
            if player_mmr < opponent_mmr:
                return 200 + (abs(gap) // 5)
            else:
                return 1
        elif result == "draw":
            return 0
        else:
            if player_mmr > opponent_mmr:
                return -200 - (abs(gap) // 5)
            else:
                return -1
