import asyncio
from dataclasses import dataclass

from fastapi import HTTPException

from app.models.comparison import (
    RepoGrowthSummary,
    WeeklyStarComparisonResponse,
    WeeklyStarDelta,
)
from app.models.repository import RepositoryRef, WeeklyGrowthPoint
from app.services.analytics import RepoAnalyticsService
from app.services.github import (
    GitHubAPIError,
    GitHubClient,
    GitHubClientError,
    GitHubNotFoundError,
)
from app.services.metrics import calculate_momentum_score


@dataclass(slots=True)
class StarGrowthComparisonAgent:
    """Coordinates repository analytics and produces a comparison summary."""

    analytics_service: RepoAnalyticsService
    github_client: GitHubClient

    async def compare_weekly_star_growth(
        self,
        *,
        left_repository: RepositoryRef,
        right_repository: RepositoryRef,
        weeks: int,
    ) -> WeeklyStarComparisonResponse:
        repositories = [left_repository, right_repository]

        try:
            growth_batch, live_star_counts = await asyncio.gather(
                self.analytics_service.get_weekly_growth_batch(
                    repositories=repositories,
                    weeks=weeks,
                ),
                self._fetch_live_star_counts(repositories),
            )
        except GitHubNotFoundError as exc:
            raise HTTPException(
                status_code=404,
                detail=f"Repository not found on GitHub: {exc.resource}",
            ) from exc
        except GitHubAPIError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"GitHub returned status {exc.status_code} while fetching repository data.",
            ) from exc
        except GitHubClientError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"GitHub request failed: {exc}",
            ) from exc
        left_growth, right_growth = growth_batch

        winner = self._select_winner(left_growth, right_growth)
        summary = self._build_summary(
            left_growth,
            right_growth,
            winner,
            live_star_counts=live_star_counts,
        )

        return WeeklyStarComparisonResponse(
            winner=winner.full_name,
            summary=summary,
            repositories=[
                self._to_repo_summary(left_growth, live_star_counts),
                self._to_repo_summary(right_growth, live_star_counts),
            ],
        )

    def _select_winner(
        self,
        left: tuple[RepositoryRef, list[WeeklyGrowthPoint]],
        right: tuple[RepositoryRef, list[WeeklyGrowthPoint]],
    ) -> RepositoryRef:
        left_repo, left_points = left
        right_repo, right_points = right
        left_score = calculate_momentum_score(left_points)
        right_score = calculate_momentum_score(right_points)
        return left_repo if left_score >= right_score else right_repo

    def _build_summary(
        self,
        left: tuple[RepositoryRef, list[WeeklyGrowthPoint]],
        right: tuple[RepositoryRef, list[WeeklyGrowthPoint]],
        winner: RepositoryRef,
        *,
        live_star_counts: dict[str, int],
    ) -> str:
        left_repo, left_points = left
        right_repo, right_points = right
        left_score = calculate_momentum_score(left_points)
        right_score = calculate_momentum_score(right_points)
        gap = abs(left_score - right_score)
        loser = right_repo if winner == left_repo else left_repo
        winner_score = left_score if winner == left_repo else right_score
        loser_score = right_score if winner == left_repo else left_score
        return (
            f"{winner.full_name} shows stronger recent GitHub adoption momentum over the "
            f"last {len(left_points)} weeks, with an EWMA star-growth score of "
            f"{winner_score:.2f} versus {loser.full_name}'s {loser_score:.2f}, a margin "
            f"of {gap:.2f}. Current GitHub stars are "
            f"{left_repo.full_name}: {live_star_counts[left_repo.full_name]} and "
            f"{right_repo.full_name}: {live_star_counts[right_repo.full_name]}."
        )

    def _to_repo_summary(
        self,
        result: tuple[RepositoryRef, list[WeeklyGrowthPoint]],
        live_star_counts: dict[str, int],
    ) -> RepoGrowthSummary:
        repo, points = result
        total_growth = sum(point.star_delta for point in points)
        momentum_score = calculate_momentum_score(points)
        return RepoGrowthSummary(
            repository=repo.full_name,
            total_growth=total_growth,
            momentum_score=momentum_score,
            current_stargazers=live_star_counts[repo.full_name],
            weekly_deltas=[
                WeeklyStarDelta(week_start=point.week_start, stars_gained=point.star_delta)
                for point in points
            ],
        )

    async def _fetch_live_star_counts(self, repositories: list[RepositoryRef]) -> dict[str, int]:
        responses = await asyncio.gather(
            *(self._fetch_stargazers_count(repository) for repository in repositories)
        )
        return {repository_name: stargazers for repository_name, stargazers in responses}

    async def _fetch_stargazers_count(
        self,
        repository: RepositoryRef,
    ) -> tuple[str, int]:
        try:
            payload = await self.github_client.get_repository(repository.owner, repository.name)
        except GitHubNotFoundError:
            raise HTTPException(
                status_code=404,
                detail=f"Repository not found on GitHub: {repository.full_name}",
            )
        except GitHubAPIError as exc:
            raise HTTPException(
                status_code=502,
                detail=(
                    f"GitHub returned status {exc.status_code} while fetching "
                    f"{repository.full_name}."
                ),
            ) from exc
        except GitHubClientError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"GitHub request failed while fetching {repository.full_name}: {exc}",
            ) from exc

        stargazers_count = payload.get("stargazers_count")
        if not isinstance(stargazers_count, int):
            raise HTTPException(
                status_code=502,
                detail=f"GitHub response for {repository.full_name} did not include stargazers_count",
            )

        return repository.full_name, stargazers_count
