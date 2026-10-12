"""Search-only evaluation: runs plan + retrieve (no answer model) for a fixed question
set and checks whether the retrieved sources contain the facts a good answer needs.

    uv run python -m scripts.retrieval_eval            # one pass
    uv run python -m scripts.retrieval_eval --repeats 3

Prints a per-question report and appends a JSON summary to data/retrieval_eval.jsonl.
A fact counts as found when any of its patterns matches any source's title or content
(the search snippet plus the passages fetched by Tavily Extract).
"""

import argparse
import asyncio
import json
import logging
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from langgraph.graph import END, START, StateGraph

from src.inference.nodes.plan import plan_node
from src.inference.nodes.retrieve import retrieve_node
from src.inference.pipeline_definition import pipeline
from src.inference.state import SinaState

REPORT_PATH = Path("data/retrieval_eval.jsonl")

# (question, [(fact label, [regex alternatives])])
QUESTIONS: list[tuple[str, list[tuple[str, list[str]]]]] = [
    (
        "28F, 3 days of fever, dysuria, and right flank pain. Temp 38.9, HR 112. What is the differential and the most likely diagnosis?",
        [
            ("urine culture", [r"urine culture"]),
            ("fluoroquinolone regimen", [r"fluoroquinolone", r"ciprofloxacin"]),
            ("admission criteria", [r"hospitali[sz]", r"admission", r"inpatient"]),
            ("pregnancy", [r"pregnan"]),
            ("imaging if no improvement 48–72 h", [r"48\s*(–|-|to)\s*72", r"72 hours"]),
        ],
    ),
    (
        "What is the current first-line management of newly diagnosed type 2 diabetes with HbA1c 8.5% and established ASCVD?",
        [
            ("GLP-1 RA / SGLT2i for ASCVD", [r"(GLP-1|SGLT2|SGLT-2).{0,120}(ASCVD|atherosclerotic)", r"(ASCVD|atherosclerotic).{0,120}(GLP-1|SGLT2|SGLT-2)"]),
            ("independent of HbA1c", [r"independent(ly)? of (baseline )?(A1C|HbA1c|glyc)", r"regardless of (baseline )?(A1C|HbA1c|glyc)", r"irrespective of (baseline )?(A1C|HbA1c|glyc)"]),
            ("independent of metformin", [r"(independent|regardless|irrespective) of metformin", r"with or without metformin"]),
            ("statin", [r"statin"]),
        ],
    ),
    (
        "ما جرعة amoxicillin للأطفال في acute otitis media؟ وهل تحتاج تعديلًا في القصور الكلوي؟",
        [
            ("80–90 mg/kg/day", [r"80\s*(–|-|to)\s*90\s*mg/kg"]),
            ("two divided doses", [r"twice daily", r"two divided", r"divided (into )?(two|2) doses", r"every 12 hours", r"q12"]),
            ("renal adjustment threshold", [r"(GFR|creatinine clearance|CrCl)\s*(<|less than|below|of)\s*30"]),
            ("duration", [r"10[- ]days?", r"(5|7)\s*(–|-|to)\s*(7|10)\s*days"]),
        ],
    ),
    (
        "Interpret these ABG results: pH 7.28, PaCO2 28, HCO3 13, Na 138, Cl 102. What is the acid-base disorder?",
        [
            ("Winter's formula", [r"winter", r"1\.5\s*[×x\*]\s*\[?\s*HCO"]),
            ("anion gap formula", [r"anion gap\s*(\(AG\))?\s*=", r"Na\+?\s*[-−–]\s*\(?\s*\[?Cl"]),
            ("delta ratio / delta gap", [r"delta[- ](ratio|gap)", r"Δ\s*AG", r"ΔAG", r"Δ/Δ"]),
            ("normal anion gap range", [r"anion gap.{0,80}\b(8|10)\s*(–|-|to)\s*12", r"\b(8|10)\s*(–|-|to)\s*12\s*m(Eq|mol)"]),
        ],
    ),
    (
        "Calculate CHA2DS2-VASc for a 72-year-old woman with hypertension and diabetes, and advise on anticoagulation.",
        [
            ("age 65–74 = 1 point", [r"65\s*(–|-|to)\s*74"]),
            ("threshold for women", [r"(≥|>=|score of|scores? of)\s*3.{0,60}wom[ae]n", r"wom[ae]n.{0,80}(≥|>=|score of|scores? of)\s*3"]),
            ("CHA2DS2-VA (2024 ESC)", [r"CHA[2₂]DS[2₂][-‐–]?VA(?!S)"]),
            ("DOAC over warfarin", [r"(DOAC|NOAC|direct oral anticoagulant)s?.{0,100}(prefer|over (warfarin|VKA|vitamin K))", r"(prefer|recommended).{0,60}(DOAC|NOAC|direct oral anticoagulant)"]),
            ("bleeding risk", [r"HAS-BLED", r"bleeding risk"]),
        ],
    ),
    (
        "Write a SOAP note for a 35M with 2 days of sore throat, fever 38.5, tonsillar exudate, tender anterior nodes, no cough.",
        [
            ("Centor criteria", [r"centor"]),
            ("rapid antigen test", [r"rapid antigen", r"\bRADT\b"]),
            ("backup culture rule", [r"back-?up (throat )?culture"]),
            ("penicillin/amoxicillin first-line", [r"(penicillin|amoxicillin).{0,80}(first[- ]line|drug of choice|treatment of choice|recommended)"]),
            ("10-day course", [r"10[- ]days?"]),
        ],
    ),
    (
        "اشرح لمريض مصاب حديثًا بارتفاع ضغط الدم ما هو المرض وكيف يتعامل معه، بلغة عربية بسيطة.",
        [
            ("sodium target", [r"(sodium|salt).{0,80}(1,?500|2,?300)\s*mg", r"<\s*(1,?500|2,?300)\s*mg"]),
            ("DASH diet", [r"\bDASH\b"]),
            ("weight loss", [r"weight (loss|reduction)"]),
            ("exercise amount", [r"150\s*min", r"30\s*min"]),
            ("urgent threshold 180/120", [r"180\s*/\s*120"]),
        ],
    ),
    (
        "What does the evidence say about SGLT2 inhibitors in heart failure with preserved ejection fraction?",
        [
            ("EMPEROR-Preserved", [r"EMPEROR[- ]Preserved"]),
            ("DELIVER", [r"\bDELIVER\b"]),
            ("no mortality reduction", [r"mortality.{0,80}(not significant|no significant|neutral|did not|not reduce|comparable)", r"(no|not|without).{0,40}(significant )?(reduction|difference|effect).{0,40}(mortality|death)"]),
            ("guideline class", [r"class (I|1|2a|IIa)\b"]),
            ("10 mg dose", [r"10\s*mg"]),
        ],
    ),
    (
        "Adult with suspected anaphylaxis after a bee sting: hypotensive, wheezing, facial swelling. Step-by-step immediate management?",
        [
            ("IM epinephrine dose", [r"0\.(3|5)\s*mg", r"0\.01\s*mg/kg"]),
            ("thigh injection site", [r"(anterolateral|mid-?outer|lateral) (aspect of the )?thigh", r"vastus lateralis"]),
            ("positioning", [r"supine", r"recumbent", r"legs? (raised|elevated)"]),
            ("IV fluid bolus", [r"(fluid|crystalloid|saline).{0,60}(bolus|1\s*(–|-|to)\s*2\s*L|\d+\s*mL/kg)"]),
            ("airway management", [r"airway", r"intubat"]),
            ("bronchodilator", [r"salbutamol", r"albuterol", r"beta-?2[- ]agonist"]),
            ("glucagon (β-blockers)", [r"glucagon"]),
        ],
    ),
    (
        "Give me 5 high-yield MCQs on nephrotic vs nephritic syndrome with explanations, SMLE style.",
        [
            ("nephrotic proteinuria threshold", [r"3\.5\s*g"]),
            ("hypoalbuminemia", [r"hypoalbumin"]),
            ("RBC casts", [r"(RBC|red (blood )?cell) casts"]),
            ("minimal change disease", [r"minimal change"]),
            ("post-infectious / IgA", [r"post-?(streptococcal|infectious)", r"IgA nephropathy"]),
        ],
    ),
]


