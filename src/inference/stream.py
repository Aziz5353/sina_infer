import json
import time
from typing import AsyncIterator

from langchain_core.messages import AIMessageChunk
from langgraph.graph.state import CompiledStateGraph

from src.inference.state import SinaState
from src.util.conversation_log import build_row, save_conversation

# Only these nodes' LLM tokens are forwarded to the SSE stream.
# Other nodes (e.g. analyzer) also produce AIMessageChunks but their
# output is internal (structured JSON, etc.) and must not reach the client.
STREAMABLE_NODES = {"generate", "clarify", "refuse"}


async def run_model_stream(
    chat_graph: CompiledStateGraph,
    graph_state: SinaState,
) -> AsyncIterator[str]:
    t0 = time.perf_counter()
    final_state: dict = dict(graph_state)
    streamed: list[str] = []
    error = ""
    try:
        async for mode, payload in chat_graph.astream(
            graph_state,
            stream_mode=["messages", "values"],
        ):
            if mode == "values":
                final_state = payload
                continue
            chunk, metadata = payload
            if metadata.get("langgraph_node") not in STREAMABLE_NODES:
                continue
            if isinstance(chunk, AIMessageChunk) and chunk.content:
                streamed.append(chunk.content)
                yield f"data: {json.dumps({'content': chunk.content})}\n\n"
        yield "data: [DONE]\n\n"
    except BaseException as exc:
        # Includes client disconnects (CancelledError / GeneratorExit).
        error = type(exc).__name__
        raise
    finally:
        answer = final_state.get("answer") or "".join(streamed)
        save_conversation(build_row(final_state, answer, time.perf_counter() - t0, error))
