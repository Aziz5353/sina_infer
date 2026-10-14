# Sina evaluation: GPT-5.1 for both planning and answering

Evaluated on 2026-10-13, using the same metrics and the same 87-fact reference checklist as `evaluation_gpt-5.1_v2_vs_qwen3.5-35b-a3b_v3.md`. This report looks at this run only. Section 7 adds a short comparison with the earlier GPT run that used gpt-4o-mini as the planner, because the planner is the only thing that changed.

---

## 1. Run

| | |
|---|---|
| Data file | `data/conversations_gpt-5.1_v2.csv`, last 10 rows (rows 12–21) |
| Date | 2026-10-13, 09:42–09:48 UTC |
| Plan model | gpt-5.1 |
| Answer model | gpt-5.1 |
| Graph | plan → retrieve → answer, 2 model calls per turn |
| Code | `HEAD` (340147e) |
| Reference | `data/eval_simple.csv` (Q1 = MED-010, Q2 = MED-001, …, Q9 = MED-008, Q10 = MED-009) |

---

## 2. Metrics

- **Correctness:** the percentage of key facts from the reference answer that the answer covers. Each fact scores 1 if covered, 0.5 if partly covered and 0 if missing; there are 87 facts in total, listed in the appendix. Wrong or outdated statements are listed separately.
- **Relevancy:** a 0–5 score for whether the answer covers every part of the question, in the form and language asked, without padding.
- **Faithfulness:** a 0–5 score built from five checks:
  - citation validity;
  - the share of claims that carry a citation;
  - how often a sentence stacks 3 or more citations;
  - a check of 12 cited claims against the full text of the source;
  - source type.

  This time it also checks faithfulness to the doctor's input: no invented case details.
- **Operational:** routing, task classification, red flags, language, latency and length.

The CSV logs each source's title and URL but not its text. The answer step saw only a snippet plus an excerpt of at most 3,000 characters per source, so "supported" means the cited document contains the claim.

---

## 3. Results

### Summary

| Metric | Result |
|---|---|
| **Correctness** (mean of per-question %) | **78.0%** |
| Correctness, all key facts pooled | 78.2% (68 / 87) |
| Questions at ≥ 75% correctness | 8 / 10 |
| Wrong or outdated statements | 4 (section 6) |
| **Relevancy** (0–5) | **4.2** |
| **Faithfulness** (0–5) | **4.1** |
| Citation validity (`[n]` points to a retrieved source) | 100% (531 / 531) |
| Claim lines carrying a citation (automatic) | 67% |
| Clinical recommendations without a citation (manual count) | 9 (5 of them labelled by the model as "not in the sources") |
| Cited lines stacking ≥3 citations | 37% |
| Spot-checked claims found in the cited source | 12 / 12 (one of them outdated) |
| Invented case details | 1 (Q6) |
| Retrieved sources that were cited | 89% (78 / 88) |
| Case reports cited for general claims | 4 (Q4 [5], Q9 [2][3], Q10 [4]) |
| Questions answered / wrong refusals | 10 / 10 · 0 |
| Task classified correctly | 10 / 10 |
| Red flags extracted (Q1 sepsis, Q9 shock) | 2 / 2 |
| Replied in the doctor's language | 10 / 10 |
| Latency, mean (median, max) | 35.9 s (33.6 s, 54.3 s) |
| Answer length, mean | 8,223 characters |

### Per question

