import asyncio
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.agents.star_growth_agent import StarGrowthComparisonAgent
from app.api.deps import get_star_growth_agent
from app.main import app
from app.models.repository import RepositoryRef, WeeklyGrowthPoint
from app.services.analytics import GitHubRepoAnalyticsService, RepoAnalyticsService
from app.services.github import GitHubNotFoundError


class StubAnalyticsService(RepoAnalyticsService):
    async def get_weekly_growth(
        self,
        repository: RepositoryRef,
        weeks: int,
    ) -> tuple[RepositoryRef, list[WeeklyGrowthPoint]]:
        if repository.full_name == "NVIDIA/TensorRT":
            values = [10, 12, 20, 40]
        else:
            values = [15, 15, 15, 15]

        anchor = datetime.now(UTC).date() - timedelta(days=datetime.now(UTC).date().weekday())
        points = [
            WeeklyGrowthPoint(
                week_start=anchor - timedelta(weeks=len(values) - index - 1),
                star_delta=value,
            )
            for index, value in enumerate(values[-weeks:])
        ]
        return repository, points


class StubGitHubClient:
    async def get_repository(self, owner: str, name: str) -> dict[str, int]:
        if owner == "ROCm" and name == "MissingRepo":
            raise GitHubNotFoundError(f"{owner}/{name}")

        if owner == "NVIDIA" and name == "TensorRT":
            return {"stargazers_count": 12000}
        return {"stargazers_count": 7000}


client = TestClient(app)


def override_star_growth_agent() -> StarGrowthComparisonAgent:
    return StarGrowthComparisonAgent(
        analytics_service=StubAnalyticsService(),
        github_client=StubGitHubClient(),  # type: ignore[arg-type]
    )


def test_healthcheck() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_weekly_star_comparison_shape() -> None:
    app.dependency_overrides[get_star_growth_agent] = override_star_growth_agent
    try:
        response = client.post(
            "/api/v1/comparisons/weekly-stars",
            json={
                "weeks": 4,
                "left_repository": {"owner": "NVIDIA", "name": "TensorRT"},
                "right_repository": {"owner": "ROCm", "name": "ROCm"},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["winner"] == "NVIDIA/TensorRT"
    assert "momentum" in payload["summary"].lower()
    assert "current github stars" in payload["summary"].lower()
    assert len(payload["repositories"]) == 2
    assert all(len(repo["weekly_deltas"]) == 4 for repo in payload["repositories"])
    assert all(isinstance(repo["momentum_score"], float) for repo in payload["repositories"])
    assert all(isinstance(repo["current_stargazers"], int) for repo in payload["repositories"])


def test_weekly_star_comparison_rejects_duplicate_repositories() -> None:
    response = client.post(
        "/api/v1/comparisons/weekly-stars",
        json={
            "weeks": 4,
            "left_repository": {"owner": "NVIDIA", "name": "TensorRT"},
            "right_repository": {"owner": "NVIDIA", "name": "TensorRT"},
        },
    )

    assert response.status_code == 422


class FakeGitHubClient:
    def __init__(self, pages: list[list[dict[str, str]]]) -> None:
        self.pages = pages

    async def list_stargazers(
        self,
        owner: str,
        name: str,
        *,
        page: int,
        per_page: int = 100,
    ) -> list[dict[str, str]]:
        index = page - 1
        if index >= len(self.pages):
            return []
        return self.pages[index]


def test_github_repo_analytics_service_buckets_by_week() -> None:
    anchor = datetime.now(UTC).date() - timedelta(days=datetime.now(UTC).date().weekday())
    pages = [
        [
            {"starred_at": f"{anchor.isoformat()}T12:00:00Z"},
            {"starred_at": f"{(anchor - timedelta(days=1)).isoformat()}T12:00:00Z"},
            {"starred_at": f"{(anchor - timedelta(weeks=1)).isoformat()}T12:00:00Z"},
        ]
    ]
    service = GitHubRepoAnalyticsService(github_client=FakeGitHubClient(pages))  # type: ignore[arg-type]

    repository, points = asyncio.run(
        service.get_weekly_growth(RepositoryRef(owner="NVIDIA", name="TensorRT"), weeks=2)
    )

    assert repository.full_name == "NVIDIA/TensorRT"
    assert [point.star_delta for point in points] == [2, 1]
