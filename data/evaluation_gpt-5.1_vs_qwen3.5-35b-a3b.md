# Sina evaluation: GPT-5.1 vs Qwen3.5-35B-A3B

**Goal of this evaluation:** get the highest-quality results from Sina running fully on the self-hosted Qwen model, since that is the deployment target.

Evaluated on 2026-10-11. Each answer is checked against the question asked, current clinical guidance, and Sina's own prompt contract (`src/config/constants.py`).

---

## 1. Runs compared

| Run | Data file | Turns | Models per node |
|---|---|---|---|
| **A. GPT** | `data/conversations_gpt-5.1.csv` (2026-10-08) | 10 | gpt-4o-mini for analyzer, contextualize, assess, clarify, refuse; **gpt-5.1** for generate only |
| **B. Qwen, thinking ON** | *(overwritten by run C; scores kept from the first evaluation)* | 7 | Qwen for every node; chain of thought leaked into every answer |
| **C. Qwen, thinking OFF** | `data/conversations_qwen3.5-35b-a3b.csv` (2026-10-11 09:29) | 10 | Qwen for every node, `enable_thinking: False` |

**Model identity.** The vLLM endpoint serves the model under the name `qwen3`. `/v1/models` reports `root: Qwen/Qwen3.5-35B-A3B-FP8`: a mixture-of-experts model with 35B total and about 3B active parameters, FP8-quantized. The first run was mislabelled "qwen3-8b".

**Caveat.** Each question was run once, and web search returns different sources on each run. Some differences between runs come from retrieval variance rather than the model; Q3 is the clearest example. Where this matters it is called out.

---

## 2. Scoring rubric

Each turn gets a score from 0 to 10:

| Dimension | Weight | What is checked |
|---|---|---|
| Routing | 2 | Right branch for the request (answer, clarify, refuse) |
| Clinical accuracy | 3 | No wrong facts, doses or thresholds; matches current guidance |
| Completeness | 2 | Answers what was asked, in the form asked; covers must-not-miss items |
| Grounding | 2 | Claims cited; sources relevant and current; no invented doses |
| Format & language | 1 | Follows the output contract; replies in the doctor's language |

Verdicts: **PASS** ≥ 7, **PARTIAL** 4–6, **FAIL** ≤ 3.

---

## 3. Results

| # | Question | A. GPT | B. Qwen (thinking) | **C. Qwen (no thinking)** | C route / outcome |
|---|---|---|---|---|---|
| 1 | Pyelonephritis case | 8 | 7 | **9** | answered |
| 2 | T2DM + ASCVD first-line | 6 | 9 | **7** | answered |
| 3 | Amoxicillin dose for pediatric AOM + renal (Arabic) | 2 | 8 | **2** | evidence-gap clarify ❌ |
| 4 | ABG interpretation | 2 | 3 | **1** | evidence-gap clarify ❌ |
| 5 | CHA2DS2-VASc + anticoagulation | 9 | 9 | **7** | answered |
| 6 | SOAP note, sore throat | 1 | 4 | **6** | answered, but not as a SOAP note |
| 7 | Hypertension explanation for a patient (Arabic) | 1 | 2 | **2** | evidence-gap clarify ❌ |
| 8 | SGLT2i in HFpEF | 9 | – | **8** | answered |
| 9 | Anaphylaxis management | 9 | – | **9** | answered |
| 10 | SMLE MCQs nephrotic vs nephritic | 1 | – | **1** | evidence-gap clarify ❌ |
| | **Total** | **48 / 100** | 42 / 70 | **52 / 100** | |

### Key metrics

| Metric | A. GPT | C. Qwen (no thinking) |
|---|---|---|
| Total score | 48 / 100 | **52 / 100** |
| PASS / PARTIAL / FAIL | 4 / 1 / 5 | 5 / 1 / 4 |
| Head-to-head on the 5 questions both models answered (Q1, 2, 5, 8, 9) | **41 / 50** | 40 / 50 |
| Wrong refusals | 3 | **0** |
| Unnecessary "evidence gap" clarifications | 2 | **4** |
| Replied in the wrong language | 1 (Q3) | 2 (Q3, Q7) |
| Mean latency, all turns | 22.7 s (refusals took about 3.6 s) | 30.8 s |
| Mean latency, generated answers | 35.5 s | 36.6 s |
| Reasoning leak | none | **none (fixed)** |

