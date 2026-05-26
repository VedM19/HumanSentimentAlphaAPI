from functools import lru_cache

from app.agents.star_growth_agent import StarGrowthComparisonAgent
from app.core.config import get_settings
from app.services.analytics import GitHubRepoAnalyticsService, RepoAnalyticsService
from app.services.github import GitHubClient


@lru_cache
def get_github_client() -> GitHubClient:
    return GitHubClient(settings=get_settings())


@lru_cache
def get_repo_analytics_service() -> RepoAnalyticsService:
    return GitHubRepoAnalyticsService(github_client=get_github_client())


def get_star_growth_agent() -> StarGrowthComparisonAgent:
    return StarGrowthComparisonAgent(
        analytics_service=get_repo_analytics_service(),
        github_client=get_github_client(),
    )
