# Sina evaluation: GPT-5.1 vs Qwen3.5-35B-A3B on the plan → retrieve → answer graph

Evaluated on 2026-10-13. Both systems now run the same graph and code, so this is the first comparison where only the models differ.

---

## 1. Runs compared

| | **GPT run** | **Qwen run** |
|---|---|---|
| Data file | `data/conversations_gpt-5.1_v2.csv`, last 10 rows (rows 2–11) | `data/conversations_qwen3.5-35b-a3b_v3.csv`, last 10 rows (rows 31–40) |
| Date | 2026-10-13 | 2026-10-12 |
| Plan model | **gpt-4o-mini** | Qwen3.5-35B-A3B-FP8 (vLLM, thinking off) |
| Answer model | **gpt-5.1** | Qwen3.5-35B-A3B-FP8 (vLLM, thinking off) |
| Graph | plan → retrieve → answer | plan → retrieve → answer |
| Code | `HEAD` (7156596) + the uncommitted `DISABLE_THINKING` switch | 0538226 + the calculation prompt edits, which is the same as `src/` at `HEAD` |
| Model calls per turn | 2 | 2 |

Row 1 of the GPT file is left out. It failed with `BadRequestError`, because OpenAI rejects the `chat_template_kwargs` argument. The uncommitted `DISABLE_THINKING` change fixes this.

The reference answers come from `data/eval_simple.csv`. The IDs map to the question numbers used here as follows: Q1 = MED-010, Q2 = MED-001, Q3 = MED-002, Q4 = MED-003, Q5 = MED-004, Q6 = MED-005, Q7 = MED-006, Q8 = MED-007, Q9 = MED-008, Q10 = MED-009.

---

## 2. Metrics

| Metric | How it is measured |
|---|---|
| **Correctness** | Each reference answer in `eval_simple.csv` is split into its key facts (87 in total, listed in the appendix). Each fact scores 1 if the answer contains it, 0.5 if partly, and 0 if missing. The score is the percentage of key facts covered. Wrong or outdated statements are listed separately. |
| **Relevancy** | Scored 0–5: does the answer address every part of the question, in the form and language asked, without padding or off-topic content? 5 = all of it with no padding; 4 = complete, with minor padding; 3 = a notable part missing or clearly off-topic content; 0 = refused. |
| **Faithfulness** | Measured from the citations: (a) **validity**, i.e. every `[n]` points to a retrieved source; (b) **coverage**, i.e. clinical claims carry a citation; (c) **attribution precision**, i.e. how often one sentence stacks 3 or more citations; (d) **support**, i.e. 10 key claims checked against the full text of the cited source; (e) **source quality**, i.e. the share of cited sources that are guidelines or consensus documents. These are combined into a 0–5 score per answer. |
| Operational | Routing, task classification, red-flag extraction, reply language, latency, answer length. |

Source text is not logged in the CSV (only title, URL and score), so support was checked by fetching the cited documents. The answer step only sees a snippet plus an excerpt of at most 3,000 characters. "Supported by the document" therefore means a reader who clicks the citation finds the claim there. It does not prove the excerpt contained it.

---

## 3. Results

### Summary

