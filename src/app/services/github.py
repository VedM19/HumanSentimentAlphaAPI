from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import Settings


class GitHubClientError(Exception):
    """Base exception for GitHub client failures."""


class GitHubAPIError(GitHubClientError):
    """Raised when GitHub returns a non-success response."""

    def __init__(self, message: str, *, status_code: int, response_body: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class GitHubGraphQLError(GitHubClientError):
    """Raised when a GraphQL response includes one or more errors."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        super().__init__("GitHub GraphQL request failed.")
        self.errors = errors


class GitHubNotFoundError(GitHubClientError):
    """Raised when a GitHub resource does not exist."""

    def __init__(self, resource: str) -> None:
        super().__init__(f"GitHub resource not found: {resource}")
        self.resource = resource


@dataclass(slots=True)
class GitHubClient:
    """
    Reusable async GitHub API shell backed by httpx.

    This client is intentionally small but production-shaped: it centralizes
    auth, timeouts, REST/GraphQL requests, and consistent error handling so the
    analytics adapter can focus on star-growth logic.
    """

    settings: Settings
    timeout: float = 15.0
    _client: httpx.AsyncClient | None = field(default=None, init=False, repr=False)

    def build_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "human-sentiment-alpha-api",
        }
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        return headers

    async def __aenter__(self) -> "GitHubClient":
        await self._ensure_client()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        return await self.request("GET", path, params=params, headers=headers)

    async def post(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        return await self.request("POST", path, params=params, json=json, headers=headers)

    async def get_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        payload = await self.get_payload(path, params=params, headers=headers)
        if not isinstance(payload, dict):
            raise GitHubClientError("Expected a JSON object from GitHub REST API.")
        return payload

    async def get_payload(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        response = await self.get(path, params=params, headers=headers)
        return response.json()

    async def graphql(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        client = await self._ensure_client()
        response = await client.post(
            self.settings.github_graphql_url,
            json={"query": query, "variables": variables or {}},
        )
        self._raise_for_status(response)

        payload = response.json()
        if not isinstance(payload, dict):
            raise GitHubClientError("Expected a JSON object from GitHub GraphQL API.")

        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            raise GitHubGraphQLError(errors)

        data = payload.get("data")
        if not isinstance(data, dict):
            raise GitHubClientError("GitHub GraphQL response did not include a data object.")
        return data

    async def get_repository(self, owner: str, name: str) -> dict[str, Any]:
        path = f"/repos/{owner}/{name}"
        try:
            return await self.get_json(path)
        except GitHubAPIError as exc:
            if exc.status_code == 404:
                raise GitHubNotFoundError(f"{owner}/{name}") from exc
            raise

    async def list_stargazers(
        self,
        owner: str,
        name: str,
        *,
        page: int,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        try:
            payload = await self.get_payload(
                f"/repos/{owner}/{name}/stargazers",
                params={"page": page, "per_page": per_page},
                headers={"Accept": "application/vnd.github.star+json"},
            )
        except GitHubAPIError as exc:
            if exc.status_code == 404:
                raise GitHubNotFoundError(f"{owner}/{name}") from exc
            raise
        if not isinstance(payload, list):
            raise GitHubClientError("Expected a JSON array from GitHub stargazers API.")
        if not all(isinstance(item, dict) for item in payload):
            raise GitHubClientError("GitHub stargazers API returned an invalid payload.")
        return payload

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        client = await self._ensure_client()
        response = await client.request(method, path, params=params, json=json, headers=headers)
        self._raise_for_status(response)
        return response

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.settings.github_api_url,
                headers=self.build_headers(),
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.is_success:
            return

        body = response.text.strip()
        if len(body) > 500:
            body = f"{body[:500]}..."
        raise GitHubAPIError(
            f"GitHub API request failed with status {response.status_code}.",
            status_code=response.status_code,
            response_body=body,
        )
