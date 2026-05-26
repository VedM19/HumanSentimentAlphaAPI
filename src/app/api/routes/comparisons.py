from fastapi import APIRouter, Depends

from app.agents.star_growth_agent import StarGrowthComparisonAgent
from app.api.deps import get_star_growth_agent
from app.models.comparison import WeeklyStarComparisonRequest, WeeklyStarComparisonResponse

router = APIRouter(prefix="/v1/comparisons", tags=["comparisons"])


@router.post("/weekly-stars", response_model=WeeklyStarComparisonResponse)
async def compare_weekly_stars(
    payload: WeeklyStarComparisonRequest,
    agent: StarGrowthComparisonAgent = Depends(get_star_growth_agent),
) -> WeeklyStarComparisonResponse:
    return await agent.compare_weekly_star_growth(
        left_repository=payload.left_repository,
        right_repository=payload.right_repository,
        weeks=payload.weeks,
    )