| # | Question | Correctness | Relevancy | Faithfulness | Latency | Length |
|---|---|---|---|---|---|---|
| 1 | Pyelonephritis case | 75% | 4 | 4 | 33.3 s | 8,753 |
| 2 | T2DM + ASCVD first-line | **44%** | 4 | 4 | 33.9 s | 7,812 |
| 3 | Amoxicillin for pediatric AOM + renal (Arabic) | 78% | 4 | 5 | 54.3 s | 9,433 |
| 4 | ABG interpretation | **92%** | 5 | 5 | 21.0 s | 4,238 |
| 5 | CHA2DS2-VASc + anticoagulation | 71% | 5 | 4 | 17.9 s | 3,972 |
| 6 | SOAP note, sore throat | 81% | 4 | **2** | 28.7 s | 6,398 |
| 7 | Hypertension for a patient (Arabic) | **91%** | 4 | 4 | 52.5 s | 8,116 |
| 8 | SGLT2i in HFpEF | 78% | 4 | 5 | 31.9 s | 9,590 |
| 9 | Anaphylaxis management | **90%** | 4 | 4 | 43.9 s | 9,990 |
| 10 | SMLE MCQs | 80% | 4 | 4 | 42.1 s | 13,932 |

---

## 4. What the numbers say

1. **The planner side now works.** Every question was answered and every task was classified correctly. The ABG went to `calculation` and got the full method, including Winter's formula, the delta ratio and a mixed-disorder check. Red flags were extracted for sepsis (Q1) and anaphylactic shock (Q9), so both answers open with an urgent-action section.
2. **Correctness is good (78%), with one clear weak spot.** Q2 scores 44% because of how the planner rewrote it:
   - The planner turned "What is the current first-line management…" into "what is the current evidence-based first-line **pharmacologic** management strategy (**drug class and approach**)".
   - The answer step only sees this rewrite (`answer.py:49`, `render_context`).
   - The result covers the drug question well: GLP-1 RA or SGLT2i regardless of metformin and HbA1c, early combination therapy, and the agents named. But it drops lifestyle, statin, aspirin, the BP target and kidney checks, which are half the reference answer.
3. **The planner's rewrites also expand questions, which makes answers long and slow.**
   - **Q8:** the rewrite lists six sub-topics.
   - **Q9:** adds "drug choices, doses, routes and sequence".
   - **Q3:** adds "age ranges, weight, route, duration, and eGFR/CrCl adjustment".
   - **Q7:** adds "possible causes".

   The answers follow these briefs. The mean length is 8,223 characters, with Q10 at 13,932 and Q9 at 9,990. Latency averages 35.9 s and reaches 54 s on Q3 and Q7.
4. **Faithfulness to the sources is high.**
   - Every citation number is valid.
   - All 12 spot-checked claims are in their sources, often word for word: the amoxicillin label's "no dosing recommendations for pediatric patients with impaired renal function", the KCCQ gains of +1.03/+1.24/+1.50, and the EF-band HR of 0.83 (0.71–0.98).
   - When a source lacks something, the model says so instead of inventing it.
   - Citation stacking is moderate at 37%. It is worst in Q2, where 18 of 24 cited lines carry 3 or more sources.
5. **Faithfulness drops in two places.**
   - **Q6 invents a detail in the medical record.** The Subjective section says "He reports painful swallowing and persistent throat pain", which the doctor never stated.
   - **Q6 retrieval failed.** The planner returned no usable search queries, so `plan.py:128–131` fell back to sending the whole 280-character instruction ("Write a full SOAP note for…") as one search. That returned only 3 sources, two of them from 2001 and 2006. As a result the plan names no antibiotic at all ("the sources do not provide specific adult drug choices").
6. **Outdated advice copied from old sources is still present.**
   - **Q9** offers ranitidine as the H2 blocker, taken from a 2010 source; ranitidine was withdrawn in 2020.
   - **Q3** recommends 5–7 days of amoxicillin for all ages, based on a Finnish adherence study. The AAP recommends 10 days for children under 2.
7. **Gaps that recur across runs:**
   - No pregnancy test for the 28-year-old woman (Q1). The planner left `pregnancy_status` empty but did not list it as missing.
   - No amoxicillin-clavulanate indication (Q3).
   - No ACC/AHA Class 2a (Q8).
   - No renal-based DOAC dosing (Q5).

---

## 5. Faithfulness detail

### Spot-check against the full source text

