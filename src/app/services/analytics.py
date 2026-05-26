from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.models.repository import RepositoryRef, WeeklyGrowthPoint
from app.services.github import GitHubClient


class RepoAnalyticsService(ABC):
    @abstractmethod
    async def get_weekly_growth(
        self,
        repository: RepositoryRef,
        weeks: int,
    ) -> tuple[RepositoryRef, list[WeeklyGrowthPoint]]:
        raise NotImplementedError

    async def get_weekly_growth_batch(
        self,
        repositories: list[RepositoryRef],
        weeks: int,
    ) -> list[tuple[RepositoryRef, list[WeeklyGrowthPoint]]]:
        results: list[tuple[RepositoryRef, list[WeeklyGrowthPoint]]] = []
        for repository in repositories:
            results.append(await self.get_weekly_growth(repository=repository, weeks=weeks))
        return results


class InMemoryRepoAnalyticsService(RepoAnalyticsService):
    """
    Temporary provider that keeps the API runnable before GitHub wiring exists.
    """

    _fixture_data = {
        "NVIDIA/TensorRT": [43, 55, 61, 58, 72, 76],
        "ROCm/ROCm": [39, 44, 46, 49, 50, 54],
    }

    async def get_weekly_growth(
        self,
        repository: RepositoryRef,
        weeks: int,
    ) -> tuple[RepositoryRef, list[WeeklyGrowthPoint]]:
        values = self._fixture_data.get(repository.full_name, [0] * max(weeks, 1))
        selected_values = values[-weeks:]
        anchor = self._start_of_week(datetime.now(UTC).date())
        points = [
            WeeklyGrowthPoint(
                week_start=anchor - timedelta(weeks=len(selected_values) - index - 1),
                star_delta=value,
            )
            for index, value in enumerate(selected_values)
        ]
        return repository, points

    @staticmethod
    def _start_of_week(value: date) -> date:
        return value - timedelta(days=value.weekday())


@dataclass(slots=True)
class GitHubRepoAnalyticsService(RepoAnalyticsService):
    """Build weekly star-growth series from the GitHub stargazers API."""

    github_client: GitHubClient
    page_size: int = 100

    async def get_weekly_growth(
        self,
        repository: RepositoryRef,
        weeks: int,
    ) -> tuple[RepositoryRef, list[WeeklyGrowthPoint]]:
        if weeks <= 0:
            raise ValueError("weeks must be positive")

        current_week_start = self._start_of_week(datetime.now(UTC).date())
        oldest_week_start = current_week_start - timedelta(weeks=weeks - 1)
        bucket_counts = {oldest_week_start + timedelta(weeks=index): 0 for index in range(weeks)}

        page = 1
        while True:
            stargazers = await self.github_client.list_stargazers(
                repository.owner,
                repository.name,
                page=page,
                per_page=self.page_size,
            )

            if not stargazers:
                break

            for stargazer in stargazers:
                starred_at = self._parse_starred_at(stargazer)
                starred_week = self._start_of_week(starred_at)

                if starred_week in bucket_counts:
                    bucket_counts[starred_week] += 1

            if len(stargazers) < self.page_size:
                break

            page += 1

        points = [
            WeeklyGrowthPoint(week_start=week_start, star_delta=bucket_counts[week_start])
            for week_start in sorted(bucket_counts)
        ]
        return repository, points

    @staticmethod
    def _parse_starred_at(stargazer: dict[str, Any]) -> date:
        starred_at_raw = stargazer.get("starred_at")
        if not isinstance(starred_at_raw, str):
            raise ValueError("GitHub stargazer payload did not include starred_at")
        return datetime.fromisoformat(starred_at_raw.replace("Z", "+00:00")).date()

    @staticmethod
    def _start_of_week(value: date) -> date:
        return value - timedelta(days=value.weekday())
