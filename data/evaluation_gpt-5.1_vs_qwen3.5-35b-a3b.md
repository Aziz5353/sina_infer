# Sina evaluation: Qwen3.5-35B-A3B vs GPT-5.1

**Goal of this evaluation:** get the highest-quality results from Sina running fully on the self-hosted Qwen model, since that is the deployment target.

Evaluated on 2026-10-12. Each answer is checked against the question asked, current clinical guidance, and Sina's own prompt contract (`src/config/constants.py`).

---

## 1. Runs compared

| | **GPT-5.1** | **Qwen3.5-35B-A3B** |
|---|---|---|
| Data file | `data/conversations_gpt-5.1.csv`, all 10 rows | `data/conversations_qwen3.5-35b-a3b_v3.csv`, **last 10 rows only** (rows 31–40) |
| Date | 2026-10-08 | 2026-10-12 |
| Graph | Old graph: contextualize → analyzer → search ⇄ assess evidence (up to 2 search rounds) → generate, with clarify and refuse branches | plan → retrieve → answer |
| Models | gpt-4o-mini for analyzer, contextualize, assess, clarify and refuse; **gpt-5.1** for generate only | **Qwen3.5-35B-A3B-FP8** on vLLM (served as `qwen3`, thinking off) for plan and answer; temperature 0 for both |
| Model calls per answered turn | 4–5 | 2 |
| Code | Before the graph redesign | Commit `0538226` plus the three calculation prompt edits described in section 6 |

The same 10 questions were asked in both runs, each in a new conversation (no history).

**What this comparison is and is not.**
- It compares two complete systems. The model **and** the pipeline differ, so the total score gap cannot be credited to the model alone. Section 4 separates the two where possible.
- Each system ran each question once. Search results vary between runs. The Qwen rows used here are the third of three repeats on the same code; the other two scored 75 and 74, so this run is representative.

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

| # | Question | GPT-5.1 | **Qwen** | GPT-5.1 outcome | Qwen outcome |
|---|---|---|---|---|---|
| 1 | Pyelonephritis case | **8** | 7 | answered | answered (consult) |
| 2 | T2DM + ASCVD first-line | 8 | 8 | answered | answered (consult) |
| 3 | Amoxicillin for pediatric AOM + renal (Arabic) | 1 | **8** | evidence-gap clarify, in English | answered, in Arabic |
| 4 | ABG interpretation | 1 | **9** | evidence-gap clarify | answered (calculation) |
| 5 | CHA2DS2-VASc + anticoagulation | **8** | 6 | answered | answered (calculation) |
| 6 | SOAP note, sore throat | 1 | **5** | refused as "non-medical" | answered (SOAP note) |
| 7 | Hypertension explained to a patient (Arabic) | 1 | **8** | refused | answered (patient explanation), in Arabic |
| 8 | SGLT2i in HFpEF | **9** | 8 | answered | answered (consult) |
| 9 | Anaphylaxis management | **9** | 8 | answered | answered (consult) |
| 10 | SMLE MCQs, nephrotic vs nephritic | 1 | **8** | refused | answered (5 MCQs) |
| | **Total** | **47 / 100** | **75 / 100** | | |

### Key metrics

| Metric | GPT-5.1 | Qwen |
|---|---|---|
| Total score | 47 / 100 | **75 / 100** |
| PASS / PARTIAL / FAIL | 5 / 0 / 5 | **8 / 2 / 0** |
| Questions answered | 5 / 10 | **10 / 10** |
| Wrong refusals | 3 (Q6, Q7, Q10) | **0** |
| Unnecessary clarifications | 2 (Q3, Q4) | **0** |
| Replied in the wrong language | 1 (Q3) | **0** |
| **Head-to-head on the 5 questions both answered** (Q1, 2, 5, 8, 9) | **42 / 50** | 37 / 50 |
| Mean latency, all turns | 22.7 s (refusals took about 3.7 s) | **15.8 s** |
| Mean latency, answered turns | 35.5 s | **15.8 s** |
| Mean answer length on Q1, 2, 5, 8, 9 | 7,870 characters | 4,250 characters |
| Runs on own hardware | no | **yes** |