| Metric | GPT-5.1 + gpt-4o-mini | Qwen3.5-35B |
|---|---|---|
| **Correctness**, all 10 questions (mean of per-question %) | **71.0%** | 64.0% |
| Correctness, all key facts pooled (out of 87) | **74.1%** (64.5) | 63.2% (55) |
| **Correctness, the 9 questions both answered** | **78.7%** | 61.6% |
| Head-to-head wins on correctness | **7** (Q2, Q3, Q5, Q6, Q7, Q8, Q9) | 3 (Q1, Q4, Q10) |
| Wrong or outdated clinical statements | **2** | 5 |
| **Relevancy**, all 10 (0–5) | 3.9 | **4.1** |
| Relevancy, 9 both answered | **4.3** | 4.0 |
| **Faithfulness**, answered turns (0–5) | **4.2** | 3.8 |
| Citation validity (`[n]` points to a real source) | 100% (405/405) | 100% (211/211) |
| Lines with a claim that carry a citation (automatic) | 69% | **77%** |
| Clinical recommendations with no citation (manual count) | **5** | 10 |
| Cited lines stacking ≥3 citations | 44% | **14%** |
| Spot-checked claims supported by the cited document | 6/6 | 3/3 (1 not checkable) |
| Cited sources that are guidelines or consensus documents | **~34%** | ~22% |
| Questions answered | 9/10 | **10/10** |
| Wrong refusals | 1 (Q10) | **0** |
| Task classified correctly | 9/10 (Q4 → consult) | **10/10** |
| Red flags extracted (Q1 sepsis, Q9 shock) | 0/2 | **2/2** |
| Replied in the doctor's language | 10/10 | 10/10 |
| Mean latency, answered turns | 20.2 s | **15.8 s** |
| Mean answer length, answered turns | 5,678 chars | 4,106 chars |

### Per question

| # | Question | Correctness GPT | Correctness Qwen | Relevancy GPT | Relevancy Qwen | Faithful. GPT | Faithful. Qwen |
|---|---|---|---|---|---|---|---|
| 1 | Pyelonephritis case | 64% | **71%** | 4 | 4 | 4 | 4 |
| 2 | T2DM + ASCVD first-line | **69%** | 25% | **5** | 4 | **4** | 2 |
| 3 | Amoxicillin for pediatric AOM + renal (Arabic) | **61%** | 50% | 4 | 4 | 4 | 4 |
| 4 | ABG interpretation | 58% | **100%** | 4 | **5** | 4 | **5** |
| 5 | CHA2DS2-VASc + anticoagulation | **100%** | 43% | **5** | 4 | **5** | 3 |
| 6 | SOAP note, sore throat | **94%** | 69% | **4** | 3 | **4** | 3 |
| 7 | Hypertension for a patient (Arabic) | **86%** | 68% | **5** | 4 | **5** | 4 |
| 8 | SGLT2i in HFpEF | **78%** | 39% | 4 | **5** | 4 | **5** |
| 9 | Anaphylaxis management | **100%** | 85% | **4** | 3 | **4** | 3 |
| 10 | SMLE MCQs | 0% (refused) | **90%** | 0 | **5** | n/a | 5 |

---

## 4. What the numbers say

1. **When both systems answer, GPT-5.1 is clearly more correct**: 78.7% vs 61.6% of reference facts, winning 7 of 9 questions. The gap is largest on standard-of-care recommendations. Qwen leaves out DOAC preference, "no aspirin" and renal dosing for AF (Q5); combination therapy, statin, BP and kidney checks for T2DM with ASCVD (Q2); and guideline classes, the diabetes subgroup and symptom benefit for HFpEF (Q8).
2. **GPT's three losses come from the gpt-4o-mini planner, not GPT-5.1.**
   - **Q10:** the planner refused MCQs ("I can only assist with clinical questions"), so GPT-5.1 never saw the question.
   - **Q4:** the planner labelled the ABG as `consult` instead of `calculation`, even though `PLAN_PROMPT` lists ABG under calculation. The answer therefore had no Working layout. The planner's generic queries ("current guidelines for interpreting ABG results") also retrieved pages that name Winter's formula without stating it. GPT-5.1 stayed faithful, declined to compute it and skipped the delta ratio. The Qwen planner searched for "anion gap" and "delta gap", got StatPearls and ATS pages that contain the formulas, and scored 100%.
   - **Q1 and Q9:** the planner extracted no red flags (sepsis, anaphylactic shock), so neither answer had a "Red flags / urgent action" section. The Qwen planner flagged both, and also listed pregnancy status as missing in Q1.
   - **Q6:** the query "SOAP note format" spent 5 of 10 source slots on papers about SOAP documentation.
