from fastapi import APIRouter, HTTPException, Request

health_router = APIRouter()


@health_router.get("/health")
async def health(request: Request) -> dict:
    if getattr(request.app.state, "graph", None) is None:
        raise HTTPException(status_code=503, detail="graph not initialized")
    return {"status": "ok"}