| # | Q | Claim | Source | Verdict |
|---|---|---|---|---|
| 1 | Q1 | Urine cultures positive in ≈90% | [4][6][8] | Supported in substance: AFP 2011 [8] says ">95%" have ≥10⁵ CFU; the 90% figure was not in the checked source |
| 2 | Q3 | "No dosing recommendations for pediatric patients with impaired renal function" | DailyMed label [2] | Supported (verbatim) |
| 3 | Q3 | Infants ≤3 months: maximum 30 mg/kg/day, every 12 h | DailyMed label [2] | Supported |
| 4 | Q3 | Most clinicians cap high-dose amoxicillin at 4,000 mg/day (2,000 mg/dose) | Review [3] | Supported (verbatim) |
| 5 | Q4 | Expected PaCO2 = 1.5 × HCO3 + 8 ± 2 | MSD Manual [1] | Supported |
| 6 | Q5 | DOAC preferred over VKA (Class I); antiplatelet is not a substitute | Review [9] | Supported |
| 7 | Q8 | KCCQ-CSS +1.03 / +1.24 / +1.50 at 12 / 32 / 52 weeks | EMPEROR-Preserved QoL [5] | Supported (exact) |
| 8 | Q8 | LVEF ≥50%: HR 0.83 (0.71–0.98), P = 0.024 | Pre-specified analysis [6] | Supported (exact) |
| 9 | Q9 | Initial fluid bolus 20 mL/kg | 2020 guideline [5] | Supported |
| 10 | Q9 | IM 0.3–0.5 mg every 5–15 min; infusion 1 mg in 250 mL at 0.1 µg/kg/min; IV bolus 0.05–0.1 mg | Merck Manual [10] | Supported |
| 11 | Q9 | Diphenhydramine + ranitidine is better than diphenhydramine alone | 2010 paper [7] | Supported, but **outdated** (ranitidine withdrawn) |
| 12 | Q9 | Glucocorticoids may reduce biphasic reactions | 2020 guideline [5] | Supported (the source rates the evidence "very uncertain"; Merck [10] says "no proven role") |

### Uncited clinical recommendations (9)

- **Q1:** reassess within 24–48 h.
- **Q6:** analgesia, hydration, gargles, contagiousness and work exclusion, follow-up at 48–72 h. Four of these five are labelled "not specified in sources" or "standard care".
- **Q9:** large-bore IV; observation for biphasic reactions (labelled "exact times not in sources").
- **Q10:** the prerenal-AKI distractor explanation.

Most other uncited lines are case restatements, arithmetic or headings.

---

## 6. Wrong or outdated statements

| Q | Statement | Problem |
|---|---|---|
| Q3 | "Use 5–7 days" as the practical duration for all ages | The AAP recommends 10 days under age 2 (7 days at 2–5 years, 5–7 days at 6 and over); this under-treats infants |
| Q6 | "He reports painful swallowing and persistent throat pain" | Not in the doctor's input; invented content in a medical record |
| Q9 | "Diphenhydramine plus ranitidine" | Ranitidine was withdrawn from the market in 2020 |
| Q10 | Nephrotic proteinuria ">3 g/24 h" (repeated in 4 explanations) | 3.5 g/day is the standard threshold for an exam answer key |

A minor point: Q9 lists corticosteroids as a step to "give", where current AAAAI guidance treats them as not routine. The cited source supports it, so it is scored as a partial match, not an error.

---

## 7. Change from the run with gpt-4o-mini as the planner

| Metric | gpt-4o-mini planner | gpt-5.1 planner |
|---|---|---|
| Correctness (mean of per-question %) | 71.0% | **78.0%** |
| Key facts, Q1–Q9 only | 64.5 / 82 | 64 / 82 |
| Questions answered | 9 / 10 | **10 / 10** |
| Task classified correctly | 9 / 10 | **10 / 10** |
| Red flags extracted | 0 / 2 | **2 / 2** |
| Relevancy | 3.9 | **4.2** |
| Faithfulness (answered turns) | 4.2 | 4.1 |
| Cited lines stacking ≥3 citations | 44% | 37% |
| Mean latency, answered turns | **20.2 s** | 35.9 s |
| Mean answer length | **5,678** | 8,223 |