GPT-5.1 scores were re-checked for this report and differ slightly from the earlier version: Q2 6 → 8, Q3 and Q4 2 → 1, Q5 9 → 8 (total 48 → 47).

---

## 4. What the numbers say

1. **The Qwen system wins by 28 points because it answers every question.** On the five questions the GPT system did not answer (Q3, Q4, Q6, Q7, Q10), Qwen scores 38 points against 5. On the five both answered, GPT-5.1 leads by 5.
2. **The GPT system's failures came from its old pipeline, not from GPT-5.1.** gpt-4o-mini refused a SOAP note, a patient explanation and MCQs as "non-medical". The evidence assessor sent Q3 and Q4 to clarify because no source contained the finished answer, and asked the doctor about age, medications and "which severity". GPT-5.1 never saw those five questions.
3. **When both answer, GPT-5.1 still writes the better answer** (42 vs 37). It is more complete on safety-critical details: immediate fluids, airway escalation and glucagon in anaphylaxis; DOAC preference and "no aspirin" for AF; guideline positions for HFpEF. Its costs are length (almost twice as long), padding (AKI guidelines in a pyelonephritis answer, a mechanisms section for HFpEF) and one withdrawn drug (ranitidine).
4. **Qwen is more than twice as fast on answered turns** (15.8 s vs 35.5 s) with 2 model calls instead of 4–5, and it runs on self-hosted hardware.
5. **Most of Qwen's remaining errors are copied from weak or old sources**, not invented: a repeat urine culture after treatment (AFP 2005), a backup throat culture for an adult (a Medscape calculator page), fluids held back until hypotension persists (AFP). Grounding works as designed, so what the model writes is only as current as the sources it is given (section 7).
6. **Both systems miss the same things:** neither orders a pregnancy test in a 28-year-old woman with pyelonephritis, and neither names the 2024 ESC change to CHA2DS2-VA.

---

## 5. Per-question detail

### Q1. 28F, fever, dysuria, right flank pain, T 38.9, HR 112. GPT-5.1: 8 · Qwen: 7

Reference: acute pyelonephritis; pregnancy test; urinalysis and urine culture before antibiotics (blood cultures if severe); oral FQ for 5–7 days, with a single parenteral dose (e.g. ceftriaxone) first where FQ resistance is >10%; imaging if septic, obstruction is suspected or no improvement at 48–72 h; admission criteria.

- **GPT-5.1** ✔ Ranked differential including perinephric abscess, renal infarction and stones. Imaging only when septic, obstructed or not improving at 48–72 h. Outpatient vs admission criteria. Follow-up in 24–48 h. ✗ Pregnancy assumed negative, no test ordered. Durations from a 2001 review (FQ 7–14 d, TMP-SMX ≥14 d), and no initial parenteral dose for high resistance. KDIGO AKI guidelines cited as padding. Renal infarction supported by a case report.
- **Qwen** ✔ Sepsis red flags. Culture before antibiotics. FQ for 7 days, plus a single ceftriaxone or aminoglycoside dose if FQ resistance is >10%. Admission criteria and imaging at 72 h. ✗ Pregnancy assumed negative; only named under "what would change the assessment". **Recommends a repeat urine culture 1–2 weeks after treatment** (AFP 2005; not recommended for non-pregnant women). Renal infarction listed from a single case report. Gynecological causes only mentioned generically (no PID or ectopic pregnancy).

### Q2. T2DM, HbA1c 8.5%, established ASCVD. GPT-5.1: 8 · Qwen: 8

Reference: a GLP-1 RA with proven CV benefit or an SGLT2i, independent of HbA1c and of metformin (ADA Standards); consider combination therapy at 8.5%; statin and other secondary prevention.

