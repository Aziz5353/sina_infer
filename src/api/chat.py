import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from src.model.chat_request import ChatRequest
from src.inference.state import SinaState
from src.inference.stream import run_model_stream

logger = logging.getLogger(__name__)
chat_router = APIRouter()


@chat_router.post("/chat")
async def chat(request: Request, req: ChatRequest):
    logger.info(
        f"chat | msg_chars={len(req.message)} history_turns={len(req.history)}"
    )
    logger.debug(
        f"chat | message={req.message!r} "
        f"history={[h.model_dump() for h in req.history]}"
    )

    # The graph is built in the app lifespan before any request is served; failures
    # inside the graph surface while streaming and are recorded by run_model_stream.
    initial_state = SinaState(
        message=req.message,
        history=[h.model_dump() for h in req.history],
    )
    return StreamingResponse(
        run_model_stream(
            chat_graph=request.app.state.graph,
            graph_state=initial_state,
        ),
        media_type="text/event-stream",
    )
