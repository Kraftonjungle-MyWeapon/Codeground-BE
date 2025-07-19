from scipy.optimize import linear_sum_assignment
import numpy as np
from src.app.domain.match.schemas.match_schemas import MatchingUserInfo
from src.app.domain.match.utils.tunning_gap import personal_gap
from datetime import datetime, timezone

# 매칭 cost 계산용 상수 (서비스 상황 맞게 조정)
MMR_RANGE = 500.0
RD_MAX = 350.0
ALPHA = 1.0  # mmr 차이 중요도
BETA = 0.5  # 신뢰구간 중요도


def match_cost(a, b):
    mmr_term = ((a.mmr - b.mmr) / MMR_RANGE) ** 2
    rd_term = ((a.rd / RD_MAX) ** 2 + (b.rd / RD_MAX) ** 2) / 2
    return ALPHA * mmr_term + BETA * rd_term


def pop_median_user(users):
    users_sorted = sorted(users, key=lambda x: x.mmr)
    median_idx = len(users_sorted) // 2
    waiting_user = users_sorted[median_idx]
    rest_users = users_sorted[:median_idx] + users_sorted[median_idx + 1 :]
    return waiting_user, rest_users


def hungarian_matching(users):
    len(users)
    mmr = np.array([u.mmr for u in users], dtype=float)
    rd = np.array([u.rd for u in users], dtype=float)
    mmr_term = ((mmr[:, None] - mmr[None, :]) / MMR_RANGE) ** 2
    rd_term = ((rd[:, None] / RD_MAX) ** 2 + (rd[None, :] / RD_MAX) ** 2) / 2
    cost = ALPHA * mmr_term + BETA * rd_term
    np.fill_diagonal(cost, np.inf)

    row, col = linear_sum_assignment(cost)

    paired, pairs = set(), []
    for i, j in zip(row, col):
        if i in paired or j in paired:
            continue
        pairs.append((users[i], users[j]))
        paired.update([i, j])

    match_pairs, waitings = filtering_gap(pairs)

    unpaired = [u for idx, u in enumerate(users) if idx not in paired]
    waitings.extend(unpaired)

    return match_pairs, waitings


def greedy_matching(users):
    waiting_user = None
    users = sorted(users, key=lambda x: x.mmr)
    if len(users) % 2 == 1:
        waiting_user, users = pop_median_user(users)
    matched_pairs = []
    for i in range(0, len(users), 2):
        matched_pairs.append((users[i], users[i + 1]))

    matched_pairs, waitings = filtering_gap(matched_pairs)

    if waiting_user:
        waitings.append(waiting_user)
    return matched_pairs, waitings


def hard_greedy_matching(users):
    waiting_user = None
    users = sorted(users, key=lambda x: x.mmr)
    if len(users) % 2 == 1:
        waiting_user, users = pop_median_user(users)
    matched_pairs = []
    for i in range(0, len(users), 2):
        matched_pairs.append((users[i], users[i + 1]))

    return matched_pairs, waiting_user


# 하이브리드 매칭 진입 함수
def hybrid_match(users, threshold=50):
    if len(users) <= threshold:
        pairs, waiting = hungarian_matching(users)
        return (pairs, waiting), "hungarian"  # ← 중첩 튜플
    else:
        pairs, waiting = greedy_matching(users)
        return (pairs, waiting), "greedy"


def filtering_gap(pairs):
    """허용 갭을 넘는 페어는 reject, accept/waiting 분리"""
    matched, waitings = [], []
    now = datetime.now(timezone.utc)

    gap_cache = {}

    def gap(user: MatchingUserInfo) -> float:
        uid = user.id
        if uid not in gap_cache:
            gap_cache[uid] = personal_gap(user, now=now)
        return gap_cache[uid]

    for a, b in pairs:
        diff = abs(a.mmr - b.mmr)
        if diff <= gap(a) and diff <= gap(b):
            matched.append((a, b))
        else:
            waitings.append(a)
            waitings.append(b)
    return matched, waitings


def hard_match(hard_users):
    pairs, next_waiter = hard_greedy_matching(hard_users)
    return pairs, next_waiter


def force_match(hard_waiter: MatchingUserInfo, wait_users):
    assert wait_users, "wait_users must be non-empty"

    most_closest = wait_users[0]
    closet_value = abs(hard_waiter.mmr - most_closest.mmr)
    for user in wait_users:
        gap_value = abs(hard_waiter.mmr - user.mmr)
        if gap_value < closet_value:
            closet_value = gap_value
            most_closest = user

    return most_closest