**The gain comes from Q10, which is now answered, plus Q4, which is now treated as a calculation.** Across Q1–Q9 the total is flat (64.5 vs 64). Q1, Q3, Q4 and Q7 went up; Q2, Q5, Q6 and Q9 went down. Two of the drops have a clear cause: the Q2 rewrite narrowed the question, and the Q6 search fell back to the raw instruction. The rest is within the run-to-run variance seen in earlier evaluations (about ±5 points), because each run retrieves different sources.

---

## 8. Recommendations

1. **Keep the doctor's scope in the answer step.** Pass the original message to `render_context` alongside the rewrite. Add a line to `PLAN_PROMPT` saying `standalone_question` must not add or drop sub-questions. This targets the Q2 narrowing and most of the extra length and latency.
2. **Fix the empty-query fallback** (`plan.py:128–131`). Sending the whole request to Tavily returns few, old sources. Build the fallback from the case instead (e.g. chief complaint + "diagnosis and management guideline"), or make queries required in `PlanOutput` even when the route is later overridden.
3. **Cap answer length per task in `ANSWER_PROMPT`.** For example: a consult answer of about 600 words, MCQ explanations of 2–3 lines. Emergencies (Q9) need the steps first and the background last, if at all.
4. **Add a pregnancy-status guard in code.** If `sex` is female, age is 12–50 and `pregnancy_status` is empty, add it to `missing_critical_info`. Every run so far has missed the pregnancy test in Q1.
5. **Improve the source pool** (open since the first evaluation): demote case reports and sources older than about 10 years, and boost guideline documents. This targets ranitidine, the Finnish duration and the case reports cited in Q9 and Q10.

---

## 9. Limitations

- 10 questions, one run. Search results change between runs.
- One rater (Claude) scored the answers against the reference answers, without blinding.
- 12 of about 530 citations were checked against the source. Three cited documents could not be checked (publisher access): the ADA/EASD 2022 full text, PMC6188440 and Medscape pages.

---

## Appendix: key-fact scoring

✔ = 1, ½ = 0.5, ✗ = 0.