### What the numbers say

1. **When Qwen writes the final answer, it is on par with GPT-5.1** (40 vs 41 out of 50 on the same five questions). Qwen is better on pyelonephritis and anaphylaxis dosing, and GPT is better on CHA2DS2-VASc and HFpEF guideline context. **The model is not the bottleneck.**
2. **The pipeline is the bottleneck.** In run C, 4 of the 10 questions never reached the generate step: the evidence assessor declared a gap and sent the request to clarify. Those 4 turns account for 6 of the 52 points. If they were answered at the quality of the other turns (about 8 each), Qwen would score **about 80/100**. This is an estimate.
3. **Disabling thinking fixed the leak and halved latency** (66 s → 31 s). On the 7 questions shared with run B, the score dropped from 42 to 34. Part of that is retrieval variance: in Q3, run C did not retrieve the amoxicillin monograph and label that run B had. Part is lower reasoning quality in the generate and assess steps (Q2 and Q5 are less current and less precise). See enhancement M1.
4. **Over-refusal is gone with Qwen** (0 wrong refusals vs 3 with gpt-4o-mini). The same tasks now fail one step later, at the evidence check.

---

## 4. Per-question detail for run C (Qwen, thinking off), with GPT comparison

### Q1. 28F, fever, dysuria, right flank pain, T 38.9, HR 112. **C: 9 (PASS)** · A: 8

- ✔ Most likely: acute pyelonephritis. Red flag raised: possible sepsis, consider admission.
- ✔ **Pregnancy test listed as critical.** Run A missed this. The analyzer also flagged "pregnancy status" as missing, but still routed to search and stated the assumption, which is correct behavior.
- ✔ Urinalysis, urine culture and blood cultures. CT or ultrasound if complicated. FQ 5–7 d or TMP-SMX 14 d. Ceftriaxone if admitted. Re-evaluate at 48 h.
- ✗ "Complicated UTI / urosepsis" is listed as a separate differential; it is a severity grade, not a different diagnosis. Pyonephrosis, renal abscess and renal infarction are not named, and ectopic pregnancy/PID only appear as "gynecological".
- ✗ The source list includes uncited and irrelevant items (pediatric UTI, an AKI case report).

### Q2. T2DM, HbA1c 8.5%, established ASCVD. **C: 7 (PASS)** · A: 6 · B: 9

- ✔ Metformin plus an immediate SGLT2i or GLP-1 RA with proven CV benefit, regardless of HbA1c. Early combination therapy at 8.5%. Insulin threshold (HbA1c >10% or catabolic symptoms). High-intensity statin.
- ✗ **Relies on older sources** (ADA 2018, 2020 and 2021 abridged) even though **ADA 2025 Standards [8][9] and the 2026 CKM guideline [13] were retrieved**. It therefore misses the current position: SGLT2i/GLP-1 RA are recommended *independent of metformin*, and metformin is no longer a prerequisite. Run B got this right.
- ✗ **Format:** prints "⚠️ Red flags: none" and a **"Differential diagnosis" section** (type 1 diabetes as "must-not-miss") for a general clinical question.

### Q3. (Arabic) Amoxicillin dose for children with AOM; renal adjustment? **C: 2 (FAIL)** · A: 2 · B: 8

- ✗ The assessor declared an evidence gap because no source gave **pediatric renal dosing**. The **first half of the question, the AOM dose (80–90 mg/kg/day), was answerable** from the retrieved sources (AFP 2019 otitis review, Italian consensus, the high-dose papers), but the whole answer was withheld.
- ✗ The clarify reply is **in English** for an Arabic question. Its questions are poor; for example, it asks the doctor which guideline to prioritize.
- Retrieval differed from run B: this run fetched amoxicillin-clavulanate labels instead of the amoxicillin monograph.

### Q4. ABG pH 7.28 / PaCO2 28 / HCO3 13 / Na 138 / Cl 102. **C: 1 (FAIL)** · A: 2 · B: 3

