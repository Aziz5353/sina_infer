import json
from typing import AsyncIterator

from langchain_core.messages import AIMessageChunk
from langgraph.graph.state import CompiledStateGraph

from inference.state import SinaState

# Only these nodes' LLM tokens are forwarded to the SSE stream.
# Other nodes (e.g. analyzer) also produce AIMessageChunks but their
# output is internal (structured JSON, etc.) and must not reach the client.
STREAMABLE_NODES = {"generate", "refuse"}


async def run_model_stream(
    chat_graph: CompiledStateGraph,
    graph_state: SinaState,
) -> AsyncIterator[str]:
    async for chunk, metadata in chat_graph.astream(
        graph_state,
        stream_mode="messages",
    ):
        if metadata.get("langgraph_node") not in STREAMABLE_NODES:
            continue
        if isinstance(chunk, AIMessageChunk) and chunk.content:
            yield f"data: {json.dumps({'content': chunk.content})}\n\n"
    yield "data: [DONE]\n\n"