- **GPT-5.1** ✔ Sets out both positions (metformin-first vs complication-centric). Says SGLT2i/GLP-1 RA are recommended independently of HbA1c and other glucose-lowering drugs. Recommends early combination with metformin. Statin and HbA1c target. ✗ Gives the older metformin-first position equal weight and relies on a Chinese consensus. Newest sources are from 2023. Long.
- **Qwen** ✔ GLP-1 RA or SGLT2i first-line, independent of glycemic control, chosen by comorbidity. Names the GLP-1 RAs with proven CV benefit. Add the other class if above target. ✗ No statin. The contraindications bullet says it comes from "standard clinical knowledge": accurate, but it breaks the grounding rule. The plan searched for "ADA Standards of Care 2024" in 2026, and most cited sources are cohort studies.

### Q3. (Arabic) Amoxicillin dose for children with AOM; renal adjustment? GPT-5.1: 1 · Qwen: 8

Reference: 80–90 mg/kg/day in 2 divided doses; duration by age (10 d under 2 y, 7 d at 2–5 y, 5–7 d at 6 y and over); adjust only when GFR is <30 mL/min; the pediatric renal regimen comes from a drug reference.

- **GPT-5.1** ✗ Evidence-gap clarify ("no specific pediatric dosing for amoxicillin in acute otitis media"). **Reply in English** to an Arabic question. Asks the doctor for age ranges, severity and other medications.
- **Qwen** ✔ Fully Arabic. 80–90 mg/kg/day in two doses. Correct age-based durations. Names the adjustment threshold (GFR 10–30) from NICE CKS and says plainly that the sources lack a pediatric renal regimen, pointing to a drug reference. ✗ No watchful waiting or amoxicillin-clavulanate indication. One filler line on maximum dose.

### Q4. ABG pH 7.28 / PaCO2 28 / HCO3 13 / Na 138 / Cl 102. GPT-5.1: 1 · Qwen: 9

Reference: primary metabolic acidosis; AG 23, so high anion gap; Winter's 27.5 ± 2, so compensation is appropriate; delta ratio 11/11 = 1.0, so no additional metabolic disorder; next: lactate, ketones, renal function, osmolar gap, albumin.

- **GPT-5.1** ✗ Evidence-gap clarify ("no specific interpretation for the given ABG values"). Asks for age, history and medications, none of which are needed to interpret an ABG.
- **Qwen** ✔ Matches the reference in full, with every step's arithmetic shown, a Result consistent with the Working, and osmolar gap and albumin correction as next steps. ✗ Shows two delta methods; hedges the delta-ratio range ("1.0 to 2.0 depending on the guideline").

### Q5. CHA2DS2-VASc, 72F, HTN, DM. GPT-5.1: 8 · Qwen: 6

Reference: score 4; OAC recommended (ACC/AHA: ≥2 in men, ≥3 in women; 2024 ESC: CHA2DS2-VA = 3); DOAC over VKA except mechanical valve or moderate–severe mitral stenosis; no aspirin; bleeding-risk assessment; the score assumes AF.

- **GPT-5.1** ✔ Score 4. Sex-specific thresholds. DOAC preferred, with the valve exception. No aspirin. States the AF assumption. ✗ No bleeding-risk assessment. No CHA2DS2-VA, although a 2024 ESC key-points source was retrieved.
- **Qwen** ✔ Score 4 with each point shown. ACC/AHA sex-specific thresholds and the 2024 ESC threshold. HAS-BLED. ✗ **DOAC vs VKA left to "individual patient factors"** (DOACs are preferred). No aspirin statement. CHA2DS2-VA not named. AF not stated as an assumption.

### Q6. SOAP note, 35M with sore throat. GPT-5.1: 1 · Qwen: 5

Reference: S/O/A/P; Centor/McIsaac 4; rapid antigen test; **no backup culture in adults**; penicillin V or amoxicillin for 10 days; allergy alternatives; consider EBV.

- **GPT-5.1** ✗ Refused as a "non-medical request".
- **Qwen** ✔ Real S/O/A/P note with "not documented" for missing vitals. McIsaac 4. No empirical antibiotics (IDSA). Penicillin or amoxicillin first-line, macrolides only for allergy. ✗ **"If RADT is negative, confirm with a throat culture"** for an adult. Sinusitis self-care advice (warm facial packs, head of bed raised). No dose or duration. McIsaac age points garbled (the total is still right). No EBV.