| Q | Key fact | Score |
|---|---|---|
| **Q1** (10.5 / 14) | Most likely: acute pyelonephritis | ✔ |
| | Assess for SIRS / sepsis | ✔ |
| | Obstructed infected kidney | ✔ |
| | Renal or perinephric abscess | ½ (imaging only) |
| | Cystitis does not explain fever and flank pain | ✔ |
| | Gynecologic causes (ectopic, PID/TOA, torsion) | ½ (PID only) |
| | Appendicitis, cholecystitis, uncomplicated stone | ½ |
| | Pregnancy test | ✗ |
| | Urinalysis + urine culture | ✔ |
| | Blood cultures | ✔ |
| | CBC, creatinine, lactate | ½ (no lactate) |
| | Imaging if obstruction/abscess or no improvement at 48–72 h | ✔ |
| | IV antibiotics and fluids | ½ (no fluids) |
| | Admit if septic, pregnant or unable to take oral medication | ✔ |
| **Q2** (3.5 / 8) | Lifestyle and education | ✗ |
| | GLP-1 RA or SGLT2i regardless of HbA1c and metformin | ✔ |
| | Agents named | ✔ |
| | ≥1.5% above target → combination therapy | ✔ |
| | High-intensity statin | ✗ |
| | Aspirin | ✗ |
| | BP <130/80 | ✗ |
| | eGFR and urine albumin | ½ (eGFR only) |
| **Q3** (7 / 9) | 80–90 mg/kg/day | ✔ |
| | 2 doses, every 12 h | ✔ |
| | Not above the adult maximum | ✔ (4 g/day) |
| | Duration by age (10 / 7 / 5–7 days) | ½ (5–7 days for all) |
| | Amoxicillin-clavulanate indication | ✗ |
| | Adjust only when GFR <30 | ✔ |
| | Every 12 h at GFR 10–30, every 24 h below 10 | ½ ("q12–24h", no thresholds) |
| | No adjustment in mild or moderate impairment | ✔ |
| | Drug reference or pharmacist | ✔ |
| **Q4** (5.5 / 6) | HAGMA with appropriate compensation | ✔ |
| | Metabolic acidosis | ✔ |
| | AG 23, high | ✔ |
| | Winter's 27.5 ± 2 | ✔ |
| | Delta ratio 1, no additional disorder | ✔ |
| | Lactate, ketones, creatinine, osmolar gap, salicylates | ½ (no osmolar gap) |
| **Q5** (5 / 7) | Score 4 with components | ✔ |
| | Assumes AF | ½ (implied, not stated as an assumption) |
| | OAC recommended | ✔ |
| | DOAC over warfarin | ✔ |
| | Dose by renal function | ✗ |
| | Aspirin is not an alternative | ✔ |
| | Bleeding risk used to fix modifiable factors, not to withhold OAC | ½ |
| **Q6** (6.5 / 8) | Correct S/O sections | ✔ (but with an invented symptom; see section 6) |
| | Likely group A strep | ✔ |
| | Centor 4 | ✔ |
| | Differential: viral, mononucleosis | ½ (no mononucleosis) |
| | Rapid strep test ± culture | ✔ |
| | Penicillin V or amoxicillin, dose, 10 days | ✗ (no drug named) |
| | Paracetamol/NSAID and fluids | ✔ |
| | Return precautions | ✔ |
| **Q7** (10 / 11) | What blood pressure is | ✔ |
| | About 140/90 on repeated readings | ✗ |
| | Often silent; harms heart, brain, kidneys, eyes | ✔ |
| | Controllable | ✔ |
| | Less salt, with local examples | ✔ |
| | More vegetables and fruit | ✔ |
| | Walk 30 min most days | ✔ (20–30 min, 5 days a week) |
| | Lose weight; stop smoking and shisha | ✔ |
| | Take medication daily even when feeling well; don't stop it | ✔ |
| | Home BP readings recorded; regular follow-up | ✔ |
| | Emergency symptoms | ✔ |
| **Q8** (7 / 9) | EMPEROR-Preserved (HR 0.79) | ✔ (21% reduction) |
| | DELIVER (HR 0.82) | ½ (named, no result) |
| | Composite reduced, driven by hospitalizations | ✔ |
| | No clear mortality reduction | ✔ |
| | Modest symptom / QoL benefit | ✔ |
| | Benefit with or without diabetes | ✔ |
| | ESC 2023 Class I | ✔ |
| | ACC/AHA 2022 Class 2a | ✗ |
| | Genital infections, volume depletion, euglycemic DKA | ½ (volume depletion only) |
| **Q9** (9 / 10) | Call for help | ✔ |
| | IM epinephrine 0.5 mg, thigh, immediately | ✔ |
| | Repeat every 5 min | ✔ |
| | Flat with legs raised | ✔ |
| | High-flow oxygen; airway, prepare to intubate | ✔ |
| | IV access + fluid bolus now | ✔ |
| | Salbutamol | ✔ |
| | IV epinephrine infusion + ICU | ✔ |
| | Antihistamines after epinephrine; steroids not routine | ½ (steroids given routinely) |
| | Observation; 2 auto-injectors; allergy referral | ½ (one auto-injector) |
| **Q10** (4 / 5) | 5 questions | ✔ |
| | Clinical vignettes | ✔ |
| | 4 options each | ½ (5 options, as Sina's layout asks) |
| | Answer + explanation | ✔ |
| | Tests distinguishing features (MCD, low C3, RBC casts vs fat bodies, thrombosis) | ½ (no complications; 3 questions test the same classification) |
