"""Trend Intelligence API routes. Stays thin: parse request, call service,
map result to a response schema. No business logic or DB access here.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.v1.dependencies import (
    get_ai_analysis_service,
    get_orchestration_service,
    get_script_service,
    get_trend_service,
)
from app.api.v1.schemas.orchestration import GenerateVideoResponse
from app.api.v1.schemas.script import ScriptGenerationRequest, ScriptResponse
from app.api.v1.schemas.trend import TrendAnalysisResponse, TrendSearchRequest, TrendSearchResponse
from app.api.v1.schemas.video import AssembledVideoResponse
from app.services.ai_analysis_service import AIAnalysisService
from app.services.orchestration_service import OrchestrationService
from app.services.script_service import ScriptService
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


@router.post("/{search_id}/script", response_model=ScriptResponse, status_code=status.HTTP_201_CREATED)
async def generate_script(
    search_id: UUID,
    request: ScriptGenerationRequest,
    service: ScriptService = Depends(get_script_service),
) -> ScriptResponse:
    result = await service.generate(search_id, video_idea=request.video_idea)
    return ScriptResponse.model_validate(result)


@router.post(
    "/{search_id}/generate-video",
    response_model=GenerateVideoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_video(
    search_id: UUID,
    request: ScriptGenerationRequest,
    service: OrchestrationService = Depends(get_orchestration_service),
) -> GenerateVideoResponse:
    script, video = await service.generate_video(search_id, video_idea=request.video_idea)
    return GenerateVideoResponse(
        script=ScriptResponse.model_validate(script),
        video=AssembledVideoResponse.from_domain(video),
    )