- Reference answer: primary metabolic acidosis. Winter's expected PaCO2 = 27.5 ± 2, so compensation is appropriate. AG = 23 → high anion gap metabolic acidosis. Delta-delta ≈ 1, so no second metabolic disorder.
- ✗ Evidence-gap clarify again ("no source with the Winter's result for these values"). The clarify reply **asks the doctor to calculate the anion gap and delta gap**, which is the very task Sina was asked to do. This is worse than runs A and B.
- The retrieved sources (MSD Manual, StatPearls AG, AFP 2025 acid-base approach) contained every formula needed.

### Q5. CHA2DS2-VASc, 72F, HTN, DM. **C: 7 (PASS)** · A: 9 · B: 9

- ✔ Score of 4. OAC recommended. DOAC preferred, with the valve/mitral stenosis exception. HAS-BLED and renal function.
- ✗ Muddled threshold text ("≥2 or ≥3 depending on guideline… universally ≥2"). Cites the 2019 ACC/AHA and 2020 ESC guidelines, and **ignores source [13], which is specifically about the 2024 shift to CHA2DS2-VA**. Run B used it.
- ✗ "Annual stroke risk 4.8–7.2%" is not verifiable from the cited text. It assumes "not pregnant" for a 72-year-old. Same format issues as Q2 (empty red-flag header, a "Differential diagnosis" note).

### Q6. SOAP note, 35M with sore throat. **C: 6 (PARTIAL)** · A: 1 · B: 4

- ✔ Not refused, and no hallucinated "missing duration". Centor 4/4. Strep (GAS) pharyngitis vs viral vs EBV. Rapid antigen test. Penicillin or amoxicillin for 10 days. Allergy alternatives (azithromycin 5 d). Avoid amoxicillin if EBV.
- ✗ **Not written as a SOAP note.** It used the generic differential template, because the generate prompt has only one output format.
- ✗ **Clinical error:** "If RADT negative, backup throat culture is recommended." IDSA recommends backup culture for **children and adolescents only, not adults**.
- query_type was classified as `clinical_question` even though the request describes a specific patient.

### Q7. (Arabic) Explain hypertension to a newly diagnosed patient. **C: 2 (FAIL)** · A: 1 · B: 2

- ✔ No longer refused.
- ✗ **The analyzer wrote 2 of its 3 search queries in Chinese** ("高血压 患者教育 …"), which pulled in Chinese WHO documents and an unrelated Chinese oncology consensus.
- ✗ The assessor then looked for "Arabic patient-education material", did not find any, and declared a gap. The ESC 2024 hypertension guideline sources it had retrieved were enough to write the explanation.
- ✗ The reply is in English for an Arabic request, and starts with a stray line: "⚠️ Not a red flag case; proceeding with clarification."

### Q8. SGLT2i in HFpEF. **C: 8 (PASS)** · A: 9

- ✔ Concise and correct: reduces HF hospitalization and the composite outcome regardless of diabetes, no significant mortality reduction, better KCCQ scores and 6-minute walk. Doses **empagliflozin 10 mg and dapagliflozin 10 mg once daily**, sourced. Median follow-up 26.2 months.
- ✗ No guideline class of recommendation (ESC 2023 gives Class I), although the HFA statement [7] was retrieved. Less depth than run A on effect sizes (no HRs).

### Q9. Anaphylaxis after a bee sting. **C: 9 (PASS)** · A: 9

