from fastapi import FastAPI

from app.api.routes.comparisons import router as comparisons_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Agent-driven weekly GitHub star-growth comparisons.",
    )
    app.include_router(comparisons_router, prefix=settings.api_prefix)

    @app.get("/health", tags=["system"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
