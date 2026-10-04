from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

UI_INDEX = Path(__file__).resolve().parent.parent / "ui" / "index.html"

ui_router = APIRouter()


@ui_router.get("/", include_in_schema=False)
async def ui() -> FileResponse:
    return FileResponse(UI_INDEX)
