from datetime import timedelta

from config import settings as cfg


def next_review(review_level, now):
    """When to check a mastered skill again; intervals grow with each passed review."""
    intervals = cfg.REVIEW_INTERVALS_DAYS
    return now + timedelta(days=intervals[min(review_level, len(intervals) - 1)])
