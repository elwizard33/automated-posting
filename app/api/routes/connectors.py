from fastapi import APIRouter

from app.api.dependencies import SettingsDep
from app.platforms.registry import catalog
from app.schemas import ConnectorInfo

router = APIRouter(tags=["connectors"])


@router.get(
    "/connectors",
    summary="List every platform connector",
    description=(
        "Shows each connector's auth type, whether it is enabled, and which settings "
        "are still missing. Credential values are never returned."
    ),
)
async def list_connectors(settings: SettingsDep) -> list[ConnectorInfo]:
    return catalog(settings)
