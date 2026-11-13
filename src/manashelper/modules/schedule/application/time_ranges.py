LUNCH_START_MINUTES = 12 * 60 + 25
LUNCH_END_MINUTES = 14 * 60 + 25

# Regular breaks between periods run ~10 minutes; anything longer (a free period, lunch) starts a new block.
MAX_GAP_MINUTES_TO_GROUP = 20


def parse_time_range_start_minutes(time_range: str) -> int:
    """Minutes since midnight for a "H:MM-H:MM" range's start — sorts "10:45" correctly after "9:50"."""
    hours, minutes = time_range.split("-", 1)[0].split(":")
    return int(hours) * 60 + int(minutes)


def parse_time_range_end_minutes(time_range: str) -> int:
    hours, minutes = time_range.split("-", 1)[1].split(":")
    return int(hours) * 60 + int(minutes)


def format_minutes(minutes: int) -> str:
    return f"{minutes // 60}:{minutes % 60:02d}"
