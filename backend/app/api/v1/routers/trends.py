"""Trend Intelligence API routes. Stays thin: parse request, call service,
map result to a response schema. No business logic or DB access here.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.v1.dependencies import get_ai_analysis_service, get_trend_service
from app.api.v1.schemas.trend import TrendAnalysisResponse, TrendSearchRequest, TrendSearchResponse
from app.services.ai_analysis_service import AIAnalysisService
from app.services.trend_service import TrendService

router = APIRouter(prefix="/trends", tags=["trends"])


@router.post("/search", response_model=TrendSearchResponse, status_code=status.HTTP_201_CREATED)
async def search_trends(
    request: TrendSearchRequest,
    service: TrendService = Depends(get_trend_service),
) -> TrendSearchResponse:
    result = await service.search(keyword=request.keyword, max_results=request.max_results)
    return TrendSearchResponse.model_validate(result)


@router.post(
    "/{search_id}/insights",
    response_model=TrendAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_insights(
    search_id: UUID,
    service: AIAnalysisService = Depends(get_ai_analysis_service),
) -> TrendAnalysisResponse:
    result = await service.analyze(search_id)
    return TrendAnalysisResponse.model_validate(result)


@router.get("/{search_id}", response_model=TrendSearchResponse)
async def get_trend_search(
    search_id: UUID,
    service: TrendService = Depends(get_trend_service),
) -> TrendSearchResponse:
    result = await service.get_by_id(search_id)
    return TrendSearchResponse.model_validate(result)
