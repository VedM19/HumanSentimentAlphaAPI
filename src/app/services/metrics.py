from app.models.repository import WeeklyGrowthPoint


def calculate_momentum_score(
    points: list[WeeklyGrowthPoint],
    span: int = 2,
) -> float:
    """Return an exponentially weighted momentum score from weekly star deltas."""
    if span <= 0:
        raise ValueError("span must be a positive integer")

    if len(points) < span + 1:
        return 0.0

    alpha = 2 / (span + 1)
    current_ewma = float(points[0].star_delta)

    for week_gain in points[1:]:
        current_ewma = (1 - alpha) * current_ewma + alpha * week_gain.star_delta

    return current_ewma
