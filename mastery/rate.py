"""Smoothed correct rate per difficulty level, and the level rules built on it.

`history` = one node's graded answers, oldest first: [(question difficulty, score 0..1), ...].
"""
from statistics import mean

from config import settings as cfg

TOP_LEVEL = cfg.LEVELS[-1]


def recent(history, level):
    """Scores of the last RATE_WINDOW answers at one level."""
    return [score for difficulty, score in history if difficulty == level][-cfg.RATE_WINDOW:]


def rate(scores):
    """(correct + 1) / (answers + 2): 0.5 with no answers, firms up as answers come in."""
    return (sum(scores) + 1) / (len(scores) + 2)


def passed_level(history, level):
    """Enough answers at this level with a high enough rate."""
    scores = recent(history, level)
    return len(scores) >= cfg.LEVEL_UP_MIN_ANSWERS and rate(scores) >= cfg.LEVEL_UP_RATE


def next_level(history, level):
    """Levels only go up in practice: up one level for each passed level."""
    while level < TOP_LEVEL and passed_level(history, level):
        level += 1
    return level


def is_stuck(history, level):
    scores = recent(history, level)
    return len(scores) >= cfg.STUCK_MIN_ANSWERS and rate(scores) < cfg.STUCK_BELOW


def overall(history):
    """One 0..1 number per node for the profile: the average of the level rates."""
    return mean(rate(recent(history, level)) for level in cfg.LEVELS)


def level_mix(level, count):
    """{difficulty: question count} for one node: the current level plus a share of the one below."""
    if level == cfg.LEVELS[0]:
        return {level: count}
    previous = int(count * cfg.PREVIOUS_LEVEL_SHARE + 0.5)
    return {d: n for d, n in {level - 1: previous, level: count - previous}.items() if n}