3. **Faithfulness is high in both systems; they differ in how claims are attributed.** No invented citations: every `[n]` is valid and every spot-checked claim was found in its source (section 5).
   - **GPT-5.1** cites more, from better sources (34% vs 22% guideline documents), but stacks citations: 44% of cited lines carry 3 or more, up to six (`[1][3][5][7][8][10]`), so the reader cannot tell which source says what. It is also strict about grounding. When the sources lack a number, it says so and leaves it out: no antibiotic regimen in Q1, no Winter's formula in Q4, no penicillin dose in Q6.
   - **Qwen** cites more precisely (14% stacked) but leaves about twice as many clinical recommendations uncited (admission for 4–6 h, ECG, ICU care, the "what would change" bullets). In Q2 it says outright that contraindications come from "standard clinical knowledge". Also in Q2, it cited a hospitalization-continuation study and a cohort study while ignoring the ADA Standards of Care sections it had retrieved ([6], [8]). Its source [4] there is a PubMed author-search URL, not an article.
4. **Both copy outdated advice from old sources ("faithful but outdated").** GPT-5.1 says ESC guidelines lag on SGLT2i in HFpEF, quoting a 2023 review of ESC 2021; ESC 2023 already gives Class I. Qwen recommends a repeat urine culture after treatment (AFP 2005) and holds fluids until hypotension persists after epinephrine (AFP 2020 key recommendation), in a patient who is already hypotensive. This is the source-pool issue (R1–R3) from the previous evaluation, and it is still open.
5. **Relevancy is close.** GPT is 4.3 vs 4.0 on the 9 shared questions, while Qwen leads 4.1 vs 3.9 over all 10 because of the refusal. GPT pads with length: 38% longer answers, with a case-control LA-strain study and a NICE appraisal in Q8 and ten "not documented" lines in the SOAP note. Qwen pads with off-topic content: sinusitis self-care in a pharyngitis SOAP note (Q6), and panic attack and vasovagal syncope as differentials in a step-by-step anaphylaxis request (Q9).
6. **Qwen is faster** (15.8 s vs 20.2 s on answered turns) and runs on its own hardware. Both use 2 model calls per turn.
7. **Both miss the same items:** a pregnancy test for the 28-year-old woman (Q1); the amoxicillin-clavulanate indication and the renal dosing intervals for children (Q3); ESC 2023 Class I for SGLT2i in HFpEF (Q8); antibiotic doses in the SOAP note (Q6).

---

## 5. Faithfulness detail

### Spot-check of cited claims against the full source text

