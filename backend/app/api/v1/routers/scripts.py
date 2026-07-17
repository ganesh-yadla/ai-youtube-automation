"""Script Agent API routes. Stays thin: parse request, call service, map
result to a response schema. No business logic or DB access here.
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.v1.dependencies import get_script_service
from app.api.v1.schemas.script import ScriptResponse
from app.exceptions.script_exceptions import ScriptNotFoundError
from app.services.script_service import ScriptService

router = APIRouter(prefix="/scripts", tags=["scripts"])


@router.get("/{script_id}", response_model=ScriptResponse)
async def get_script(
    script_id: UUID,
    service: ScriptService = Depends(get_script_service),
) -> ScriptResponse:
    result = await service.get_by_id(script_id)
    if result is None:
        raise ScriptNotFoundError(f"No script found with id '{script_id}'")
    return ScriptResponse.model_validate(result)