- ✔ IM epinephrine 0.01 mg/kg (max 0.5 mg), repeat every 5–15 min. Supine with legs raised. O2. 1–2 L crystalloid. Salbutamol 2.5–5 mg. Diphenhydramine 25–50 mg. **Famotidine 20 mg** (better than run A's withdrawn ranitidine). Epinephrine infusion from 0.1 µg/kg/min. Tryptase. Observe 4–24 h. Auto-injector. Most doses come from the Saudi MoH protocol, which is relevant locally.
- ✗ Fluids are described as "for hypotension not responding to epinephrine"; with shock present they should start immediately alongside epinephrine. Glucagon for patients on β-blockers is missing. The septic/cardiogenic shock differential is padding.

### Q10. 5 SMLE-style MCQs. **C: 1 (FAIL)** · A: 1

- ✔ Not refused.
- ✗ The assessor searched for **ready-made MCQs** and declared a gap when none were found. The glomerular disease review [1] had all the content needed to write them. The same article also appears **5 times** in the source list under different URLs.

---

## 5. Root causes in the Qwen pipeline

| # | Root cause | Questions affected | Points lost (approx.) |
|---|---|---|---|
| R1 | **The evidence assessor expects a source to contain the finished output** (the calculation result, an Arabic leaflet, ready-made MCQs, every sub-answer), so the generate step never runs | Q3, Q4, Q7, Q10 | ~25 |
| R2 | **A partial gap blocks the whole answer**: one unanswered sub-question means no answer at all | Q3 | (inside R1) |
| R3 | **One output template for every task**: no SOAP, patient-education or MCQ formats, and empty red-flag and differential sections still printed | Q2, Q5, Q6 | ~4 |
| R4 | **Older sources preferred over newer ones** that were also retrieved | Q2, Q5 | ~4 |
| R5 | **Language drift**: Chinese search queries; English clarify replies to Arabic questions | Q3, Q7 | ~2 |
| R6 | **Source list hygiene**: uncited sources listed, duplicates, irrelevant results | Q1, Q5, Q10 | ~1 |
| R7 | Individual clinical slips (adult backup culture, fluid timing, glucagon missing) | Q6, Q9 | ~2 |

---

## 6. Recommended enhancements

Ordered by expected impact on Qwen quality. "W" items change the workflow (code and prompts), "M" items change the model or how it is served.

### W1. Make the evidence assessor task-aware *(fixes R1; biggest gain)*

File: `src/config/constants.py` (`ASSESS_PROMPT`), `src/inference/nodes/assess_evidence.py`.

- Judge **whether the sources cover the underlying facts**, not whether they contain the finished product. Add to the prompt:
  - Calculations and scores (ABG, CHA2DS2-VASc, CrCl, corrected Na/Ca): sufficient if the sources give the formula or criteria. The doctor's own values will never appear in a source.
  - Composition tasks (SOAP note, patient explanation, MCQs, discharge letter): sufficient if the sources cover the clinical content. Language, reading level and format are Sina's job, not the source's.
- Better still, have the analyzer output a `task_type` (`answer | calculate | document | educate | teach`) and pass it to the assessor and generate step.
- **Search queries must always be in English.** Sources are English-only, so never search for "Arabic material".

### W2. Allow partial answers instead of all-or-nothing *(fixes R2)*

File: `src/inference/graph.py` (`_route_from_assess`), `GENERATE_PROMPT`.

- After the final search attempt, **route to `generate` whenever any part of the question is covered**, and pass `evidence_gaps` to the generate step so it states the uncovered parts ("Pediatric renal dosing was not in the configured sources; check a drug reference"). The current prompt already has a rule for this ("If a section cannot be supported, say so briefly").
- Send a request to `clarify` for an evidence gap only when **nothing** relevant was retrieved.

### W3. Build the output template in code, per task *(fixes R3)*

File: `src/inference/nodes/generate.py`, `GENERATE_PROMPT`.

- Do not ask the model to skip sections conditionally; Qwen frequently ignores "ONLY when…" instructions. **Assemble the format section in Python**: include the red-flag section only if `red_flags` is non-empty, use "Differential diagnosis" vs "Answer" based on query_type, and switch to a SOAP, patient-education (plain language, no citations inline, doctor-facing note at the end) or MCQ template based on `task_type`.
- Shorter, unconditional prompts are followed more reliably by smaller models.

### W4. Prefer current guidance *(fixes R4)*

File: `src/inference/context.py` (`render_web_results`), `src/inference/nodes/search.py`, `GENERATE_PROMPT`.

- Include the **publication year** and **source type** (guideline / review / trial / label) for each source in the context, extracted from the URL, title or Tavily metadata.
- Prompt rule: "When sources conflict, follow the most recent guideline from a major society; mention older positions only as history."
- Sort guidelines and recent sources first, and drop results older than about 10 years unless no newer source covers the topic.

### W5. Enforce language in code, not just the prompt *(fixes R5)*

File: `src/inference/nodes/analyzer.py`, `clarify.py`, `refuse.py`.

- Detect Arabic script in the message with a regex (`[؀-ۿ]`) and pass an explicit instruction to every user-facing node: "Respond in Arabic." This is more reliable than "respond in the user's language".
- Validate the analyzer's search queries: if a query contains non-ASCII/CJK characters, drop it or fall back to a translated message. This would have prevented the Chinese queries in Q7.

### W6. Render the Sources section in code *(fixes R6)*

File: `src/inference/nodes/generate.py`, `search.py`.

- Deduplicate search results by normalized URL and PMID/PMC ID in `search.py` (PMC6188440 appeared 5 times in Q10).
- Have the model output only the body with `[n]` citations, then **build the Sources list from the numbers actually cited**. This removes uncited and irrelevant sources and guarantees that every citation resolves.

### W7. Add a self-check step for safety-critical content *(fixes R7; optional)*

- Add a short "verify" pass after generate. The same Qwen model checks each dose, threshold and recommendation against the cited source text and flags or removes unsupported ones. This targets slips like the adult backup culture. It costs one extra call of about 5–10 s.

### M1. Turn thinking back on, but only where it pays, and without leaking it

File: vLLM launch flags, `src/inference/pipeline_definition.py`.

- Run B (thinking on) wrote better generate answers on Q2 and Q5 and judged evidence better on Q3. Run C is 2× faster.
- Recommended setup: start vLLM with **`--reasoning-parser qwen3`**, so reasoning goes to `reasoning_content` and never reaches `content`. Then enable thinking **only for `assess_llm` and `generate_llm`**, and keep it off for analyzer, contextualize, clarify and refuse, which need speed, not depth.
- Expected latency is roughly 40–50 s per answered question, in exchange for better currency and precision. Re-measure before adopting.

### M2. Set sampling parameters explicitly

File: `src/inference/pipeline_definition.py`.

- `analyzer_llm` and `assess_llm` currently send no temperature, so the server's default applies. Set **`temperature=0`** (or 0.1) for analyzer, assess and contextualize so routing and gap decisions are deterministic.
- For generate, follow Qwen's published recommendations for the chosen mode (non-thinking: about T 0.7 / top_p 0.8 / top_k 20; thinking: about T 0.6 / top_p 0.95 / top_k 20; check the model card). The current `GENERATE_TEMPERATURE=0.2` is fine for grounding, but very low temperatures can cause repetition with Qwen models. A/B test it.

### M3. Consider a larger Qwen3.5 variant only after W1–W3

- The head-to-head result (40 vs 41) shows Qwen3.5-35B-A3B already matches GPT-5.1 at writing grounded answers. Its weaknesses here are judgment calls (assessment, template following), which W1–W3 address directly.
- If GPU capacity allows and quality is still short after W1–W3, a larger Qwen3.5 model (more active parameters, e.g. a dense ~27B or a larger MoE; check what is released and what your GPUs fit) is the next lever.

### E1. Make evaluation repeatable

- Turn these 10 questions into a regression suite (`eval/cases.yaml`) with **expected route + key facts** per question, for example Q4: "metabolic acidosis", "anion gap 23", "appropriate compensation"; Q5: "score 4", "DOAC"; Q3: "80–90 mg/kg/day". This allows automatic scoring after every prompt change.
- Run each question **3 times** and average, because search results vary between runs.
- Add Arabic variants of a few English cases and a few multi-turn conversations, since `contextualize` was not exercised in this set.

---

## 7. Suggested order of work

| Step | Change | Effort | Expected effect on Qwen score |
|---|---|---|---|
| 1 | W1 + W2: task-aware assessor + partial answers | Small (prompt + routing) | **+20 to +25** (Q3, Q4, Q7, Q10 get answered) |
| 2 | W3: per-task template built in code | Medium | +3 to +5 (Q2, Q5, Q6) |
| 3 | W5 + W6: language enforcement + sources rendered in code | Small | +2 to +3 and cleaner output |
| 4 | M2: temperature 0 for analyzer/assess | Trivial | More consistent routing |
| 5 | W4: prefer current guidance | Medium | +3 to +4 (Q2, Q5) |
| 6 | M1: thinking on for assess and generate, with reasoning parser | Small (needs server restart) | Better precision; re-measure latency |
| 7 | E1: regression suite with 3× repeats | Medium | Measures 1–6 reliably |

With steps 1–3, a realistic target is **75–85/100** on this question set, comfortably above the GPT-5.1 configuration's 48. This is an estimate to verify with step 7.