| # | Answer | Claim | Cited source | Verdict |
|---|---|---|---|---|
| 1 | GPT Q1 | Flank pain is "nearly universal" in acute pyelonephritis | AFP 2011 [9] | Supported (verbatim) |
| 2 | GPT Q1 | 15–30% have positive blood cultures | AFP 2011 [9] | Supported ("15 to 30 percent … bacteremic") |
| 3 | GPT Q4 | The sources do not give Winter's numeric range | MSD Manual, metabolic acidosis [3] | Supported: the page names the formula but does not state it |
| 4 | GPT Q8 | HF hospitalization HR 0.74; all-cause death 0.97; CV death 0.96 | Meta-analysis [1] | Supported (exact figures) |
| 5 | GPT Q8 | AHA 2022 Class 2a; ESC guidelines lag | Review, 2023 [4] | Supported, but **outdated** (the review refers to ESC 2021) |
| 6 | GPT Q9 | 20 mL/kg crystalloid bolus for cardiovascular instability | WAO 2020 [7] | Supported |
| 7 | Qwen Q1 | FQ resistance >10% → add a dose from another class | CDC EID 2016 [5] | Supported (the source names ceftriaxone or gentamicin) |
| 8 | Qwen Q9 | 1–2 L saline if hypotension persists after epinephrine | AFP 2020 [10] | Supported (Key Recommendations), but against the reference for a patient who is already hypotensive |
| 9 | Qwen Q2 | GLP-1 RAs with CV benefit: liraglutide, dulaglutide, injectable semaglutide | Hospitalization study [1] | Supported second-hand (from the study's background section); "the only classes" overstates it |
| 10 | Qwen Q3 | Adjust the dose at GFR 10–30 | NICE CKS [6] | Not checkable (HTTP 403) |

### Uncited clinical recommendations (manual count)

- **GPT-5.1 (5):** Q3 check GFR before high-dose treatment; Q5 check renal and hepatic function for DOAC dosing; Q8 monitoring and cautions (2, marked as "general class effects"); Q9 inhaled β2-agonist.
- **Qwen (10):** Q1 the three "what would change the assessment" bullets; Q2 contraindications ("standard clinical knowledge applies"); Q6 re-evaluate at 48–72 h; Q9 continuous monitoring, ECG, admit for 4–6 h, glucagon and pregnancy (the last two marked "not covered in sources").

Most lines the automatic coverage counts as uncited are case restatements, arithmetic or headings. That is why the manual count above is the better measure of uncited claims.

---

## 6. Correctness detail: wrong or outdated statements

| Model | Q | Statement | Why it is wrong |
|---|---|---|---|
| GPT-5.1 | Q3 | Don't exceed the adult maximum "(e.g. ≥1500 mg/day)" | 1,500 mg/day is a standard adult dose, not the maximum; capping a heavy child there under-doses high-dose amoxicillin |
| GPT-5.1 | Q8 | ESC guidelines "are expected to align in future iterations" | The ESC 2023 focused update already gives Class I |
| Qwen | Q1 | Repeat urine culture 1–2 weeks after treatment | Not recommended for non-pregnant women (from an AFP 2005 source) |
| Qwen | Q6 | McIsaac age rule "0 for age 3–14, 1 for 15–44"; sinusitis self-care advice | Garbled rule (the total is still right); advice for a different condition |
| Qwen | Q9 | Fluids only "if hypotension persists despite epinephrine"; IM "or deltoid" | The patient is already hypotensive, so a bolus is due now; the thigh is the recommended site |
| Qwen | Q10 | Nephrotic proteinuria ">3.0 g/24 hours" | 3.5 g/day is standard; its own Q3 uses 3.5 |
| Qwen | Q3 | "The sources give no thresholds", then "adjust at GFR 10–30" | Contradicts itself |

---

## 7. Recommendations

1. **Swap the planner before judging GPT-5.1 further.** Every GPT loss traces to gpt-4o-mini (refusal, wrong task, no red flags, generic queries). Running Qwen or GPT-5.1 as `PLAN_MODEL` with GPT-5.1 as `ANSWER_MODEL` is an `.env` change. It shows the real ceiling of the answer model, and should recover Q4 and Q10.
2. **For the self-hosted Qwen target, the gap is completeness on standard-of-care points, not grounding.** The fix is still the source pool from the previous evaluation: boost guideline sources in `dedupe()` and show each source's year and type. In Q2, the ADA Standards were retrieved but ranked 6th and 8th behind cohort studies, and Qwen cited the cohort studies.
3. **Ask for one source per claim.** Add a line to `ANSWER_PROMPT`: cite the one or two sources that actually state the claim, not every related source. This targets GPT-5.1's stacking without loosening grounding.
4. **Make this scoring automatic.** The key-fact checklist in the appendix can become must-contain patterns, with the errors in section 6 as must-not-say patterns. A rerun then takes minutes, and run-to-run variance (about ±5 points in the previous evaluation) becomes visible.

---

## 8. Limitations

- 10 questions, one run per system. Search results change between runs, and the two runs retrieved different sources for the same question.
- One rater (Claude) scored the answers against the reference answers, without blinding. The key facts were split out of `eval_simple.csv` by the same rater.
- Some reference facts (exact doses, renal intervals) depend on what the sources contain. Both systems are told to give doses only when a source states them, which lowers correctness for both.
- The planner model differs between the runs, so the score gap cannot be credited to the answer model alone (section 4, point 2).

---

## Appendix: key-fact scoring

✔ = 1, ½ = 0.5, ✗ = 0.

**Q1 Pyelonephritis (14 facts): GPT 9 · Qwen 10**

| Key fact | GPT | Qwen |
|---|---|---|
| Most likely: acute pyelonephritis | ✔ | ✔ |
| Assess for SIRS / sepsis | ✗ | ✔ |
| Obstructed infected kidney | ✔ | ½ |
| Renal or perinephric abscess | ½ | ½ |
| Cystitis does not explain fever and flank pain | ✔ | ✔ |
| Gynecologic causes (ectopic, PID/TOA, torsion) | ½ (generic) | ½ (generic) |
| Appendicitis, cholecystitis, uncomplicated stone | ½ | ½ |
| Pregnancy test | ✗ | ✗ |
| Urinalysis + urine culture | ✔ | ✔ |
| Blood cultures | ✔ | ✔ |
| CBC, creatinine, lactate | ½ | ½ |
| Imaging if obstruction/abscess or no improvement at 48–72 h | ✔ | ✔ |
| IV antibiotics and fluids | ½ | ½ |
| Admit if septic, pregnant or unable to take oral medication | ½ | ✔ |

**Q2 T2DM + ASCVD (8 facts): GPT 5.5 · Qwen 2**

| Key fact | GPT | Qwen |
|---|---|---|
| Lifestyle and education | ✔ | ✗ |
| GLP-1 RA or SGLT2i with CV benefit regardless of HbA1c and metformin | ✔ | ✔ |
| Agents named | ✗ | ✔ |
| ≥1.5% above target → start combination therapy | ✔ | ✗ |
| High-intensity statin | ✔ | ✗ |
| Aspirin | ½ | ✗ |
| BP <130/80 | ½ | ✗ |
| eGFR and urine albumin | ½ | ✗ |

**Q3 Amoxicillin for AOM (9 facts): GPT 5.5 · Qwen 4.5**

| Key fact | GPT | Qwen |
|---|---|---|
| 80–90 mg/kg/day | ✔ | ✔ |
| In 2 doses, every 12 h | ½ (BID or TID) | ✔ |
| Not above the adult maximum | ½ (wrong example) | ✗ |
| Duration by age (10 / 7 / 5–7 days) | ✔ | ✔ |
| Amoxicillin-clavulanate if amoxicillin in the last 30 days or purulent conjunctivitis | ✗ | ✗ |
| Renal adjustment only when GFR <30 | ✔ | ½ |
| Every 12 h at GFR 10–30, every 24 h below 10 | ✗ | ✗ |
| No adjustment in mild or moderate impairment | ½ | ✗ |
| Check a drug reference or pharmacist | ✔ | ✔ |

**Q4 ABG (6 facts): GPT 3.5 · Qwen 6**

| Key fact | GPT | Qwen |
|---|---|---|
| HAGMA with appropriate compensation | ✔ | ✔ |
| Low pH + low HCO3 = metabolic acidosis | ✔ | ✔ |
| AG 23, high | ✔ | ✔ |
| Winter's 27.5 ± 2, PaCO2 28 is appropriate | ✗ | ✔ |
| Delta ratio 1, no additional disorder | ✗ | ✔ |
| Lactate, ketones, creatinine, osmolar gap, salicylates | ½ | ✔ |

**Q5 CHA2DS2-VASc (7 facts): GPT 7 · Qwen 3**

| Key fact | GPT | Qwen |
|---|---|---|
| Score 4 with components | ✔ | ✔ |
| Assumes AF | ✔ | ½ |
| OAC recommended | ✔ | ✔ |
| DOAC preferred over warfarin | ✔ | ✗ |
| Dose by renal function | ✔ | ✗ |
| Aspirin is not an alternative | ✔ | ✗ |
| Bleeding risk used to fix modifiable factors, not to withhold OAC | ✔ | ½ |

**Q6 SOAP note (8 facts): GPT 7.5 · Qwen 5.5**

| Key fact | GPT | Qwen |
|---|---|---|
| Correct S/O sections | ✔ | ✔ |
| Likely group A strep | ✔ | ½ |
| Centor 4 | ✔ | ✔ |
| Differential: viral, mononucleosis | ✔ | ½ |
| Rapid strep test ± culture | ✔ | ✔ |
| Penicillin V or amoxicillin 500 mg BID for 10 days | ½ (no dose) | ½ (no dose) |
| Paracetamol/ibuprofen and fluids | ✔ | ½ |
| Return precautions (swallowing, breathing, drooling, 48–72 h) | ✔ | ½ |

**Q7 Hypertension for a patient (11 facts): GPT 9.5 · Qwen 7.5**

| Key fact | GPT | Qwen |
|---|---|---|
| What blood pressure is | ✔ | ✔ |
| About 140/90 on repeated readings | ½ | ✗ |
| Often silent; harms heart, brain, kidneys, eyes | ✔ | ✔ |
| Controllable | ✔ | ✔ |
| Less salt, with local examples | ✔ | ½ |
| More vegetables and fruit | ✔ | ✔ |
| Walk 30 min most days | ½ | ½ |
| Lose weight; stop smoking and shisha | ½ | ½ |
| Take medication daily even when feeling well; don't stop it | ✔ | ½ |
| Home BP readings recorded; regular follow-up | ✔ | ½ |
| Emergency symptoms | ✔ | ✔ |

**Q8 SGLT2i in HFpEF (9 facts): GPT 7 · Qwen 3.5**

| Key fact | GPT | Qwen |
|---|---|---|
| EMPEROR-Preserved (HR 0.79) | ½ | ½ |
| DELIVER (HR 0.82) | ½ | ½ |
| Composite reduced, driven by hospitalizations | ✔ | ✔ |
| No clear mortality reduction | ✔ | ✔ |
| Modest symptom / QoL benefit | ✔ | ✗ |
| Benefit with or without diabetes | ✔ | ✗ |
| ESC 2023 Class I | ✗ | ✗ |
| ACC/AHA 2022 Class 2a | ✔ | ✗ |
| Genital infections, volume depletion, euglycemic DKA | ✔ | ½ |

**Q9 Anaphylaxis (10 facts): GPT 10 · Qwen 8.5**

| Key fact | GPT | Qwen |
|---|---|---|
| Call for help | ✔ | ✔ |
| IM epinephrine 0.5 mg, outer thigh, immediately | ✔ | ½ (0.3 mg, "or deltoid") |
| Repeat every 5 min | ✔ | ✔ |
| Flat with legs raised | ✔ | ✔ |
| High-flow oxygen; early airway, prepare to intubate | ✔ | ½ (no oxygen) |
| IV access + fluid bolus for hypotension | ✔ | ½ (delayed) |
| Salbutamol | ✔ | ✔ |
| IV epinephrine infusion + ICU after 2 doses | ✔ | ✔ |
| Antihistamines only after epinephrine; steroids not routine | ✔ | ✔ |
| Observation; auto-injectors; allergy referral | ✔ | ✔ |

**Q10 MCQs (5 facts): GPT 0 · Qwen 4.5**

| Key fact | GPT | Qwen |
|---|---|---|
| 5 questions | ✗ | ✔ |
| Clinical vignettes | ✗ | ✔ |
| 4 options each | ✗ | ½ (5 options, as Sina's layout asks) |
| Answer + explanation | ✗ | ✔ |
| Tests the distinguishing features (MCD, low C3, RBC casts vs fat bodies, thrombosis) | ✗ | ✔ |
