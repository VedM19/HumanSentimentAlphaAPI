from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.models.repository import RepositoryRef


class WeeklyStarComparisonRequest(BaseModel):
    weeks: int = Field(default=4, ge=1, le=52, description="Number of weeks to compare.")
    left_repository: RepositoryRef = Field(
        default_factory=lambda: RepositoryRef(owner="NVIDIA", name="TensorRT"),
        description="First repository to compare.",
    )
    right_repository: RepositoryRef = Field(
        default_factory=lambda: RepositoryRef(owner="ROCm", name="ROCm"),
        description="Second repository to compare.",
    )

    @model_validator(mode="after")
    def validate_distinct_repositories(self) -> "WeeklyStarComparisonRequest":
        if self.left_repository.full_name == self.right_repository.full_name:
            raise ValueError("left_repository and right_repository must be different")
        return self


class WeeklyStarDelta(BaseModel):
    week_start: date
    stars_gained: int


class RepoGrowthSummary(BaseModel):
    repository: str
    total_growth: int
    momentum_score: float
    current_stargazers: int
    weekly_deltas: list[WeeklyStarDelta]


class WeeklyStarComparisonResponse(BaseModel):
    winner: str
    summary: str
    repositories: list[RepoGrowthSummary]
