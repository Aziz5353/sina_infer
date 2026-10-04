import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langgraph.graph.state import CompiledStateGraph

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

    chat_graph: CompiledStateGraph | None = getattr(request.app.state, "graph", None)
    if chat_graph is None:
        logger.error("Could not retrieve server graph")
        raise HTTPException(
            status_code=500,
            detail="Server graph was not initiated successfully.",
        )

    try:
        initial_state = SinaState(
            message=req.message,
            history=[h.model_dump() for h in req.history],
        )

        logger.debug("chat | starting streaming response")
        return StreamingResponse(
            run_model_stream(
                chat_graph=chat_graph,
                graph_state=initial_state,
            ),
            media_type="text/event-stream",
        )

    except Exception:
        logger.exception("Chat request failed")
        raise HTTPException(
            status_code=500,
            detail="Chat request failed. Check logs for details.",
        )
