"""The worksheet blueprint: one slot (node, difficulty) per question, decided from the student's profile."""
from dataclasses import dataclass

from mastery.rate import level_mix


@dataclass(frozen=True)
class Slot:
    node_id: int
    difficulty: int


def blueprint(navigator, profile, plan):
    """Slots for the whole sheet, prerequisites first.

    Each node's slots are split over difficulties by its level in the profile (`level_mix`),
    unless the plan fixes one difficulty (placement).
    """
    slots = []
    for node in navigator.order(plan.skill_counts):
        count = plan.skill_counts[node]
        mix = {plan.difficulty: count} if plan.difficulty else level_mix(profile.level(node), count)
        for difficulty, n in mix.items():
            slots += [Slot(node, difficulty)] * n
    return slots