### Q7. (Arabic) Explain hypertension to a newly diagnosed patient. GPT-5.1: 1 · Qwen: 8

Reference: plain Arabic; what blood pressure is and why it matters without symptoms; lifestyle with concrete targets; take medication even when feeling well; home monitoring; when to seek urgent care.

- **GPT-5.1** ✗ Refused ("a medical explanation not suitable for clinical purposes"), in Arabic.
- **Qwen** ✔ Simple, warm Arabic. Adherence, home BP monitoring, DASH, weight, exercise, smoking, stress and sleep, and emergency symptoms. No citation numbers in the patient text; the physician section is cited. ✗ No numbers (salt target, exercise minutes, target BP, 180/120). No emergency phone number.

### Q8. SGLT2i in HFpEF. GPT-5.1: 9 · Qwen: 8

Reference: EMPEROR-Preserved and DELIVER; composite HR about 0.80; benefit driven by HF hospitalization; no mortality reduction; better KCCQ; empagliflozin 10 mg or dapagliflozin 10 mg; ESC 2023 Class I, AHA 2022 Class 2a.

- **GPT-5.1** ✔ HRs with confidence intervals. Mortality neutral. KCCQ and 6-minute walk. Renal outcomes, subgroups, the ESC 2023 update and a Class IIa position, plus safety. ✗ No doses. 10,500 characters, including a mechanisms section. Does not state ESC Class I.
- **Qwen** ✔ Mortality neutral. Both trials named. HR range. 10 mg doses. Benefit across renal function. Monitoring. ✗ No class of recommendation ("aligns with major society recommendations").

### Q9. Anaphylaxis after a bee sting. GPT-5.1: 9 · Qwen: 8

Reference: call for help; remove the trigger; supine with legs raised; IM epinephrine 0.5 mg (0.01 mg/kg) in the anterolateral thigh, repeat every 5 min; high-flow oxygen; airway assessment and early intubation; **IV crystalloid bolus now** (the patient is hypotensive); salbutamol; IV epinephrine infusion if refractory; glucagon if on β-blockers; observation; auto-injectors; allergist and venom immunotherapy.

- **GPT-5.1** ✔ Every reference step, in order, including immediate aggressive fluids and airway escalation up to cricothyrotomy. ✗ **Ranitidine** (withdrawn from the market) as the H2 option. No fluid volumes. About 9,000 characters is long for an emergency.
- **Qwen** ✔ IM epinephrine. Legs raised. Call for help and prepare for an advanced airway. Repeat every 5–15 min. Salbutamol. IV infusion for refractory cases. Glucagon (flagged as not in the sources). Observation, two auto-injectors and allergist referral. ✗ **Fluids only "if hypotension persists despite epinephrine"**. "Or deltoid". No oxygen. Panic attack and vasovagal syncope as padding differentials.

### Q10. 5 SMLE-style MCQs, nephrotic vs nephritic. GPT-5.1: 1 · Qwen: 8

Reference: five vignettes testing different points (proteinuria >3.5 g/day, hypoalbuminemia, lipiduria vs hematuria, RBC casts, hypertension; typical causes by age; complications).

- **GPT-5.1** ✗ Refused ("can't assist with creating MCQs").
- **Qwen** ✔ Five vignettes with options A–E, answers and explanations, each testing a different point: minimal change disease, edema mechanism, thrombosis risk, diabetes as the commonest secondary cause, and oval fat bodies vs PSGN with low C3. ✗ Question 1 gives the threshold as >3.0 g/day (3.5 is standard).

---

## 6. The Qwen configuration in this run

Compared with the old graph that the GPT run used:

- **One planning call** replaces analyzer, contextualize and evidence assessment. Code guards: clarify only for a consult about a specific patient with something missing; search queries in non-Latin scripts dropped; reply language detected in code.
- **No evidence assessor.** The answer step states what the sources did not cover and still answers the rest. This alone removed every unnecessary clarification.
- **Answer layout per task, built in code** (consult, calculation, SOAP note, patient explanation, teaching), with localized headings. The Sources list is built from the citations actually used.
- **Three prompt edits for calculations** (in `src/config/constants.py`), which fixed Q4. Without them, Q4 scored 4–5 in every recent run, because the model stated a wrong conclusion first and then corrected itself in the visible text:
  1. `PLAN_PROMPT`: the `calculation` task lists examples (ABG / acid-base interpretation, anion gap, CrCl, corrected sodium or calcium, CHA2DS2-VASc, Wells, CURB-65).
  2. `ANSWER_PROMPT`: never show drafts, corrections or a revised second version; work through the arithmetic before stating the conclusion.
  3. Calculation layout: the Working section asks for the full method (for an ABG, including the delta ratio).

---

## 7. Remaining issues in the Qwen system

| # | Issue | Questions | Root cause |
|---|---|---|---|
| R1 | Outdated recommendations copied from old or non-guideline sources | Q1 (test-of-cure culture), Q6 (adult backup culture), Q9 (fluids delayed) | Sources are ranked by Tavily relevance only; the `nih.gov` whitelist admits all of PubMed/PMC (case reports, audits, single-center studies) |
| R2 | Current guidelines missing from the source pool | Q5 (CHA2DS2-VA), Q6 (IDSA pharyngitis guideline) | Full texts of IDSA guidelines (*Clin Infect Dis*) and ESC guidelines (*Eur Heart J*) are hosted on `academic.oup.com`, which is not in `SEARCH_ALLOWED_DOMAINS` |
| R3 | The answer step cannot tell old sources from new | Q1, Q2, Q6 | `render_context` passes title, URL and content, but no year or source type, so "follow the most recent guideline" cannot be applied |
| R4 | Stale years in search queries | Q2, Q5, Q6, Q8, Q9 ("2024" in October 2026) | The plan step does not know today's date |
| R5 | Queries for the output form instead of the clinical content | Q6 ("SOAP note structure"), Q10 ("high yield MCQs") | The prompt rule is not followed reliably |
| R6 | Less complete than GPT-5.1 on safety-critical details | Q5, Q9 | Model and sources together; not separable with this data |

---

## 8. Recommendations

Ordered by expected value. All are small changes; none adds a model call.

1. **Make evaluation cheap and repeatable first.** Run-to-run variance is about ±5 points and comes mostly from search results (at temperature 0, repeated answers on the same sources were identical for 8 of 10 questions), so smaller improvements cannot be seen today.
   - Save each question's sources once and replay them, so prompt changes are judged against the same evidence in one run.
   - Score answers automatically: must-contain facts (reuse the patterns in `scripts/retrieval_eval.py`) and must-not-say patterns (adult backup culture, repeat urine culture, "or deltoid", "contraindicated if eGFR <30").
   - Add cases this set does not cover: one that should be clarified, one that should be refused, a two-turn follow-up and an Arabic patient case.
2. **Improve the source pool (R1, R2).** Add `academic.oup.com` to `SEARCH_ALLOWED_DOMAINS`, and check `scripts/retrieval_eval.py` before and after. In `dedupe()`, boost guideline bodies and guideline titles, demote case reports, and demote sources older than about 10 years. Reserve the first source slots for the guideline query.
3. **Show each source's year and type to the answer step (R3),** e.g. `[3] (2005, review) Title`, so the existing "most recent guideline wins" rule can actually be applied.
4. **Fix queries in code (R4, R5).** Put today's date in `PLAN_PROMPT` (an earlier run showed it retrieves the ADA 2026 and AHA 2025 documents). In `_clean_queries`, remove output-form words (SOAP note, MCQ, patient education, "in Arabic").
5. **Measure the model ceiling once.** Run the same 10 questions with GPT-5.1 as `ANSWER_MODEL` on the current pipeline (an `.env` change only). This shows how much of R6 is the model and whether a larger self-hosted model is worth evaluating.
6. **Not a priority now:** thinking mode, a larger Qwen model, or a verification pass. The remaining errors are faithful copies of weak sources. A larger model would reproduce them, and a verification pass would confirm them, because the sources do say those things.

Earlier runs (the old graph on Qwen and the intermediate runs of the new graph) are in the git history of this file.
