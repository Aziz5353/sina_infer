"""Renders graph state into the prompt context shared by assess, generate and clarify."""

from src.inference.state import SinaState


def render_case(case: dict | None) -> str:
    if not case:
        return "(none)"
    lines = []
    for key, value in case.items():
        if not value:
            continue
        rendered = ", ".join(value) if isinstance(value, list) else str(value)
        lines.append(f"- {key}: {rendered}")
    return "\n".join(lines) or "(none)"


def render_list(items: list[str] | None) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "(none)"


def render_web_results(results: list[dict] | None) -> str:
    if not results:
        return "(no results)"
    return "\n\n".join(
        f"[{i}] {r.get('title', '')}\nURL: {r.get('url', '')}\n{r.get('content', '')}"
        for i, r in enumerate(results, start=1)
    )


def request_text(state: SinaState) -> str:
    return state.get("standalone_message") or state["message"]


def render_case_context(state: SinaState) -> str:
    return (
        f"<request>\n{request_text(state)}\n</request>\n\n"
        f"query_type: {state.get('query_type', 'patient_case')}\n\n"
        f"<case>\n{render_case(state.get('case'))}\n</case>\n\n"
        f"<red_flags>\n{render_list(state.get('red_flags'))}\n</red_flags>\n\n"
        f"<missing_critical_info>\n{render_list(state.get('missing_critical_info'))}\n"
        f"</missing_critical_info>"
    )
