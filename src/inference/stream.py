import json
import time
from typing import AsyncIterator

from langgraph.graph.state import CompiledStateGraph

from src.inference.state import SinaState
from src.util.conversation_log import build_row, save_conversation


async def run_model_stream(
    chat_graph: CompiledStateGraph,
    graph_state: SinaState,
) -> AsyncIterator[str]:
    # Nodes send only client-facing text through the custom stream (plan's clarify /
    # refuse reply, answer's filtered tokens); raw model tokens never reach the client.
    t0 = time.perf_counter()
    final_state: dict = dict(graph_state)
    streamed: list[str] = []
    error = ""
    try:
        async for mode, payload in chat_graph.astream(
            graph_state,
            stream_mode=["custom", "values"],
        ):
            if mode == "values":
                final_state = payload
                continue
            content = payload["content"]
            streamed.append(content)
            yield f"data: {json.dumps({'content': content})}\n\n"
        yield "data: [DONE]\n\n"
    except BaseException as exc:
        # Includes client disconnects (CancelledError / GeneratorExit).
        error = type(exc).__name__
        raise
    finally:
        answer = final_state.get("answer") or "".join(streamed)
        save_conversation(build_row(final_state, answer, time.perf_counter() - t0, error))