def _build_graph():
    def after_plan(state: SinaState) -> str:
        return "retrieve" if state.get("route") == "answer" else END

    builder = StateGraph(SinaState)
    builder.add_node("plan", plan_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_edge(START, "plan")
    builder.add_conditional_edges("plan", after_plan, {"retrieve": "retrieve", END: END})
    builder.add_edge("retrieve", END)
    return builder.compile()


def _check(facts: list[tuple[str, list[str]]], sources: list[dict]) -> list[dict]:
    texts = [f"{s.get('title', '')}\n{s.get('content', '')}" for s in sources]
    checked = []
    for label, patterns in facts:
        hits = [
            i
            for i, text in enumerate(texts, start=1)
            if any(re.search(p, text, re.IGNORECASE) for p in patterns)
        ]
        checked.append({"fact": label, "found_in": hits})
    return checked


async def _run_question(graph, number: int, question: str, facts) -> dict:
    t0 = time.perf_counter()
    state = await graph.ainvoke({"message": question})
    sources = state.get("web_results") or []
    return {
        "q": number,
        "route": state.get("route"),
        "task": state.get("task"),
        "queries": state.get("search_queries") or [],
        "sources": [{"title": s.get("title", ""), "url": s.get("url", "")} for s in sources],
        "facts": _check(facts, sources),
        "seconds": round(time.perf_counter() - t0, 1),
    }


def _print(result: dict) -> None:
    found = sum(1 for f in result["facts"] if f["found_in"])
    print(f"\nQ{result['q']}  {found}/{len(result['facts'])} facts  "
          f"route={result['route']} task={result['task']} "
          f"sources={len(result['sources'])} {result['seconds']}s")
    for query in result["queries"]:
        print(f"   query: {query}")
    for fact in result["facts"]:
        mark = "✔" if fact["found_in"] else "✘"
        where = f"sources {fact['found_in']}" if fact["found_in"] else "not found"
        print(f"   {mark} {fact['fact']}: {where}")
    domains = Counter((urlparse(s["url"]).hostname or "").removeprefix("www.") for s in result["sources"])
    print(f"   domains: {dict(domains.most_common())}")


async def main(repeats: int, only: list[int] | None) -> None:
    logging.basicConfig(level=logging.WARNING, force=True)
    pipeline.init()
    graph = _build_graph()

    selected = [(i, q, f) for i, (q, f) in enumerate(QUESTIONS, start=1) if not only or i in only]
    runs: list[list[dict]] = []
    for rep in range(1, repeats + 1):
        print(f"\n===== pass {rep}/{repeats} =====")
        results = []
        for number, question, facts in selected:
            result = await _run_question(graph, number, question, facts)
            _print(result)
            results.append(result)
        runs.append(results)

    total = sum(len(f) for _, _, f in selected)
    scores = [sum(1 for r in results for f in r["facts"] if f["found_in"]) for results in runs]
    print("\n===== summary =====")
    for number, _, facts in selected:
        per_pass = [
            sum(1 for f in next(r for r in results if r["q"] == number)["facts"] if f["found_in"])
            for results in runs
        ]
        print(f"Q{number}: {' / '.join(str(s) for s in per_pass)} of {len(facts)}")
    print(f"Total facts found: {' / '.join(str(s) for s in scores)} of {total} "
          f"(mean {sum(scores) / len(scores) / total:.0%})")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "repeats": repeats,
            "facts_total": total,
            "facts_found": scores,
            "runs": runs,
        }, ensure_ascii=False) + "\n")
    print(f"Report appended to {REPORT_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repeats", type=int, default=1, help="passes over the question set")
    parser.add_argument("--only", type=int, nargs="*", help="question numbers to run, e.g. --only 4 9")
    args = parser.parse_args()
    asyncio.run(main(args.repeats, args.only))
