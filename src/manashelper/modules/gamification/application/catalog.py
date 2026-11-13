from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Achievement:
    key: str
    emoji: str
    target: int | float


ACHIEVEMENTS = (
    Achievement("night_owl", "🌚", 3),
    Achievement("foodie", "😋", 50),
    Achievement("cafeteria_boss", "😎", 100),
    Achievement("formula_one", "🏎", 1),
    Achievement("champion", "🏆", 1),
    Achievement("comeback", "📈", 0.2),
    Achievement("fall", "📉", 0.2),
    Achievement("seller", "💩", 1),
    Achievement("eldin_balasy", "🤓", 3),
    Achievement("thin_ice", "🥶", 5),
    Achievement("phoenix", "👍", 1),
    Achievement("stability", "🧘", 3),
    Achievement("iron_attendance", "🔒", 1),
    Achievement("critic", "🧐", 100),
    Achievement("einstein", "⚛️", 1),
)

ACHIEVEMENT_KEYS = tuple(achievement.key for achievement in ACHIEVEMENTS)
