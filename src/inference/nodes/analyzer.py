import logging
import time
from typing import Literal, cast

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.config.constants import ANALYZER_PROMPT
from src.inference.pipeline_definition import pipeline
from src.inference.state import SinaState

logger = logging.getLogger(__name__)


class AnalyzerOutput(BaseModel):
    route: Literal["retrieve", "search", "generate", "refuse"] = Field(
        description="Which downstream branch should run for this question."
    )
    rewritten_query: str | None = Field(
        default=None,
        description=(
            "Verse-like Arabic query used only when route='retrieve'. "
            "Must be null for any other route."
        ),
    )
    poet_name: str | None = Field(
        default=None,
        description="Arabic poet name if explicitly mentioned by the user; otherwise null.",
    )
    poet_era: str | None = Field(
        default=None,
        description="Arabic literary era if explicitly mentioned (e.g. الجاهلي، العباسي).",
    )
    poem_category: list[str] | None = Field(
        default=None,
        description=(
            "List of Arabic poem purpose/category values explicitly mentioned by the user "
            "(e.g. [\"فخر\"], or [\"مدح\", \"حماسة\"] when several are mentioned). "
            "Null if none is mentioned."
        ),
    )
    poem_meter: str | None = Field(
        default=None,
        description=(
            "Arabic poetic meter (بحر) when named directly OR implied by a derived/nisba "
            "form (e.g. أراجيز→الرجز, موشحة→موشح), mapped to one of the allowed values "
            "(e.g. الطويل، الكامل، الوافر). Null only when no meter is referenced at all."
        ),
    )
    poem_rhyme: str | None = Field(
        default=None,
        description=(
            "Arabic rhyme (قافية) if explicitly mentioned by the user, mapped to one of the "
            "allowed full-string values (e.g. 'قافية الراء (ر)'). Null if none is mentioned."
        ),
    )
    refusal_reason: str | None = Field(
        default=None,
        description="Short reason when route='refuse'; otherwise null.",
    )


async def analyzer_node(state: SinaState) -> dict:
    t0 = time.perf_counter()
    logger.debug(f"analyzer | question={state['question']!r}")
    llm = pipeline.analyzer_llm.with_structured_output(AnalyzerOutput)
    result = cast(
        AnalyzerOutput,
        await llm.ainvoke(
            [
                SystemMessage(content=ANALYZER_PROMPT),
                HumanMessage(content=state["question"]),
            ]
        ),
    )
    took = time.perf_counter() - t0
    logger.info(
        f"analyzer | route={result.route} "
        f"rewritten={result.rewritten_query!r} "
        f"poet_name={result.poet_name or '-'} "
        f"poet_era={result.poet_era or '-'} "
        f"poem_category={result.poem_category or '-'} "
        f"poem_meter={result.poem_meter or '-'} "
        f"poem_rhyme={result.poem_rhyme or '-'} "
        f"refusal={result.refusal_reason or '-'} took={took:.2f}s"
    )
    return {
        "route": result.route,
        "rewritten_query": result.rewritten_query,
        "poet_name": result.poet_name,
        "poet_era": result.poet_era,
        "poem_category": result.poem_category,
        "poem_meter": result.poem_meter,
        "poem_rhyme": result.poem_rhyme,
        "refusal_reason": result.refusal_reason,
    }
